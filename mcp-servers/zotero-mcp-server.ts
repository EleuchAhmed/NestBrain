/**
 * Zotero MCP Server
 * =================
 * A Model Context Protocol server that provides search, metadata
 * retrieval, and PDF path resolution against a local Zotero SQLite
 * database.  Uses `better-sqlite3` for zero-copy reads and the
 * official `@modelcontextprotocol/sdk` for MCP transport.
 *
 * Tools exposed:
 *   - search       : full-text search across titles, creators, tags
 *   - get_item     : detailed metadata for a specific item key
 *   - get_pdf_path : resolve the on-disk path to a PDF attachment
 *
 * Usage:
 *   npx tsx mcp-servers/zotero-mcp-server.ts
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import Database from "better-sqlite3";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

// ── Paths ──────────────────────────────────────────────────────

const ZOTERO_DIR = process.env.ZOTERO_DATA_DIR ?? join(homedir(), "Zotero");
const DB_PATH = join(ZOTERO_DIR, "zotero.sqlite");
const STORAGE_DIR = join(ZOTERO_DIR, "storage");

// ── Database helpers ───────────────────────────────────────────

function openDb(): Database.Database {
  if (!existsSync(DB_PATH)) {
    throw new Error(`Zotero database not found at ${DB_PATH}`);
  }
  return new Database(DB_PATH, { readonly: true, fileMustExist: true });
}

interface SearchRow {
  itemKey: string;
  title: string;
  creators: string | null;
  date: string | null;
  itemType: string;
}

function searchItems(db: Database.Database, query: string, limit: number): SearchRow[] {
  const sql = `
    SELECT DISTINCT
      i.key       AS itemKey,
      idv.value   AS title,
      GROUP_CONCAT(
        CASE WHEN cd.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'firstName')
             THEN cd.value ELSE NULL END
        || ' ' ||
        CASE WHEN cd.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'lastName')
             THEN cd.value ELSE NULL END,
        '; '
      ) AS creators,
      dv.value    AS date,
      it.typeName AS itemType
    FROM items i
    JOIN itemData id   ON id.itemID  = i.itemID
    JOIN itemDataValues idv ON idv.valueID = id.valueID
    JOIN fields f      ON f.fieldID  = id.fieldID AND f.fieldName = 'title'
    JOIN itemTypes it   ON it.itemTypeID = i.itemTypeID
    LEFT JOIN itemCreators ic ON ic.itemID = i.itemID
    LEFT JOIN creators c      ON c.creatorID = ic.creatorID
    LEFT JOIN creatorData cd  ON cd.creatorDataID = c.creatorDataID
    LEFT JOIN itemData id2    ON id2.itemID = i.itemID
    LEFT JOIN fields f2       ON f2.fieldID = id2.fieldID AND f2.fieldName = 'date'
    LEFT JOIN itemDataValues dv ON dv.valueID = id2.valueID AND f2.fieldName = 'date'
    WHERE idv.value LIKE ? COLLATE NOCASE
      AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
    GROUP BY i.itemID
    ORDER BY i.dateModified DESC
    LIMIT ?
  `;
  return db.prepare(sql).all(`%${query}%`, limit) as SearchRow[];
}

interface ItemDetail {
  itemKey: string;
  itemType: string;
  fields: Record<string, string>;
  creators: string[];
  tags: string[];
  citekey: string | null;
}

function getItem(db: Database.Database, itemKey: string): ItemDetail | null {
  const item = db.prepare(
    `SELECT itemID, key, itemTypeID FROM items WHERE key = ?`
  ).get(itemKey) as { itemID: number; key: string; itemTypeID: number } | undefined;

  if (!item) return null;

  const typeName = (
    db.prepare(`SELECT typeName FROM itemTypes WHERE itemTypeID = ?`).get(item.itemTypeID) as { typeName: string }
  ).typeName;

  // Fields
  const fieldsRows = db.prepare(`
    SELECT f.fieldName, idv.value
    FROM itemData id
    JOIN fields f           ON f.fieldID  = id.fieldID
    JOIN itemDataValues idv ON idv.valueID = id.valueID
    WHERE id.itemID = ?
  `).all(item.itemID) as { fieldName: string; value: string }[];

  const fields: Record<string, string> = {};
  for (const r of fieldsRows) fields[r.fieldName] = r.value;

  // Creators
  const creatorsRows = db.prepare(`
    SELECT cd.firstName, cd.lastName
    FROM itemCreators ic
    JOIN creators c      ON c.creatorID = ic.creatorID
    JOIN creatorData cd  ON cd.creatorDataID = c.creatorDataID
    WHERE ic.itemID = ?
    ORDER BY ic.orderIndex
  `).all(item.itemID) as { firstName: string | null; lastName: string | null }[];

  const creators = creatorsRows.map(
    (c) => [c.firstName, c.lastName].filter(Boolean).join(" ")
  );

  // Tags
  const tagsRows = db.prepare(`
    SELECT t.name FROM itemTags it JOIN tags t ON t.tagID = it.tagID WHERE it.itemID = ?
  `).all(item.itemID) as { name: string }[];
  const tags = tagsRows.map((t) => t.name);

  // Better BibTeX citekey (if extension is installed)
  let citekey: string | null = null;
  try {
    const bbtRow = db.prepare(
      `SELECT value FROM settings WHERE setting = 'better-bibtex' AND key = ?`
    ).get(itemKey) as { value: string } | undefined;

    if (!bbtRow) {
      // Try the betterbibtex table if it exists
      const ck = db.prepare(
        `SELECT citationKey FROM betterbibtex.citationkey WHERE itemKey = ?`
      ).get(itemKey) as { citationKey: string } | undefined;
      if (ck) citekey = ck.citationKey;
    } else {
      citekey = bbtRow.value;
    }
  } catch {
    // Better BibTeX not installed or table not found — that's fine
  }

  return { itemKey: item.key, itemType: typeName, fields, creators, tags, citekey };
}

function getPdfPath(db: Database.Database, itemKey: string): string | null {
  // Find attachment items linked to the parent
  const parentItem = db.prepare(
    `SELECT itemID FROM items WHERE key = ?`
  ).get(itemKey) as { itemID: number } | undefined;

  if (!parentItem) return null;

  const attachment = db.prepare(`
    SELECT ia.itemID, i.key AS attachmentKey, ia.path
    FROM itemAttachments ia
    JOIN items i ON i.itemID = ia.itemID
    WHERE ia.parentItemID = ?
      AND ia.contentType = 'application/pdf'
    LIMIT 1
  `).get(parentItem.itemID) as { itemID: number; attachmentKey: string; path: string | null } | undefined;

  if (!attachment) return null;

  // Zotero stores relative paths as "storage:<filename>"
  if (attachment.path?.startsWith("storage:")) {
    const filename = attachment.path.slice("storage:".length);
    return join(STORAGE_DIR, attachment.attachmentKey, filename);
  }

  return attachment.path ?? null;
}

// ── MCP Server ─────────────────────────────────────────────────

const server = new Server(
  { name: "zotero-mcp-server", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "search",
      description:
        "Search the local Zotero library by title.  Returns matching items with keys, titles, creators, dates, and types.",
      inputSchema: {
        type: "object" as const,
        properties: {
          query: { type: "string", description: "Search query (matched against titles)" },
          limit: { type: "number", description: "Max results to return (default 10)" },
        },
        required: ["query"],
      },
    },
    {
      name: "get_item",
      description:
        "Retrieve full metadata for a Zotero item by its item key. Includes fields, creators, tags, and BibTeX citekey.",
      inputSchema: {
        type: "object" as const,
        properties: {
          itemKey: { type: "string", description: "The Zotero item key (e.g. 'ABC12345')" },
        },
        required: ["itemKey"],
      },
    },
    {
      name: "get_pdf_path",
      description:
        "Resolve the absolute file-system path to the PDF attachment of a Zotero item.",
      inputSchema: {
        type: "object" as const,
        properties: {
          itemKey: { type: "string", description: "The Zotero item key" },
        },
        required: ["itemKey"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const db = openDb();

  try {
    switch (name) {
      case "search": {
        const query = (args as { query: string; limit?: number }).query;
        const limit = (args as { limit?: number }).limit ?? 10;
        const results = searchItems(db, query, limit);
        return {
          content: [{ type: "text", text: JSON.stringify(results, null, 2) }],
        };
      }

      case "get_item": {
        const itemKey = (args as { itemKey: string }).itemKey;
        const item = getItem(db, itemKey);
        if (!item) {
          return {
            content: [{ type: "text", text: `No item found with key: ${itemKey}` }],
            isError: true,
          };
        }
        return {
          content: [{ type: "text", text: JSON.stringify(item, null, 2) }],
        };
      }

      case "get_pdf_path": {
        const itemKey = (args as { itemKey: string }).itemKey;
        const pdfPath = getPdfPath(db, itemKey);
        if (!pdfPath) {
          return {
            content: [{ type: "text", text: `No PDF found for item: ${itemKey}` }],
            isError: true,
          };
        }
        return {
          content: [{ type: "text", text: JSON.stringify({ itemKey, pdfPath }, null, 2) }],
        };
      }

      default:
        return {
          content: [{ type: "text", text: `Unknown tool: ${name}` }],
          isError: true,
        };
    }
  } finally {
    db.close();
  }
});

// ── Start ──────────────────────────────────────────────────────

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Zotero MCP server running on stdio");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});