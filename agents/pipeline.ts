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
 *   OBSIDIAN_VAULT_PATH, OBSIDIAN_API_KEY, GEMINI_API_KEY
 */

import * as fs from "node:fs";
import * as path from "node:path";
import * as http from "node:http";
import { fileURLToPath } from "node:url";
import { config } from "dotenv";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { GoogleGenerativeAI } from "@google/generative-ai";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Load environment ───────────────────────────────────────────

config({ path: path.resolve(__dirname, "..", ".env") });

const VAULT_PATH: string = process.env.OBSIDIAN_VAULT_PATH ?? "";
const OBSIDIAN_API_KEY: string = process.env.OBSIDIAN_API_KEY ?? "";
const OBSIDIAN_API_BASE = `http://${process.env.OBSIDIAN_HOST ?? "localhost"}:27123`;

let mcpClient: Client | null = null;
async function getMcpClient(): Promise<Client> {
  if (mcpClient) return mcpClient;
  const transport = new StdioClientTransport({
    command: process.platform === "win32" ? "node.exe" : "node",
    args: [path.resolve(__dirname, "..", "antigravity-notebooklm-mcp", "build", "index.js")]
  });
  mcpClient = new Client({ name: "research-pipeline", version: "1.0.0" }, { capabilities: {} });
  await mcpClient.connect(transport);
  return mcpClient;
}

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY ?? "");
const geminiModel = genAI.getGenerativeModel({ model: "gemini-2.0-flash" });

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
export function routeToFolder(domain: string, title: string = ""): string {
  const key = domain.toLowerCase().trim();
  if (FOLDER_ROUTES[key]) {
    return FOLDER_ROUTES[key];
  }

  const titleLower = title.toLowerCase();
  for (const [routeKey, folder] of Object.entries(FOLDER_ROUTES)) {
    if (titleLower.includes(routeKey)) {
      return folder;
    }
  }

  return "00_Inbox";
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

export function checkNotebookLMAuth(): { ok: boolean; message: string } {
  const home = process.env.HOME ?? process.env.USERPROFILE ?? "";
  const resolvedPath = path.join(home, ".notebooklm-mcp", "auth.json");
  if (!fs.existsSync(resolvedPath)) {
    return { ok: false, message: `NotebookLM auth file NOT FOUND at: ${resolvedPath}. Run authenticate.bat first.` };
  }
  console.log(`[pipeline] Checking auth at: ${resolvedPath}`);

  try {
    const raw = fs.readFileSync(resolvedPath, "utf-8");
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
export function renderNote(
  slug: string,
  meta: NoteMetadata,
  generated: any,
  collectionName: string = "",
  sourceCount: number = 1
): string {
  const frontmatter = [
    "---",
    `title: "${generated.subject_title ? generated.subject_title.replace(/"/g, '\\"') : meta.title.replace(/"/g, '\\"')}"`,
    `cite-key: ${meta.citeKey}`,
    `slug: ${slug}`,
    `collection: "${collectionName}"`,
    `source-count: ${sourceCount}`,
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
# ${generated.subject_title ? generated.subject_title : meta.title}

> **Authors**: ${meta.authors.join(", ")}
> **Year**: ${meta.year}
> **Cite-key**: \`${meta.citeKey}\`

## Abstract

${meta.abstract}

---

## The analogy

${generated.analogy ?? meta.analogy ?? "_Awaiting AI processing — the pipeline will populate this section with an intuitive analogy that maps the paper's core mechanism to an everyday concept._"}

---

## Why it matters

${generated.whyItMatters ?? meta.whyItMatters ?? "_Awaiting AI processing — explains the real-world impact, what breaks without this, and why an engineer should care._"}

---

## Architecture diagram

${generated.architectureDiagram ?? meta.architectureDiagram ?? "\`\`\`mermaid\nflowchart LR\n  A[Input] --> B[Process]\n  B --> C[Output]\n\`\`\`\n\n_Awaiting AI processing — will be replaced with a domain-specific system diagram._"}

---

## Technical manual

${generated.technicalManual ?? meta.technicalManual ?? "_Awaiting AI processing — a dense, precise breakdown of internal mechanics, failure modes, and security boundaries._"}

---

## Sources processed

${collectionName ? "_Awaiting AI processing — will be populated by the agent with processed sources._" : "- `" + meta.citeKey + "`"}

---

## Interconnections

${generated.interconnections ?? meta.interconnections ?? "_Awaiting AI processing — maps connections to other concepts in the vault, suggesting links to existing notes._"}
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

// ── Helpers & Classifiers ──────────────────────────────────────

export function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9- ]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

export function collectionNoteExists(subjectTitle: string): string | false {
  const slug = slugify(subjectTitle);
  const pathsToCheck = [
    path.join(VAULT_PATH, "20_Concepts", "Fullstack", `${slug}.md`),
    path.join(VAULT_PATH, "20_Concepts", "Cyber", `${slug}.md`),
    path.join(VAULT_PATH, "20_Concepts", "AI-Data", `${slug}.md`),
    path.join(VAULT_PATH, "20_Concepts", "General-Arch", `${slug}.md`),
    path.join(VAULT_PATH, "00_Inbox", `${slug}.md`),
  ];
  for (const p of pathsToCheck) {
    if (fs.existsSync(p)) return p;
  }
  return false;
}

export function classifySource(item: any): string {
  if (item.pdfPath && fs.existsSync(item.pdfPath)) {
    return "pdf";
  }
  const url = item.url || "";
  if (url.includes("youtube.com") || url.includes("youtu.be")) {
    return "youtube";
  }
  return "url";
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
export async function runPipeline(pdfPath: string, collectionName?: string): Promise<void> {
  const filename = path.basename(pdfPath, ".pdf");
  console.log(`\n━━━ Pipeline: ${filename} ━━━`);

  // Step 1: Build preliminary metadata from filename
  const cite_key = filename
    .replace(/^\d{8}T\d{6}Z_/, "")     // strip timestamp prefix from watcher
    .replace(/[^a-zA-Z0-9]/g, "-")
    .toLowerCase();

  // If single-item mode, check for citeKey duplication
  if (!collectionName && isDuplicate(cite_key)) {
    console.log(`⏭  Duplicate detected (cite-key: ${cite_key}). Skipping.`);
    return;
  }

  // Call NotebookLM MCP tools to analyze the source via manage_source & query_notebook
  let generated: any;
  try {
    const notebookId = collectionName || "default-synthesis";
    const ext = path.extname(pdfPath).toLowerCase();
    let content: string;
    
    if (ext === ".html") {
      const rawHtml = fs.readFileSync(pdfPath, "utf8");
      // Simple tag stripping for NotebookLM
      content = rawHtml.replace(/<[^>]*>?/gm, ' ').replace(/\s+/g, ' ').trim();
    } else {
      // For PDF, we'll try to send as base64 but warn that NotebookLM might need raw text
      content = fs.readFileSync(pdfPath, "base64");
      console.log(`⚠️  Warning: Sending binary PDF as text to NotebookLM. If synthesis is poor, consider converting to text first.`);
    }
    
    const mcp = await getMcpClient();
    console.log(`🔌 Adding source to NotebookLM (ID: ${notebookId})...`);
    await mcp.callTool({
      name: "manage_source",
      arguments: {
        action: "add",
        notebook_id: notebookId,
        type: "text",
        content: content,
        title: filename
      }
    });

    console.log(`📥 Querying NotebookLM for synthesis...`);
    const queryResult = await mcp.callTool({
      name: "query_notebook",
      arguments: {
        notebook_id: notebookId,
        query: "Provide a comprehensive technical synthesis of this document, including core mechanics, analogies, real-world impact, architecture, and interconnections."
      }
    });
    const notebookLmOutput = (queryResult.content as any)[0].text;

    console.log(`🧠 Refining synthesis with Gemini Flash...`);
    const prompt = `
Extract and structure the following NotebookLM synthesis into a JSON object. Ensure it uses the following required schema exactly.

{
  "subject_title": "A short, descriptive title",
  "analogy": "An intuitive analogy mapping the core mechanism",
  "whyItMatters": "Explanation of real-world impact and what breaks without this",
  "architectureDiagram": "A valid mermaid.js diagram starting with \`\`\`mermaid",
  "technicalManual": "A dense, precise breakdown of internal mechanics, failure modes, and security boundaries",
  "interconnections": "Connections to other concepts"
}

NotebookLM Synthesis:
${notebookLmOutput}

Return ONLY valid JSON. Avoid any markdown code block fences entirely, just raw JSON. Escape nested quotes. Use concise language.
`;
    // Add retry for Gemini to handle 429s from free tier
    let result: any;
    let retries = 3;
    while (retries > 0) {
      try {
        result = await geminiModel.generateContent(prompt);
        break;
      } catch (gemError: any) {
        if (gemError.message.includes("429") && retries > 1) {
          console.warn(`⚠️  Gemini 429 (Too Many Requests). Retrying in 10s...`);
          await new Promise(r => setTimeout(r, 10000));
          retries--;
        } else {
          throw gemError;
        }
      }
    }
    const textResp = result.response.text();
    const cleanJson = textResp.replace(/```(?:json)?\n?|```/gi, "").trim();
    generated = JSON.parse(cleanJson);
  } catch (err: any) {
    console.error(`❌ Error in AI generation for ${filename}:`, err.message);
    return; // Exit early to avoid writing a broken note
  }

  const slug = collectionName ? slugify(generated.subject_title) : cite_key;

  if (collectionName) {
    const existingPath = collectionNoteExists(generated.subject_title);
    if (existingPath) {
      console.log(`Already exists at ${existingPath}`);
      return; 
    }
  }

  // Save raw response as audit trail
  const auditPath = path.join(__dirname, "..", "staging", `${slug}-notebooklm-response.json`);
  fs.writeFileSync(auditPath, JSON.stringify(generated, null, 2), "utf8");
  console.log(`[pipeline] Audit saved: ${auditPath}`);

  // Step 3: Default domain — in production the AI classifies this
  const domain = "ai-data";
  const folder = routeToFolder(domain, generated.subject_title);
  console.log(`📂  Routing to: ${folder}`);

  // Step 4: Render note
  const meta: NoteMetadata = {
    title: generated.subject_title,
    citeKey: cite_key,
    domain,
    authors: ["Unknown Author"],
    year: new Date().getFullYear().toString(),
    abstract: "_Abstract will be extracted from the PDF by the AI agent._",
    tags: [domain, "seedling"],
  };

  const sourceCount = collectionName ? 3 : 1; // Assuming 3 for mock collections
  const markdown = renderNote(slug, meta, generated, collectionName || "", sourceCount);

  // Step 5: Write to vault
  const vaultRelPath = `${folder}/${slug}.md`;
  console.log(`📝  Writing: ${vaultRelPath}`);

  try {
    const resp = await obsidianRequest("PUT", vaultRelPath, markdown);
    if (resp.status >= 200 && resp.status < 300) {
      console.log(`✅  Note created successfully.`);
    } else {
      console.error(`❌  Obsidian API returned ${resp.status}: ${resp.body}`);
      const diskPath = path.join(VAULT_PATH, vaultRelPath);
      const diskDir = path.dirname(diskPath);
      if (!fs.existsSync(diskDir)) fs.mkdirSync(diskDir, { recursive: true });
      fs.writeFileSync(diskPath, markdown, "utf-8");
      console.log(`💾  Fallback: wrote directly to disk at ${diskPath}`);
    }
  } catch (err) {
    console.error(`❌  Obsidian API unreachable: ${err}`);
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

  const collectionIdx = args.indexOf("--collection");
  let collectionName = collectionIdx !== -1 ? args[collectionIdx + 1] : process.env.COLLECTION_NAME;

  if (!collectionName) {
    console.error("❌  Error: Collection synthesis is the standard choice. You MUST provide a collection name.");
    console.error("Usage: npx tsx agents/pipeline.ts --collection \"Your Collection Name\" OR set COLLECTION_NAME env var.");
    process.exit(1);
  }
  if (collectionName.startsWith("--")) {
     console.error("❌  Error: Invalid collection name provided.");
     process.exit(1);
  }

  // Default: process all PDFs in staging/
  const stagingDir = path.resolve(__dirname, "..", "staging");
  if (!fs.existsSync(stagingDir)) {
    console.error(`Staging directory not found: ${stagingDir}`);
    process.exit(1);
  }

  const sources = fs.readdirSync(stagingDir).filter((f) => {
    const low = f.toLowerCase();
    return low.endsWith(".pdf") || low.endsWith(".html");
  });

  if (sources.length === 0) {
    console.log("No sources (.pdf or .html) found in staging/. Nothing to process.");
    return;
  }

  console.log(`Found ${sources.length} source(s) in staging/.\n`);

  for (const source of sources) {
    await runPipeline(path.join(stagingDir, source), collectionName);
  }

  console.log("\n━━━ Pipeline complete ━━━");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});