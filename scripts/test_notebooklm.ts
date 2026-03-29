import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function test() {
    console.log("Testing NotebookLM MCP...");
    const transport = new StdioClientTransport({
        command: "node",
        args: [path.resolve(__dirname, "..", "antigravity-notebooklm-mcp", "build", "index.js")],
    });
    const client = new Client({ name: "test", version: "1.0.0" }, { capabilities: {} });
    await client.connect(transport);

    try {
        console.log("Calling manage_notebook (list)...");
        const result = await client.callTool({
            name: "manage_notebook",
            arguments: { action: "list" },
        });
        console.log("Result:", JSON.stringify(result, null, 2));
    } catch (err: any) {
        console.error("Tool call failed:", err.message);
    }
}

test().catch(console.error);
