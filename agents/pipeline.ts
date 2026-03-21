/**
 * Research Pipeline Agent
 * =======================
 * Orchestrates the Zotero → NotebookLM → Obsidian research pipeline.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import * as http from "node:http";
import { fileURLToPath } from "node:url";
import { config } from "dotenv";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import * as cheerio from "cheerio";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Load environment ───────────────────────────────────────────

config({ path: path.resolve(__dirname, "..", ".env") });

const VAULT_PATH: string = process.env.OBSIDIAN_VAULT_PATH ?? "";
const OBSIDIAN_API_KEY: string = process.env.OBSIDIAN_API_KEY ?? "";
const OBSIDIAN_API_BASE = `http://${process.env.OBSIDIAN_HOST ?? "localhost"}:27123`;
const OLLAMA_HOST: string = process.env.OLLAMA_HOST ?? "http://localhost:11434";

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

// ── Folder routing ─────────────────────────────────────────────

const FOLDER_ROUTES: Record<string, string> = {
  fullstack: "20_Concepts/Fullstack",
  cyber: "20_Concepts/Cyber",
  "ai-data": "20_Concepts/AI-Data",
  architecture: "20_Concepts/General-Arch",
};

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

// ── Helpers ────────────────────────────────────────────────────

function ollamaRequest(endpoint: string, payload?: any): Promise<any> {
  return new Promise((resolve, reject) => {
    const url = new URL(endpoint, OLLAMA_HOST);
    const options: http.RequestOptions = {
      method: payload ? "POST" : "GET",
      headers: payload ? { "Content-Type": "application/json" } : {}
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

// ── Note rendering ─────────────────────────────────────────────

export interface NoteMetadata {
  title: string;
  citeKey: string;
  domain: string;
  tags: string[];
  status: string;
}

export function renderNote(
  slug: string,
  meta: NoteMetadata,
  generatedMarkdown: string,
  audioPath: string | null,
  videoPath: string | null,
  audioUrl: string | null,
  videoUrl: string | null,
  rawSourceRef: string
): string {
  const frontmatter = [
    "---",
    `title: "${meta.title.replace(/"/g, '\\"')}"`,
    `tags:`,
    ...meta.tags.map((t) => `  - ${t}`),
    `source_type: "${meta.domain}"`,
    `date_added: ${new Date().toISOString().split("T")[0]}`,
    `status: ${meta.status}`,
    `audio_overview: ${audioPath ? `"${audioPath}"` : "null"}`,
    `summary_video: ${videoPath ? `"${videoPath}"` : "null"}`,
    "---",
  ].join("\n");

  const mediaSection = [
    "## Media",
    audioPath ? `![[${path.basename(audioPath)}]]` : (audioUrl ? `[Audio Overview](${audioUrl})` : "_No audio overview available._"),
    videoPath ? `![[${path.basename(videoPath)}]]` : (videoUrl ? `[Summary Video](${videoUrl})` : "_No summary video available._"),
    audioUrl ? `> Original Audio: ${audioUrl}` : "",
    videoUrl ? `> Original Video: ${videoUrl}` : "",
    "> **generated_by: NotebookLM**",
  ].filter(s => s !== "").join("\n\n");

  const footer = `\n\n## Raw Source Reference\n\n${rawSourceRef}`;

  return frontmatter + "\n\n" + mediaSection + "\n\n" + generatedMarkdown.trim() + footer + "\n";
}

// ── Pipeline ───────────────────────────────────────────────────

export async function runCollectionPipeline(collectionName: string, stagingDir: string): Promise<void> {
  const sources = fs.readdirSync(stagingDir).filter((f) => {
    const low = f.toLowerCase();
    return low.endsWith(".pdf") || low.endsWith(".html") || low.endsWith(".link") || low.endsWith(".txt");
  });

  if (sources.length === 0) {
    console.log("No sources found in staging/. Nothing to process.");
    return;
  }

  const mcp = await getMcpClient();
  const notebookId = collectionName; 

  console.log(`\n━━━ Ingesting ${sources.length} sources into ${notebookId} ━━━`);
  let successfulIngests = 0;
  let rawSourceRefs: string[] = [];

  // Step 1: Ingest Sources
  for (const source of sources) {
    const filePath = path.join(stagingDir, source);
    try {
      const ext = path.extname(filePath).toLowerCase();
      let content = "";
      let type: "text" | "url" | "drive" = "text";
      let ref = source;

      const rawFile = fs.readFileSync(filePath, "utf8");
      // YouTube pattern check
      const ytMatch = rawFile.match(/https?:\/\/(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/)[^\s"']+/i);

      if (ytMatch) {
        content = ytMatch[0];
        type = "url";
        ref = content;
      } else if (ext === ".html") {
        const $ = cheerio.load(rawFile);
        content = $.text().replace(/\s+/g, " ").trim();
        type = "text";
      } else if (ext === ".pdf") {
        content = fs.readFileSync(filePath, "base64");
        console.log(`⚠️ Warning: Sending binary PDF as base64 text...`);
      } else {
        content = rawFile.trim();
        type = "text";
      }

      console.log(`🔌 Adding ${source} (type: ${type})...`);
      const addResult = await mcp.callTool({
        name: "manage_source",
        arguments: { action: "add", notebook_id: notebookId, type: type, content: content, title: source }
      });
      const resData = JSON.parse((addResult.content as any)[0].text);
      if (resData.error) throw new Error(resData.error);
      
      console.log(`✅ Source added (ID: ${resData.source_id})`);
      successfulIngests++;
      rawSourceRefs.push(ref);
    } catch (err: any) {
      console.error(`❌ Skipped ${source} due to error: ${err.message}`);
    }
  }

  if (successfulIngests === 0) {
    console.error(`❌ Abort: Zero sources were successfully ingested.`);
    process.exit(1);
  }

  // Step 2: NotebookLM Query and Media Fetching
  console.log(`📥 Querying NotebookLM for full synthesis...`);
  const queryResult = await mcp.callTool({
    name: "query_notebook",
    arguments: { notebook_id: notebookId, query: "Provide a comprehensive and exhaustive technical synthesis of all sources in this notebook. Do not omit any details." }
  });
  const notebookLmOutput = (queryResult.content as any)[0].text;
  
  const slug = slugify(collectionName);
  
  async function generateAndPollMedia(mediaType: "audio" | "video"): Promise<{ path: string | null; url: string | null }> {
    let result = { path: null as string | null, url: null as string | null };
    try {
      console.log(`🎬 Requesting ${mediaType} artifact...`);
      await mcp.callTool({
        name: "generate_artifact",
        arguments: { notebook_id: notebookId, type: mediaType, config: {} }
      });
      
      console.log(`⏳ Polling ${mediaType} status...`);
      for (let i = 0; i < 60; i++) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        let listRes;
        try {
          listRes = await mcp.callTool({ name: "manage_studio", arguments: { action: "list", notebook_id: notebookId } });
        } catch(e) { continue; } // Handle potential network blips
        
        const listData = JSON.parse((listRes.content as any)[0].text);
        const item = listData.artifacts?.find((a: any) => 
          a.state === "COMPLETED" && a.type?.toLowerCase().includes(mediaType)
        );
        if (item && item.url) {
          result.url = item.url;
          console.log(`✅ ${mediaType} ready at ${item.url}`);
          const assetPathRel = `${slug}.${mediaType === 'audio' ? 'mp3' : 'mp4'}`;
          const assetPathAbs = path.join(VAULT_PATH, "assets", assetPathRel);
          
          try {
             const fRes = await fetch(item.url);
             if (!fRes.ok) throw new Error(`Fetch failed: ${fRes.status}`);
             const buf = await fRes.arrayBuffer();
             fs.writeFileSync(assetPathAbs, Buffer.from(buf));
             result.path = `assets/${assetPathRel}`;
             return result;
          } catch(e) {
             console.error(`Failed to download ${mediaType}:`, e);
             return result; // return url at least
          }
        }
      }
      console.warn(`⚠️ Timeout waiting for ${mediaType}`);
    } catch (e: any) {
      console.warn(`⚠️ Skipping ${mediaType} generation gracefully: ${e.message}`);
    }
    return result;
  }

  const audioAsset = await generateAndPollMedia("audio");
  const videoAsset = await generateAndPollMedia("video");

  // Step 3 & 5: DeepSeek Synthesis and Validation
  const ollamaPromptBase = `You are a rigorous academic research assistant. You will receive a full synthesis of a source produced by NotebookLM. Your job is to produce a dense, detailed literature review note. You must never generalize, never produce filler sentences, and never skip details. Every sentence must carry information extracted directly from the source. Structure your response in exactly this order:

## Summary
Identify the central thesis or main argument of the source in one precise sentence. Follow it with a dense 3 to 5 sentence synthesis of the source written in academic register.

## Key Concepts
Extract every key concept mentioned and define each one briefly and accurately as a markdown list.

## Methodology
Describe the methodology or reasoning structure the source uses to build its claims.

## Main Arguments
List every main finding or argument as a numbered item with its supporting evidence indented beneath it.

## Limitations & Gaps
Identify every limitation, gap, or unresolved question the source acknowledges or leaves open.

## Connections
Note connections to other fields, theories, or ideas referenced or implied by the source, using Obsidian [[wikilink]] format if possible.

Do not add introductions, conclusions, or transitional filler. Respond only with the structured content above.

Source Synthesis:
${notebookLmOutput}`;

  console.log(`🧠 Synthesizing with local Ollama deepseek-r1:14b...`);
  let isValid = false;
  let attempt = 1;
  let finalMarkdown = "";
  let currentPrompt = ollamaPromptBase;
  let status = "literature-review";

  while (attempt <= 2 && !isValid) {
    try {
      const resp = await ollamaRequest("/api/generate", {
        model: "deepseek-r1:14b",
        prompt: currentPrompt,
        stream: false,
        options: { temperature: 0.3, num_predict: 2000 }
      });

      let rawText = resp.response || "";
      finalMarkdown = rawText.replace(/<think>[\s\S]*?<\/think>\s*/gi, "").trim();

      const hasSummary = finalMarkdown.includes("## Summary");
      const hasConcepts = finalMarkdown.includes("## Key Concepts");
      const hasArgs = finalMarkdown.includes("## Main Arguments");

      if (hasSummary && hasConcepts && hasArgs) {
        isValid = true;
        console.log(`✅ Validation passed (Attempt ${attempt})`);
      } else {
        console.warn(`⚠️ Validation failed (Attempt ${attempt}). Missing required sections.`);
        if (attempt === 1) {
           currentPrompt = ollamaPromptBase + `\n\nCRITICAL FIX: Your previous output was missing required markdown headers. You MUST include exactly "## Summary", "## Key Concepts", and "## Main Arguments" headers in your response.`;
        }
      }
    } catch (e: any) {
      console.error(`❌ DeepSeek failed: ${e.message}`);
    }
    attempt++;
  }

  if (!isValid) {
    status = "incomplete";
    console.log("⚠️ Marking note as incomplete.");
  }

  // Step 4: Write Note
  const domain = "ai-data"; 
  const folder = routeToFolder(domain, collectionName);
  const meta: NoteMetadata = {
    title: collectionName,
    citeKey: slug,
    domain,
    tags: [domain],
    status
  };

  const rawRefText = rawSourceRefs.map(r => `- ${r}`).join("\n");
  const markdown = renderNote(slug, meta, finalMarkdown, audioAsset.path, videoAsset.path, audioAsset.url, videoAsset.url, rawRefText);

  const vaultRelPath = `${folder}/${slug}.md`;
  console.log(`📝 Writing Note: ${vaultRelPath}`);

  try {
    const diskPath = path.join(VAULT_PATH, vaultRelPath);
    const diskDir = path.dirname(diskPath);
    if (!fs.existsSync(diskDir)) fs.mkdirSync(diskDir, { recursive: true });
    fs.writeFileSync(diskPath, markdown, "utf-8");
    console.log(`✅ Note saved: ${diskPath}`);
  } catch (err) {
    console.error(`❌ Failed to write note: ${err}`);
  }
}

// ── CLI entrypoint ─────────────────────────────────────────────

async function main() {
  const args = process.argv.slice(2);
  
  // Ollama Healthcheck
  try {
    const tagsResp = await ollamaRequest("/api/tags");
    const hasDeepSeek = tagsResp.models?.some((m: any) => m.name.includes("deepseek-r1:14b"));
    if (!hasDeepSeek) {
      console.error(`Abort: Model deepseek-r1:14b not found. Please run: ollama pull deepseek-r1:14b`);
      process.exit(1);
    }
    console.log(`✅ Ollama health check passed.`);
  } catch (err: any) {
    console.error(`❌ Abort: Failed to reach Ollama at ${OLLAMA_HOST}: ${err.message}`);
    process.exit(1);
  }

  // Ensure assets folder exists at startup
  const assetsDir = path.join(VAULT_PATH, "assets");
  if (!fs.existsSync(assetsDir)) {
    console.log(`📁 Creating missing assets directory: ${assetsDir}`);
    fs.mkdirSync(assetsDir, { recursive: true });
  }

  const collectionIdx = args.indexOf("--collection");
  const collectionName = collectionIdx !== -1 ? args[collectionIdx + 1] : process.env.COLLECTION_NAME;

  if (!collectionName || collectionName.startsWith("--")) {
    console.error("❌ Error: You MUST provide a collection name.");
    process.exit(1);
  }

  const stagingDir = path.resolve(__dirname, "..", "staging");
  if (!fs.existsSync(stagingDir)) {
    console.error(`Staging directory not found: ${stagingDir}`);
    process.exit(1);
  }

  await runCollectionPipeline(collectionName, stagingDir);
  console.log("\n━━━ Pipeline complete ━━━");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});