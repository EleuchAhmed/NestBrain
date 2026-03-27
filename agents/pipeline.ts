/**
 * Research Pipeline Agent v2.0
 * ============================
 * 4-Stage Knowledge Automation: Zotero → NotebookLM → DeepSeek → Obsidian
 *
 * Stage 1: Scan Zotero local SQLite for collections & items
 * Stage 2: Upload sources to NotebookLM, run 10-query interrogation
 * Stage 3: Feed responses to DeepSeek (Ollama) for 6-task synthesis
 * Stage 4: Write/update per-collection master notes in Obsidian vault
 */

import * as fs from "node:fs";
import * as path from "node:path";
import * as http from "node:http";
import { fileURLToPath } from "node:url";
import * as os from "node:os";
import { config } from "dotenv";
import { execFile } from "node:child_process";
import * as util from "node:util";
const execFileAsync = util.promisify(execFile);
import Database from "better-sqlite3";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Load environment ───────────────────────────────────────────

config({ path: path.resolve(__dirname, "..", ".env") });

const VAULT_PATH: string = process.env.OBSIDIAN_VAULT_PATH ?? "";
const OLLAMA_HOST: string = process.env.OLLAMA_HOST ?? "http://localhost:11434";
const REGISTRY_PATH = path.resolve(__dirname, "..", "pipeline-registry.json");
const ZOTERO_DIR = process.env.ZOTERO_DATA_DIR ?? path.join(os.homedir(), "Zotero");
const ZOTERO_DB = path.join(ZOTERO_DIR, "zotero.sqlite");
const ZOTERO_STORAGE = path.join(ZOTERO_DIR, "storage");

// ── NotebookLM Python Bridge ───────────────────────────────────

async function callNotebookLmPython(action: string, args: any): Promise<any> {
  const scriptPath = path.resolve(__dirname, "..", "scripts", "notebooklm_operations.py");
  const payload = JSON.stringify({ action, args });
  
  return new Promise((resolve, reject) => {
    const { spawn } = require("node:child_process");
    const child = spawn(process.platform === "win32" ? "python" : "python3", [scriptPath]);
    
    let stdoutData = "";
    let stderrData = "";
    
    child.stdout.on("data", (data: any) => { stdoutData += data; });
    child.stderr.on("data", (data: any) => { stderrData += data; });
    
    child.on("close", (code: number) => {
      try {
        const lines = stdoutData.trim().split('\\n');
        const dataLine = lines[lines.length - 1] || "{}";
        const data = JSON.parse(dataLine);
        if (data.error || code !== 0) throw new Error(data.error || `Process exited with code ${code}`);
        resolve(data);
      } catch (e: any) {
        reject(new Error(`Python Bridge Error: ${e.message}\\nOutput: ${stdoutData.substring(0, 1000)}\\nStderr: ${stderrData.substring(0, 1000)}`));
      }
    });

    child.on("error", (err: any) => reject(err));

    child.stdin.write(payload);
    child.stdin.end();
  });
}

// ── Registry (persistence for processed sources) ───────────────

interface CollectionRegistry {
  name: string;
  obsidianPath: string;
  notebookId: string | null;
  processedSources: string[];
  lastUpdated: string;
}

interface PipelineRegistry {
  collections: Record<string, CollectionRegistry>;
}

function loadRegistry(): PipelineRegistry {
  if (fs.existsSync(REGISTRY_PATH)) {
    return JSON.parse(fs.readFileSync(REGISTRY_PATH, "utf-8"));
  }
  return { collections: {} };
}

function saveRegistry(reg: PipelineRegistry): void {
  fs.writeFileSync(REGISTRY_PATH, JSON.stringify(reg, null, 2), "utf-8");
}

// ── Helpers ────────────────────────────────────────────────────

function ollamaRequest(endpoint: string, payload?: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const url = new URL(endpoint, OLLAMA_HOST);
    const options: http.RequestOptions = {
      method: payload ? "POST" : "GET",
      headers: payload ? { "Content-Type": "application/json" } : {},
    };

    const req = http.request(url, options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        if (res.statusCode && res.statusCode >= 400) {
          reject(new Error(`Ollama API Error ${res.statusCode}: ${data}`));
        } else {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            reject(new Error("Failed to parse Ollama JSON response: " + data));
          }
        }
      });
    });

    req.on("error", reject);
    if (payload) {
      req.write(JSON.stringify(payload));
    }
    req.end();
  });
}

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9- ]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function log(emoji: string, msg: string): void {
  console.log(`${emoji} ${msg}`);
}

function logErr(msg: string, err?: any): void {
  console.error(`❌ ${msg}`, err?.message ?? err ?? "");
}

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── STAGE 1: Zotero Local SQLite Scanning ──────────────────────

interface ZoteroItem {
  key: string;
  title: string;
  type: string;
  url?: string;
  date?: string;
  authors?: string;
  abstract?: string;
  pdfPath?: string;
}

function parseMcpResponse(result: any): any {
  if (!result || !result.content || result.content.length === 0) {
    throw new Error("Empty MCP response");
  }

  const text = result.content[0].text;
  if (!text) {
    throw new Error("No text in MCP response content");
  }

  // Check for raw error strings from the MCP server
  if (text.startsWith("Error:")) {
    throw new Error(text);
  }

  try {
    return JSON.parse(text);
  } catch (err) {
    // If it's not JSON, return the raw text (some tools like query_notebook return raw text)
    return text;
  }
}

interface ZoteroCollection {
  key: string;
  name: string;
  items: ZoteroItem[];
}

function openZoteroDB(): { db: Database.Database; cleanup: () => void } {
  if (!fs.existsSync(ZOTERO_DB)) {
    throw new Error(`Zotero database not found at ${ZOTERO_DB}. Set ZOTERO_DATA_DIR or install Zotero.`);
  }

  // Create a temporary copy to avoid "database is locked" errors if Zotero is open
  const tempDbPath = path.join(os.tmpdir(), `zotero-${Date.now()}.sqlite`);
  fs.copyFileSync(ZOTERO_DB, tempDbPath);

  const db = new Database(tempDbPath, { readonly: true, fileMustExist: true });
  
  const cleanup = () => {
    try {
      db.close();
      if (fs.existsSync(tempDbPath)) {
        fs.unlinkSync(tempDbPath);
      }
    } catch (e) {
      console.error('Warning: Failed to clean up temp Zotero DB:', e);
    }
  };

  return { db, cleanup };
}

function scanZoteroCollections(): ZoteroCollection[] {
  const { db, cleanup } = openZoteroDB();
  const collections: ZoteroCollection[] = [];

  try {
    // Get all collections
    const collRows = db.prepare(`
      SELECT collectionID, collectionName, key FROM collections
    `).all() as { collectionID: number; collectionName: string; key: string }[];

    for (const coll of collRows) {
      // Get items in this collection (skip attachments — they are children)
      const itemRows = db.prepare(`
        SELECT DISTINCT i.itemID, i.key, it.typeName
        FROM collectionItems ci
        JOIN items i ON i.itemID = ci.itemID
        JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
        WHERE ci.collectionID = ?
          AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
          AND it.typeName != 'attachment'
          AND it.typeName != 'note'
      `).all(coll.collectionID) as { itemID: number; key: string; typeName: string }[];

      const items: ZoteroItem[] = [];

      for (const row of itemRows) {
        // Get title
        const titleRow = db.prepare(`
          SELECT idv.value
          FROM itemData id
          JOIN fields f ON f.fieldID = id.fieldID AND f.fieldName = 'title'
          JOIN itemDataValues idv ON idv.valueID = id.valueID
          WHERE id.itemID = ?
        `).get(row.itemID) as { value: string } | undefined;

        // Get URL
        const urlRow = db.prepare(`
          SELECT idv.value
          FROM itemData id
          JOIN fields f ON f.fieldID = id.fieldID AND f.fieldName = 'url'
          JOIN itemDataValues idv ON idv.valueID = id.valueID
          WHERE id.itemID = ?
        `).get(row.itemID) as { value: string } | undefined;

        // Get date
        const dateRow = db.prepare(`
          SELECT idv.value
          FROM itemData id
          JOIN fields f ON f.fieldID = id.fieldID AND f.fieldName = 'date'
          JOIN itemDataValues idv ON idv.valueID = id.valueID
          WHERE id.itemID = ?
        `).get(row.itemID) as { value: string } | undefined;

        // Get abstract
        const abstractRow = db.prepare(`
          SELECT idv.value
          FROM itemData id
          JOIN fields f ON f.fieldID = id.fieldID AND (f.fieldName = 'abstractNote' OR f.fieldName = 'abstract')
          JOIN itemDataValues idv ON idv.valueID = id.valueID
          WHERE id.itemID = ?
        `).get(row.itemID) as { value: string } | undefined;

        // Get creators
        const creatorRows = db.prepare(`
          SELECT c.firstName, c.lastName
          FROM itemCreators ic
          JOIN creators c ON c.creatorID = ic.creatorID
          WHERE ic.itemID = ?
          ORDER BY ic.orderIndex
        `).all(row.itemID) as { firstName: string | null; lastName: string | null }[];

        const authors = creatorRows
          .map((c) => [c.firstName, c.lastName].filter(Boolean).join(" "))
          .join("; ");

        // Get PDF attachment path
        let pdfPath: string | undefined;
        const pdfRow = db.prepare(`
          SELECT ia.path, i2.key AS attachmentKey
          FROM itemAttachments ia
          JOIN items i2 ON i2.itemID = ia.itemID
          WHERE ia.parentItemID = ?
            AND ia.contentType = 'application/pdf'
          LIMIT 1
        `).get(row.itemID) as { path: string | null; attachmentKey: string } | undefined;

        if (pdfRow?.path) {
          if (pdfRow.path.startsWith("storage:")) {
            pdfPath = path.join(ZOTERO_STORAGE, pdfRow.attachmentKey, pdfRow.path.slice(8));
          } else {
            pdfPath = pdfRow.path;
          }
        }

        items.push({
          key: row.key,
          title: titleRow?.value ?? "Untitled",
          type: row.typeName,
          url: urlRow?.value,
          date: dateRow?.value,
          authors: authors || undefined,
          abstract: abstractRow?.value,
          pdfPath,
        });
      }

      if (items.length > 0) {
        collections.push({ key: coll.key, name: coll.collectionName, items });
      }
    }
  } finally {
    cleanup();
  }

  return collections;
}

// ── STAGE 2: NotebookLM Knowledge Extraction ───────────────────

const NOTEBOOKLM_QUERIES = [
  "Provide a comprehensive overview of this source: its main thesis, core arguments, and conclusion.",
  "What are the key concepts, theories, and frameworks introduced? Define each one in detail.",
  "What methodology or approach is used? Describe the evidence, data, or reasoning presented.",
  "What are the most important facts, statistics, findings, or claims in this source?",
  "What are the limitations, open questions, controversies, or gaps identified?",
  "What are the practical applications and real-world implications of this knowledge?",
  "How does this source connect to or contrast with established knowledge in this field?",
  "Generate a timeline of key events or developments mentioned if applicable.",
  "Extract all key terminology and provide detailed definitions for each.",
  "What are the most surprising, counterintuitive, or paradigm-shifting ideas in this source?",
];

async function createNotebook(collectionName: string): Promise<string> {
  const data = await callNotebookLmPython("createNotebook", { title: collectionName });
  log("📓", `Created NotebookLM notebook: ${collectionName} (${data.notebookId})`);
  return data.notebookId;
}

async function ingestSourceToNotebook(notebookId: string, item: ZoteroItem): Promise<boolean> {
  try {
    if (item.url) {
      log("🔌", `Adding URL source: ${item.title} → ${item.url}`);
      await callNotebookLmPython("ingestUrl", { notebookId, url: item.url });
      log("✅", `URL source added: ${item.title}`);
      return true;
    }
    if (item.pdfPath && fs.existsSync(item.pdfPath)) {
      log("🔌", `Adding PDF: ${item.title} → ${item.pdfPath}`);
      const content = `[Source: ${item.title}]\n\n${item.abstract ? `Abstract: ${item.abstract}` : "No abstract available."}\n\nAuthors: ${item.authors || "Unknown"}\nDate: ${item.date || "Unknown"}`;
      await callNotebookLmPython("ingestText", { notebookId, title: item.title, content });
      log("✅", `PDF/Text source added: ${item.title}`);
      return true;
    }
    if (item.abstract) {
      log("🔌", `Adding abstract text: ${item.title}`);
      const content = `# ${item.title}\n${item.authors ? `**Authors:** ${item.authors}` : ""}\n${item.date ? `**Date:** ${item.date}` : ""}\n\n## Abstract\n${item.abstract}`;
      await callNotebookLmPython("ingestText", { notebookId, title: item.title, content });
      log("✅", `Abstract source added: ${item.title}`);
      return true;
    }
    log("⚠️", `No ingestable content for: ${item.title}`);
    return false;
  } catch (err: any) {
    logErr(`Failed to ingest ${item.title}:`, err);
    return false;
  }
}

async function interrogateNotebook(notebookId: string): Promise<string[]> {
  const responses: string[] = [];
  const chunkSize = 3;
  
  for (let i = 0; i < NOTEBOOKLM_QUERIES.length; i += chunkSize) {
    const chunk = NOTEBOOKLM_QUERIES.slice(i, i + chunkSize);
    log("🔍", `Running queries ${i + 1} to ${i + chunk.length}...`);
    try {
      const data = await callNotebookLmPython("interrogate", { notebookId, queries: chunk });
      responses.push(...data.responses);
      log("✅", `Batch received.`);
    } catch (err: any) {
      logErr(`Queries failed:`, err);
      chunk.forEach(q => responses.push(`### Query: ${q}\n\n⚠️ Error: ${err.message}`));
    }
  }
  return responses;
}

async function generateNotebookMedia(notebookId: string): Promise<{ audioUrl: string | null; videoUrl: string | null }> {
  log("🎬", `Requesting media artifacts (this may take up to 5 minutes)...`);
  try {
    const data = await callNotebookLmPython("generateMedia", { notebookId });
    if (data.audioUrl) log("✅", `Audio ready: ${data.audioUrl}`);
    if (data.videoUrl) log("✅", `Video ready: ${data.videoUrl}`);
    if (data.audioError) log("⚠️", `Audio generation failed: ${data.audioError}`);
    if (data.videoError) log("⚠️", `Video generation failed: ${data.videoError}`);
    return { audioUrl: data.audioUrl || null, videoUrl: data.videoUrl || null };
  } catch (err: any) {
    logErr(`Media generation failed:`, err);
    return { audioUrl: null, videoUrl: null };
  }
}

// ── STAGE 3: DeepSeek Synthesis ────────────────────────────────

interface SynthesisResult {
  academicSynthesis: string;
  conceptualDeepDive: string;
  actionableKnowledge: string;
  knowledgeConnections: string;
  criticalEvaluation: string;
  glossary: string;
}

const SYNTHESIS_PROMPTS: { key: keyof SynthesisResult; label: string; prompt: string }[] = [
  {
    key: "academicSynthesis",
    label: "Task A — Academic Synthesis",
    prompt: `You are a rigorous academic research assistant. Based on the following NotebookLM knowledge extraction responses, produce a comprehensive academic-style synthesis that includes:
- Background context and positioning within the field
- Methodology or approaches described
- Key findings with specific evidence, numbers, and citations
- Critical analysis of the strengths and weaknesses of the arguments
- Research gaps and open questions

Write at graduate-student comprehension level. Be thorough and precise. Every sentence must carry specific information — no filler.

NotebookLM Responses:
`,
  },
  {
    key: "conceptualDeepDive",
    label: "Task B — Conceptual Deep Dive",
    prompt: `You are an expert educator. From the following knowledge extraction responses, identify every major concept. For EACH concept, provide TWO explanations:

**ELI5 (Explain Like I'm 5):** A simple analogy or metaphor a child would understand.
**Expert Layer:** Full technical depth with nuance, edge cases, and precise terminology.
**Application:** One concrete real-world application of this concept.

Use markdown headers for each concept (### Concept Name). Be exhaustive — do not skip any concept.

NotebookLM Responses:
`,
  },
  {
    key: "actionableKnowledge",
    label: "Task C — Actionable Knowledge",
    prompt: `You are a practical knowledge engineer. From the following knowledge extraction responses, extract ALL concrete, actionable takeaways. For each, specify:

- What specific action can be taken
- What tools, frameworks, or methodologies to use
- What habits or practices to adopt
- Expected outcomes or benefits

Use a numbered list. Be specific — not "learn more about X" but "implement X using Y framework to achieve Z".

NotebookLM Responses:
`,
  },
  {
    key: "knowledgeConnections",
    label: "Task D — Knowledge Graph Connections",
    prompt: `You are a knowledge graph architect. From the following responses, identify ALL relationships between:
1. Concepts WITHIN this source
2. Connections to broader established knowledge in the field

For each connection, use Obsidian [[wikilink]] format when referencing related topics or concepts. Explain WHY the connection exists and what it implies.

Format as a bullet list with [[wikilinks]] embedded naturally in the text.

NotebookLM Responses:
`,
  },
  {
    key: "criticalEvaluation",
    label: "Task E — Critical Evaluation",
    prompt: `You are a critical academic reviewer. From the following knowledge extraction responses, evaluate the sources critically:

- Identify potential biases (confirmation bias, selection bias, funding bias, etc.)
- Highlight weaknesses in argumentation or methodology
- Point out conflicting evidence or alternative interpretations
- List unanswered questions that remain after studying this material
- Assess the overall reliability and quality of the evidence presented

Be specific and cite particular claims when identifying issues.

NotebookLM Responses:
`,
  },
  {
    key: "glossary",
    label: "Task F — Glossary Generation",
    prompt: `You are a technical lexicographer. From the following knowledge extraction responses, produce a COMPLETE glossary of every technical, domain-specific, or potentially unfamiliar term used.

Format each entry as:
**Term**: Clear, detailed definition with context of how it's used in this material.

Order alphabetically. Be thorough — every technical term must appear. Definitions should be precise enough to stand alone without additional context.

NotebookLM Responses:
`,
  },
];

async function runDeepSeekSynthesis(notebookLmResponses: string[]): Promise<SynthesisResult> {
  const combinedContext = notebookLmResponses.join("\n\n---\n\n");
  const result: SynthesisResult = {
    academicSynthesis: "",
    conceptualDeepDive: "",
    actionableKnowledge: "",
    knowledgeConnections: "",
    criticalEvaluation: "",
    glossary: "",
  };

  for (const task of SYNTHESIS_PROMPTS) {
    log("🧠", `Running ${task.label}...`);

    const fullPrompt = task.prompt + combinedContext;
    let attempts = 0;
    let success = false;

    while (attempts < 2 && !success) {
      attempts++;
      try {
        const resp = await ollamaRequest("/api/generate", {
          model: "deepseek-r1:14b",
          prompt: fullPrompt,
          stream: false,
          options: { temperature: 0.3, num_predict: 4000 },
        });

        let rawText: string = resp.response || "";
        // Strip <think> blocks from deepseek-r1
        rawText = rawText.replace(/<think>[\s\S]*?<\/think>\s*/gi, "").trim();

        if (rawText.length > 50) {
          result[task.key] = rawText;
          success = true;
          log("✅", `${task.label} complete (${rawText.length} chars)`);
        } else {
          log("⚠️", `${task.label} returned insufficient content (attempt ${attempts})`);
        }
      } catch (e: any) {
        logErr(`${task.label} failed (attempt ${attempts}):`, e);
      }
    }

    if (!success) {
      result[task.key] = `⚠️ Synthesis failed after ${attempts} attempts. Manual review needed.`;
    }
  }

  return result;
}

// ── STAGE 4: Obsidian Note Writing ─────────────────────────────

function buildSourcesIndexTable(items: ZoteroItem[]): string {
  const rows = items.map((item, i) => {
    const typeIcon =
      item.type === "videoRecording"
        ? "🎥 Video"
        : item.type === "webpage"
          ? "🌐 URL"
          : item.type === "journalArticle"
            ? "📄 Paper"
            : "📄 PDF";
    return `| ${i + 1} | ${item.title} | ${typeIcon} | ${item.key} | ${item.date ?? "N/A"} |`;
  });

  return [
    "| # | Title | Type | Key | Date Added |",
    "|---|-------|------|-----|------------|",
    ...rows,
  ].join("\n");
}

function renderMasterNote(
  collection: ZoteroCollection,
  synthesis: SynthesisResult,
  notebookLmResponses: string[],
  media: { audioUrl: string | null; videoUrl: string | null },
  processedKeys: string[]
): string {
  const now = new Date().toISOString();
  // Extract collection summary from first query response
  const summaryContent = notebookLmResponses[0]
    ? notebookLmResponses[0].split("\n\n").slice(1).join("\n\n").trim()
    : "_No summary available yet._";

  // Extract key findings from query 4
  const keyFindings = notebookLmResponses[3]
    ? notebookLmResponses[3].split("\n\n").slice(1).join("\n\n").trim()
    : "_Pending extraction._";

  const frontmatter = [
    "---",
    "tags:",
    `  - collection/${slugify(collection.name)}`,
    "  - auto-generated",
    "  - pipeline/zotero",
    `collection: "${collection.name}"`,
    `last_updated: "${now}"`,
    `sources_processed: [${processedKeys.map((k) => `"${k}"`).join(", ")}]`,
    `notebooklm_video: ${media.videoUrl ? `"${media.videoUrl}"` : "null"}`,
    `notebooklm_audio: ${media.audioUrl ? `"${media.audioUrl}"` : "null"}`,
    `status: "up-to-date"`,
    "---",
  ].join("\n");

  const mediaSection = [
    "## 🎬 NotebookLM Audio/Video Overview",
    media.audioUrl
      ? `> [🎧 Listen to Audio Overview](${media.audioUrl})`
      : "> _Audio overview not yet generated._",
    media.videoUrl
      ? `> [🎥 Watch Video Summary](${media.videoUrl})`
      : "> _Video summary not yet generated._",
    "> *Auto-generated overview of all sources in this collection.*",
  ].join("\n");

  return [
    frontmatter,
    "",
    `# ${collection.name} — Master Knowledge Note`,
    "",
    mediaSection,
    "",
    "---",
    "",
    "## 📌 Collection Summary",
    "",
    summaryContent,
    "",
    "---",
    "",
    "## 📚 Sources Index",
    "",
    buildSourcesIndexTable(collection.items),
    "",
    "---",
    "",
    "## 🧠 Core Concepts & Frameworks",
    "",
    synthesis.conceptualDeepDive,
    "",
    "---",
    "",
    "## 📖 Academic Deep Dive",
    "",
    synthesis.academicSynthesis,
    "",
    "---",
    "",
    "## 🔬 Key Findings & Evidence",
    "",
    keyFindings,
    "",
    "---",
    "",
    "## ⚡ Actionable Takeaways",
    "",
    synthesis.actionableKnowledge,
    "",
    "---",
    "",
    "## 🗺️ Knowledge Connections",
    "",
    synthesis.knowledgeConnections,
    "",
    "---",
    "",
    "## ⚠️ Critical Evaluation",
    "",
    synthesis.criticalEvaluation,
    "",
    "---",
    "",
    "## 📘 Glossary",
    "",
    synthesis.glossary,
    "",
    "---",
    "",
    "## 🕐 Update Log",
    "",
    "| Date | Sources Added | Summary of Changes |",
    "|------|--------------|-------------------|",
    `| ${now.split("T")[0]} | ${processedKeys.join(", ")} | Initial note creation with ${processedKeys.length} sources |`,
    "",
  ].join("\n");
}

function mergeIntoExistingNote(
  existingContent: string,
  newItems: ZoteroItem[],
  synthesis: SynthesisResult,
  notebookLmResponses: string[],
  media: { audioUrl: string | null; videoUrl: string | null },
  newKeys: string[],
  allKeys: string[]
): string {
  const now = new Date().toISOString();
  let updated = existingContent;

  // Update frontmatter
  updated = updated.replace(/last_updated:\s*"[^"]*"/, `last_updated: "${now}"`);
  updated = updated.replace(
    /sources_processed:\s*\[[^\]]*\]/,
    `sources_processed: [${allKeys.map((k) => `"${k}"`).join(", ")}]`
  );
  if (media.audioUrl) {
    updated = updated.replace(
      /notebooklm_audio:\s*(?:null|"[^"]*")/,
      `notebooklm_audio: "${media.audioUrl}"`
    );
  }
  if (media.videoUrl) {
    updated = updated.replace(
      /notebooklm_video:\s*(?:null|"[^"]*")/,
      `notebooklm_video: "${media.videoUrl}"`
    );
  }

  // Add new sources to Sources Index table
  const tableEnd = updated.lastIndexOf("|\n\n---");
  if (tableEnd > -1) {
    const newRows = newItems
      .map((item) => {
        const typeIcon =
          item.type === "videoRecording"
            ? "🎥 Video"
            : item.type === "webpage"
              ? "🌐 URL"
              : "📄 PDF";
        return `| + | ${item.title} | ${typeIcon} | ${item.key} | ${item.date ?? "N/A"} |`;
      })
      .join("\n");
    updated =
      updated.substring(0, tableEnd + 1) + "\n" + newRows + updated.substring(tableEnd + 1);
  }

  // Append enrichment to each section (never overwrite)
  const appendToSection = (sectionHeader: string, newContent: string) => {
    const marker = `## ${sectionHeader}`;
    const sectionIdx = updated.indexOf(marker);
    if (sectionIdx === -1) return;

    const nextSectionIdx = updated.indexOf("\n---\n", sectionIdx + marker.length);
    if (nextSectionIdx === -1) return;

    const enrichmentBlock = `\n\n### 📎 Updated: ${now.split("T")[0]}\n\n${newContent}\n`;
    updated =
      updated.substring(0, nextSectionIdx) +
      enrichmentBlock +
      updated.substring(nextSectionIdx);
  };

  if (synthesis.conceptualDeepDive)
    appendToSection("🧠 Core Concepts & Frameworks", synthesis.conceptualDeepDive);
  if (synthesis.academicSynthesis)
    appendToSection("📖 Academic Deep Dive", synthesis.academicSynthesis);
  if (synthesis.actionableKnowledge)
    appendToSection("⚡ Actionable Takeaways", synthesis.actionableKnowledge);
  if (synthesis.knowledgeConnections)
    appendToSection("🗺️ Knowledge Connections", synthesis.knowledgeConnections);
  if (synthesis.criticalEvaluation)
    appendToSection("⚠️ Critical Evaluation", synthesis.criticalEvaluation);
  if (synthesis.glossary) appendToSection("📘 Glossary", synthesis.glossary);

  // Append to update log
  const logTableHeaderIdx = updated.lastIndexOf("|------|");
  if (logTableHeaderIdx > -1) {
    const afterHeader = updated.indexOf("\n", logTableHeaderIdx) + 1;
    const newLogRow = `| ${now.split("T")[0]} | ${newKeys.join(", ")} | Added ${newKeys.length} new source(s), enriched all sections |\n`;
    updated = updated.substring(0, afterHeader) + newLogRow + updated.substring(afterHeader);
  }

  return updated;
}

// ── Domain classification ──────────────────────────────────────

function classifyDomain(collectionName: string): string {
  const lower = collectionName.toLowerCase();
  if (
    lower.includes("llm") ||
    lower.includes("ai") ||
    lower.includes("ml") ||
    lower.includes("data") ||
    lower.includes("deep") ||
    lower.includes("fine") ||
    lower.includes("agent")
  )
    return "AI-Data";
  if (lower.includes("cyber") || lower.includes("security") || lower.includes("pentest"))
    return "Cyber";
  if (
    lower.includes("full") ||
    lower.includes("web") ||
    lower.includes("react") ||
    lower.includes("node")
  )
    return "Fullstack";
  return "General-Arch";
}

// ── MAIN ORCHESTRATOR ──────────────────────────────────────────

export async function processCollection(collection: ZoteroCollection): Promise<void> {
  const registry = loadRegistry();
  const collReg = registry.collections[collection.key];
  const processedKeys = new Set(collReg?.processedSources ?? []);

  // Detect new sources
  const newItems = collection.items.filter((item) => !processedKeys.has(item.key));

  if (newItems.length === 0) {
    log(
      "⏭️",
      `Collection "${collection.name}": all ${collection.items.length} sources already processed. Skipping.`
    );
    return;
  }

  const isUpdate = Boolean(collReg?.obsidianPath);
  log(
    "📂",
    `Collection "${collection.name}": ${newItems.length} new source(s) to process${isUpdate ? " (UPDATE mode)" : " (NEW note)"}`
  );

  // ── Stage 2: NotebookLM ──────────────────────────────────────
  let notebookId = collReg?.notebookId ?? null;

  if (!notebookId) {
    notebookId = await createNotebook(collection.name);
  }

  // Ingest new sources
  const successfulKeys: string[] = [];
  const failedItems: ZoteroItem[] = [];

  for (const item of newItems) {
    log("📄", `Processing: ${item.title} (${item.type})`);
    const success = await ingestSourceToNotebook(notebookId, item);
    if (success) {
      successfulKeys.push(item.key);
    } else {
      failedItems.push(item);
    }
    await sleep(1000);
  }

  if (successfulKeys.length === 0) {
    logErr("No sources were successfully ingested. Aborting collection.");
    // Still save failed state in registry
    registry.collections[collection.key] = {
      name: collection.name,
      obsidianPath: collReg?.obsidianPath ?? "",
      notebookId,
      processedSources: [...processedKeys],
      lastUpdated: new Date().toISOString(),
    };
    saveRegistry(registry);
    return;
  }

  // Wait for NotebookLM to process sources
  log("⏳", "Waiting 10s for NotebookLM to process sources...");
  await sleep(10000);

  // Run 10-query interrogation
  log("📥", "Running 10-query NotebookLM interrogation...");
  const notebookLmResponses = await interrogateNotebook(notebookId);

  // Generate media
  const media = await generateNotebookMedia(notebookId);

  // ── Stage 3: DeepSeek Synthesis ──────────────────────────────
  log("🧠", "Running 6-task DeepSeek synthesis...");
  const synthesis = await runDeepSeekSynthesis(notebookLmResponses);

  // ── Stage 4: Obsidian Note ───────────────────────────────────
  const domain = classifyDomain(collection.name);
  const slug = slugify(collection.name);
  const notePath = `20_Concepts/${domain}/${slug}.md`;
  const fullPath = path.join(VAULT_PATH, notePath);
  const fullDir = path.dirname(fullPath);

  if (!fs.existsSync(fullDir)) {
    fs.mkdirSync(fullDir, { recursive: true });
  }

  const allKeys = [...processedKeys, ...successfulKeys];
  let noteContent: string;

  if (isUpdate && fs.existsSync(fullPath)) {
    log("🔄", `Updating existing note: ${notePath}`);
    const existing = fs.readFileSync(fullPath, "utf-8");
    noteContent = mergeIntoExistingNote(
      existing,
      newItems.filter((i) => successfulKeys.includes(i.key)),
      synthesis,
      notebookLmResponses,
      media,
      successfulKeys,
      allKeys
    );
  } else {
    log("📝", `Creating new master note: ${notePath}`);
    noteContent = renderMasterNote(collection, synthesis, notebookLmResponses, media, allKeys);
  }

  fs.writeFileSync(fullPath, noteContent, "utf-8");
  log("✅", `Note saved: ${fullPath}`);

  // Update registry
  registry.collections[collection.key] = {
    name: collection.name,
    obsidianPath: notePath,
    notebookId,
    processedSources: allKeys,
    lastUpdated: new Date().toISOString(),
  };
  saveRegistry(registry);
  log("💾", `Registry updated for collection: ${collection.name}`);

  // Report failures
  if (failedItems.length > 0) {
    log(
      "⚠️",
      `Failed sources (need manual review): ${failedItems.map((i) => i.title).join(", ")}`
    );
  }
}

// ── CLI Entrypoint ─────────────────────────────────────────────

async function main() {
  console.log("\n╔═══════════════════════════════════════════════════╗");
  console.log("║   Research Pipeline v2.0                          ║");
  console.log("║   Zotero → NotebookLM → DeepSeek → Obsidian      ║");
  console.log("╚═══════════════════════════════════════════════════╝\n");

  // Pre-flight checks
  if (!VAULT_PATH) {
    logErr("OBSIDIAN_VAULT_PATH not set in .env");
    process.exit(1);
  }

  log("📍", `Zotero DB: ${ZOTERO_DB}`);
  log("📍", `Obsidian Vault: ${VAULT_PATH}`);
  log("📍", `Registry: ${REGISTRY_PATH}`);

  // Ollama health check
  try {
    const tagsResp = await ollamaRequest("/api/tags");
    const hasDeepSeek = tagsResp.models?.some((m: any) => m.name.includes("deepseek-r1:14b"));
    if (!hasDeepSeek) {
      logErr("Model deepseek-r1:14b not found. Run: ollama pull deepseek-r1:14b");
      process.exit(1);
    }
    log("✅", "Ollama health check passed (deepseek-r1:14b available)");
  } catch (err: any) {
    logErr(`Cannot reach Ollama at ${OLLAMA_HOST}:`, err);
    process.exit(1);
  }

  // Ensure vault directory exists
  if (!fs.existsSync(VAULT_PATH)) {
    logErr(`Obsidian vault not found at: ${VAULT_PATH}`);
    process.exit(1);
  }

  const assetsDir = path.join(VAULT_PATH, "assets");
  if (!fs.existsSync(assetsDir)) {
    fs.mkdirSync(assetsDir, { recursive: true });
    log("📁", `Created assets directory: ${assetsDir}`);
  }

  // ── Stage 1: Scan Zotero ─────────────────────────────────────
  log("🔍", "Scanning Zotero collections...");
  const collections = scanZoteroCollections();

  if (collections.length === 0) {
    log("⏭️", "No collections with items found in Zotero. Nothing to do.");
    process.exit(0);
  }

  log("📚", `Found ${collections.length} collection(s):`);
  for (const coll of collections) {
    log("  📂", `${coll.name} (${coll.key}) — ${coll.items.length} item(s)`);
  }

  // Process each collection sequentially
  for (const collection of collections) {
    try {
      await processCollection(collection);
    } catch (err: any) {
      logErr(`Fatal error processing collection "${collection.name}":`, err);
      // Continue with other collections
    }
  }

  console.log("\n━━━ Pipeline complete ━━━");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});