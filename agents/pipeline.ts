/**
 * Research Pipeline Agent
 * =======================
 * Orchestrates the Zotero → NotebookLM → Obsidian research pipeline.
 *
 * Core functions:
 *   1. checkNotebookLMAuth() — verify NotebookLM credentials
 *   2. routeToFolder(domain)  — map domain tags to vault folders
 *   3. renderNote(metadata)   — produce Obsidian-compatible markdown
 *   4. runPipeline(pdfPath)   — full end-to-end pipeline
 *
 * Usage:
 *   npx tsx agents/pipeline.ts                 # run pipeline on staging/
 *   npx tsx agents/pipeline.ts --check-auth    # just verify auth
 *
 * Required env vars (from .env):
 *   OBSIDIAN_VAULT_PATH, OBSIDIAN_API_KEY, ANTHROPIC_API_KEY
 */

import * as fs from "node:fs";
import * as path from "node:path";
import * as http from "node:http";
import { fileURLToPath } from "node:url";
import { config } from "dotenv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Load environment ───────────────────────────────────────────

config({ path: path.resolve(__dirname, "..", ".env") });

const VAULT_PATH: string = process.env.OBSIDIAN_VAULT_PATH ?? "";
const OBSIDIAN_API_KEY: string = process.env.OBSIDIAN_API_KEY ?? "";
const OBSIDIAN_API_BASE = "http://localhost:27123";

// ── Folder routing ─────────────────────────────────────────────

const FOLDER_ROUTES: Record<string, string> = {
  fullstack: "20_Concepts/Fullstack",
  cyber: "20_Concepts/Cyber",
  "ai-data": "20_Concepts/AI-Data",
  architecture: "20_Concepts/General-Arch",
};

/**
 * Map a domain tag to the corresponding Obsidian vault subfolder.
 * Falls back to `00_Inbox` for unrecognised domains.
 */
export function routeToFolder(domain: string): string {
  const key = domain.toLowerCase().trim();
  return FOLDER_ROUTES[key] ?? "00_Inbox";
}

// ── NotebookLM auth check ──────────────────────────────────────

const AUTH_PATH = path.join(
  process.env.HOME ?? process.env.USERPROFILE ?? "",
  ".notebooklm-mcp",
  "auth.json"
);

interface AuthData {
  cookies?: string;
  expiresAt?: string;
  [key: string]: unknown;
}

/**
 * Verify that NotebookLM credentials exist and are not expired.
 * Returns `{ ok, message }`.
 */
export function checkNotebookLMAuth(): { ok: boolean; message: string } {
  if (!fs.existsSync(AUTH_PATH)) {
    return {
      ok: false,
      message: `Auth file not found at ${AUTH_PATH}. Run: node antigravity-notebooklm-mcp/build/browser-auth.js`,
    };
  }

  try {
    const raw = fs.readFileSync(AUTH_PATH, "utf-8");
    const data: AuthData = JSON.parse(raw);

    if (!data.cookies) {
      return { ok: false, message: "Auth file exists but contains no cookies." };
    }

    if (data.expiresAt) {
      const exp = new Date(data.expiresAt);
      if (exp.getTime() < Date.now()) {
        return {
          ok: false,
          message: `Auth expired at ${exp.toISOString()}. Re-authenticate.`,
        };
      }
    }

    return { ok: true, message: "NotebookLM auth is valid." };
  } catch (err) {
    return { ok: false, message: `Failed to parse auth file: ${err}` };
  }
}

// ── Note rendering ─────────────────────────────────────────────

export interface NoteMetadata {
  title: string;
  citeKey: string;
  domain: string;
  authors: string[];
  year: string;
  abstract: string;
  tags: string[];

  // AI-generated content sections (populated by pipeline)
  analogy?: string;
  whyItMatters?: string;
  architectureDiagram?: string;
  technicalManual?: string;
  interconnections?: string;
}

/**
 * Render an Obsidian-compatible markdown note from metadata.
 *
 * Contains all 5 required sections:
 *   1. The analogy
 *   2. Why it matters
 *   3. Architecture diagram
 *   4. Technical manual
 *   5. Interconnections
 */
export function renderNote(meta: NoteMetadata): string {
  const frontmatter = [
    "---",
    `title: "${meta.title.replace(/"/g, '\\"')}"`,
    `cite-key: ${meta.citeKey}`,
    `domain: ${meta.domain}`,
    `authors:`,
    ...meta.authors.map((a) => `  - "${a}"`),
    `year: "${meta.year}"`,
    `tags:`,
    ...meta.tags.map((t) => `  - ${t}`),
    `date: ${new Date().toISOString().split("T")[0]}`,
    `status: seedling`,
    "---",
  ].join("\n");

  const body = `
# ${meta.title}

> **Authors**: ${meta.authors.join(", ")}
> **Year**: ${meta.year}
> **Cite-key**: \`${meta.citeKey}\`

## Abstract

${meta.abstract}

---

## The analogy

${meta.analogy ?? "_Awaiting AI processing — the pipeline will populate this section with an intuitive analogy that maps the paper's core mechanism to an everyday concept._"}

---

## Why it matters

${meta.whyItMatters ?? "_Awaiting AI processing — explains the real-world impact, what breaks without this, and why an engineer should care._"}

---

## Architecture diagram

${meta.architectureDiagram ?? "```mermaid\nflowchart LR\n  A[Input] --> B[Process]\n  B --> C[Output]\n```\n\n_Awaiting AI processing — will be replaced with a domain-specific system diagram._"}

---

## Technical manual

${meta.technicalManual ?? "_Awaiting AI processing — a dense, precise breakdown of internal mechanics, failure modes, and security boundaries._"}

---

## Interconnections

${meta.interconnections ?? "_Awaiting AI processing — maps connections to other concepts in the vault, suggesting links to existing notes._"}
`;

  return frontmatter + "\n" + body.trim() + "\n";
}

// ── Obsidian REST API helpers ──────────────────────────────────

function obsidianRequest(
  method: string,
  vaultPath: string,
  body?: string
): Promise<{ status: number; body: string }> {
  return new Promise((resolve, reject) => {
    const url = new URL(`/vault/${vaultPath}`, OBSIDIAN_API_BASE);
    const headers: Record<string, string> = {
      Authorization: `Bearer ${OBSIDIAN_API_KEY}`,
    };
    if (body !== undefined) {
      headers["Content-Type"] = "text/markdown";
    }

    const req = http.request(
      url,
      { method, headers },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => resolve({ status: res.statusCode ?? 0, body: data }));
      }
    );

    req.on("error", reject);
    if (body !== undefined) req.write(body);
    req.end();
  });
}

/**
 * Check if a citekey already exists in the vault under 20_Concepts/.
 * Reads all markdown files and searches YAML frontmatter.
 */
export function isDuplicate(citeKey: string): boolean {
  const conceptsDir = path.join(VAULT_PATH, "20_Concepts");
  if (!fs.existsSync(conceptsDir)) return false;

  const walkDir = (dir: string): string[] => {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    const files: string[] = [];
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        files.push(...walkDir(full));
      } else if (entry.name.endsWith(".md")) {
        files.push(full);
      }
    }
    return files;
  };

  const mdFiles = walkDir(conceptsDir);
  for (const file of mdFiles) {
    const content = fs.readFileSync(file, "utf-8");
    // Check YAML frontmatter for cite-key
    const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);
    if (fmMatch) {
      const fm = fmMatch[1];
      if (fm.includes(`cite-key: ${citeKey}`)) {
        return true;
      }
    }
  }

  return false;
}

// ── Pipeline ───────────────────────────────────────────────────

/**
 * Run the full research pipeline for a single PDF.
 *
 * Steps:
 *   1. Extract metadata from the PDF filename (basic heuristic).
 *   2. Check for duplicates via citekey scan.
 *   3. Route to the correct vault folder based on domain.
 *   4. Render the note template.
 *   5. Write to the Obsidian vault via the REST API.
 *
 * Note: In production, steps 1 and the AI-generated sections are
 * populated by the NotebookLM MCP tools (manage_source, query_notebook).
 * This function provides the scaffolding; the AI agent fills the content.
 */
export async function runPipeline(pdfPath: string): Promise<void> {
  const filename = path.basename(pdfPath, ".pdf");
  console.log(`\n━━━ Pipeline: ${filename} ━━━`);

  // Step 1: Build preliminary metadata from filename
  const citeKey = filename
    .replace(/^\d{8}T\d{6}Z_/, "")     // strip timestamp prefix from watcher
    .replace(/[^a-zA-Z0-9]/g, "-")
    .toLowerCase();

  // Step 2: Duplicate check
  if (isDuplicate(citeKey)) {
    console.log(`⏭  Duplicate detected (cite-key: ${citeKey}). Skipping.`);
    return;
  }

  // Step 3: Default domain — in production the AI classifies this
  const domain = "ai-data";
  const folder = routeToFolder(domain);
  console.log(`📂  Routing to: ${folder}`);

  // Step 4: Render note (placeholder sections — AI fills these later)
  const meta: NoteMetadata = {
    title: filename.replace(/[-_]/g, " "),
    citeKey,
    domain,
    authors: ["Unknown Author"],
    year: new Date().getFullYear().toString(),
    abstract: "_Abstract will be extracted from the PDF by the AI agent._",
    tags: [domain, "seedling"],
  };

  const markdown = renderNote(meta);

  // Step 5: Write to vault
  const vaultRelPath = `${folder}/${citeKey}.md`;
  console.log(`📝  Writing: ${vaultRelPath}`);

  try {
    const resp = await obsidianRequest("PUT", vaultRelPath, markdown);
    if (resp.status >= 200 && resp.status < 300) {
      console.log(`✅  Note created successfully.`);
    } else {
      console.error(`❌  Obsidian API returned ${resp.status}: ${resp.body}`);
      // Fallback: write directly to disk if API is unreachable
      const diskPath = path.join(VAULT_PATH, vaultRelPath);
      const diskDir = path.dirname(diskPath);
      if (!fs.existsSync(diskDir)) fs.mkdirSync(diskDir, { recursive: true });
      fs.writeFileSync(diskPath, markdown, "utf-8");
      console.log(`💾  Fallback: wrote directly to disk at ${diskPath}`);
    }
  } catch (err) {
    console.error(`❌  Obsidian API unreachable: ${err}`);
    // Fallback: write directly to disk
    const diskPath = path.join(VAULT_PATH, vaultRelPath);
    const diskDir = path.dirname(diskPath);
    if (!fs.existsSync(diskDir)) fs.mkdirSync(diskDir, { recursive: true });
    fs.writeFileSync(diskPath, markdown, "utf-8");
    console.log(`💾  Fallback: wrote directly to disk at ${diskPath}`);
  }
}

// ── CLI entrypoint ─────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);

  // --check-auth mode
  if (args.includes("--check-auth")) {
    const auth = checkNotebookLMAuth();
    console.log(auth.ok ? `✅  ${auth.message}` : `❌  ${auth.message}`);
    process.exit(auth.ok ? 0 : 1);
  }

  // Default: process all PDFs in staging/
  const stagingDir = path.resolve(__dirname, "..", "staging");
  if (!fs.existsSync(stagingDir)) {
    console.error(`Staging directory not found: ${stagingDir}`);
    process.exit(1);
  }

  const pdfs = fs.readdirSync(stagingDir).filter((f) => f.toLowerCase().endsWith(".pdf"));

  if (pdfs.length === 0) {
    console.log("No PDFs found in staging/. Nothing to process.");
    return;
  }

  console.log(`Found ${pdfs.length} PDF(s) in staging/.\n`);

  for (const pdf of pdfs) {
    await runPipeline(path.join(stagingDir, pdf));
  }

  console.log("\n━━━ Pipeline complete ━━━");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});