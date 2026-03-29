import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import { config } from "dotenv";
import { spawn } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

config({ path: path.resolve(__dirname, "..", ".env") });

const VAULT_PATH: string = process.env.OBSIDIAN_VAULT_PATH ?? "";

const PDFS = [
    {
        title: "OpenAI Agents Guide",
        path: "C:\\Users\\Mega Pc\\Desktop\\research-pipeline\\staging\\20260319T033826Z_a-practical-guide-to-building-agents.pdf",
        obsidianPath: "20_Concepts/AI-Agents/openai-agents-guide.md"
    },
    {
        title: "Predibase Fine-Tuning Guide",
        path: "C:\\Users\\Mega Pc\\Desktop\\research-pipeline\\staging\\Predibase_Fine-Tuning_LLMs_ebook_.pdf",
        obsidianPath: "20_Concepts/AI-Data/predibase-finetuning.md"
    }
];

async function callNotebookLmPython(action: string, args: any): Promise<any> {
    const scriptPath = path.resolve(__dirname, "..", "scripts", "notebooklm_operations.py");
    const payload = JSON.stringify({ action, args });
    return new Promise((resolve, reject) => {
        const child = spawn("python", [scriptPath]);
        child.stdin.write(payload);
        child.stdin.end();
        let stdoutData = "";
        let stderrData = "";
        child.stdout.on("data", (data) => { stdoutData += data; });
        child.stderr.on("data", (data) => { stderrData += data; });
        child.on("close", (code) => {
            try {
                const firstBrace = stdoutData.indexOf("{");
                const lastBrace = stdoutData.lastIndexOf("}");
                if (firstBrace === -1) throw new Error("No JSON found");
                const data = JSON.parse(stdoutData.substring(firstBrace, lastBrace + 1));
                if (data.error) reject(new Error(data.error));
                else resolve(data);
            } catch (e: any) {
                reject(new Error(`Python Error: ${e.message}\nStderr: ${stderrData}`));
            }
        });
    });
}

async function processPdf(pdf: typeof PDFS[0]) {
    console.log(`--- Processing ${pdf.title} ---`);
    if (!fs.existsSync(pdf.path)) {
        console.error(`File missing: ${pdf.path}`);
        return;
    }

    console.log("📓 Creating Notebook...");
    const { notebookId } = await callNotebookLmPython("createNotebook", { title: pdf.title });
    
    console.log("🔌 Ingesting PDF...");
    await callNotebookLmPython("ingestFile", { notebookId, path: pdf.path });

    console.log("🧠 Grounded Synthesis (NotebookLM)...");
    const { answer } = await callNotebookLmPython("synthesize", { notebookId });

    console.log("🎬 Generating Media (this may take time)...");
    const videoData = await callNotebookLmPython("generateMedia", { notebookId, type: "video" });
    
    let videoEmbed = "";
    if (videoData.status === "success" && videoData.artifactId) {
        console.log("📥 Downloading Video...");
        const assetsDir = path.join(VAULT_PATH, "assets");
        if (!fs.existsSync(assetsDir)) fs.mkdirSync(assetsDir, { recursive: true });
        const slug = pdf.title.toLowerCase().replace(/[^a-z0-9]/g, "-");
        const outputPath = path.join(assetsDir, `${slug}-overview.mp4`);
        await callNotebookLmPython("downloadMedia", { 
            notebookId, 
            type: "video", 
            artifactId: videoData.artifactId,
            outputPath 
        });
        videoEmbed = `\n\n## 🎬 Video Overview\n![[assets/${path.basename(outputPath)}]]\n`;
    }

    const fullPath = path.join(VAULT_PATH, pdf.obsidianPath);
    os.makedirsSync(path.dirname(fullPath), { recursive: true });
    
    const finalNote = `---\ntags: [research, ai, automation]\nstatus: developing\n---\n\n# ${pdf.title}\n\n${videoEmbed}\n\n${answer}`;
    fs.writeFileSync(fullPath, finalNote, "utf-8");
    console.log(`✅ Note saved: ${fullPath}`);
}

const os = {
    makedirsSync: (dir: string, opts: any) => {
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, opts);
    }
}

async function main() {
    for (const pdf of PDFS) {
        try {
            await processPdf(pdf);
        } catch (e: any) {
            console.error(`Failed ${pdf.title}: ${e.message}`);
        }
    }
}

main();
