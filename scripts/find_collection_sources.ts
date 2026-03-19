
import Database from "better-sqlite3";
import { join } from "node:path";
import { homedir } from "node:os";

const ZOTERO_DIR = process.env.ZOTERO_DATA_DIR || join(homedir(), "Zotero");
const DB_PATH = join(ZOTERO_DIR, "zotero.sqlite");

function findCollectionSources(collectionLabel: string) {
  const db = new Database(DB_PATH, { readonly: true });
  try {
    const collection = db.prepare("SELECT collectionID FROM collections WHERE collectionName = ?").get(collectionLabel) as { collectionID: number } | undefined;
    if (!collection) {
      console.log(`Collection "${collectionLabel}" not found.`);
      return;
    }

    const items = db.prepare(`
      SELECT i.key, idv.value as title
      FROM collectionItems ci
      JOIN items i ON i.itemID = ci.itemID
      JOIN itemData id ON id.itemID = i.itemID
      JOIN itemDataValues idv ON idv.valueID = id.valueID
      JOIN fields f ON f.fieldID = id.fieldID AND f.fieldName = 'title'
      WHERE ci.collectionID = ?
    `).all(collection.collectionID) as { key: string; title: string }[];

    console.log(`Found ${items.length} items in collection "${collectionLabel}":`);
    for (const item of items) {
      const pdf = db.prepare(`
        SELECT ia.path, i.key as attachmentKey
        FROM itemAttachments ia
        JOIN items i ON i.itemID = ia.itemID
        WHERE ia.parentItemID = (SELECT itemID FROM items WHERE key = ?)
          AND ia.contentType = 'application/pdf'
        LIMIT 1
      `).get(item.key) as { path: string; attachmentKey: string } | undefined;
      
      if (pdf) {
        let fullPath = pdf.path;
        if (fullPath.startsWith("storage:")) {
          fullPath = join(ZOTERO_DIR, "storage", pdf.attachmentKey, fullPath.slice(8));
        }
        console.log(`- ${item.title} (Key: ${item.key}) -> PDF: ${fullPath}`);
      } else {
        console.log(`- ${item.title} (Key: ${item.key}) -> No PDF found.`);
      }
    }
  } finally {
    db.close();
  }
}

findCollectionSources("LLM-FineTuning");
