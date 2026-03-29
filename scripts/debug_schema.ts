import Database from 'better-sqlite3';
import { join, resolve } from 'node:path';
import * as os from 'node:os';
import * as fs from 'node:fs';

const ZOTERO_DIR = join(os.homedir(), "Zotero");
const DB_PATH = join(ZOTERO_DIR, "zotero.sqlite");

const tempDbPath = join(os.tmpdir(), `zotero-debug-${Date.now()}.sqlite`);
fs.copyFileSync(DB_PATH, tempDbPath);

const db = new Database(tempDbPath, { readonly: true });
const tables = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%creator%'").all() as { name: string }[];
console.log('Creator tables:', tables);

for (const table of tables) {
    const columns = db.prepare(`PRAGMA table_info(${table.name})`).all();
    console.log(`Schema for ${table.name}:`, columns);
}
db.close();
