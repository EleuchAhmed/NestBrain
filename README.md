# Research Pipeline — Zotero → NotebookLM → Obsidian

> Automated research-to-notes pipeline. Saves a paper in Zotero,
> gets a structured atomic note in Obsidian. Fully local-first.

## How it works

The full flow begins when the Zotero Connector saves a PDF to your local library. A Python watcher daemon detects this new file and copies it to a staging folder. A Node.js pipeline agent then picks it up, using MCP tools to fetch metadata from Zotero and ground its analysis in NotebookLM. Finally, Gemini generates a 5-part structured note, which is automatically pushed into your Obsidian Vault via the local REST API.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    HOST MACHINE                             │
│                                                             │
│   Zotero (port 23119)          Obsidian (port 27123)        │
│        │                              ▲                     │
│        │ Zotero storage/              │ REST API            │
│        ▼                              │                     │
│ ┌──────────────────────────────────────────────────────┐   │
│ │              DOCKER COMPOSE                          │   │
│ │                                                      │   │
│ │  ┌─────────────┐   staging/   ┌──────────────────┐  │   │
│ │  │   watcher   │ ──────────► │    pipeline      │  │   │
│ │  │  (Python)   │              │   (Node.js)      │  │   │
│ │  └─────────────┘              │  Gemini via MCP  │  │   │
│ │                               └──────────────────┘  │   │
│ └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

Before cloning this repo, install these on your HOST machine:

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| Docker Desktop | Latest | Container runtime | docker.com/get-started |
| Zotero 7 | 7.x | Reference manager | zotero.org |
| Better BibTeX | Latest | Cite-key generation | retorque.re/zotero-better-bibtex |
| Obsidian | Latest | Knowledge vault | obsidian.md |
| Obsidian Local REST API | Latest | Vault write API | Community plugins |
| AntiGravity IDE | Latest | Agent runner | antigravity-ide.com |
| uv | Latest | Python pkg manager | astral.sh/uv |

## One-Time Setup (Do This Once)

### 1. Clone and configure

```bash
git clone <your-repo-url> ~/research-pipeline
cd ~/research-pipeline
cp .env.example .env   # then fill in your values
```

### 2. Fill in .env

Open .env in any editor. Fill in every value:

```text
OBSIDIAN_VAULT_PATH      → Absolute path to your Obsidian vault folder
OBSIDIAN_API_KEY         → From Obsidian Settings → Local REST API
ZOTERO_API_KEY           → From zotero.org/settings/keys
ZOTERO_LIBRARY_ID        → The "userID" from that same page
ZOTERO_STORAGE_PATH      → Path to your Zotero/storage folder:
                           Mac/Linux: ~/Zotero/storage
                           Windows:   C:\Users\YOU\Zotero\storage
```

### 3. Configure Zotero

1. Open Zotero
2. Edit → Settings → Advanced → check "Allow other applications to communicate with Zotero"
3. Edit → Settings → Better BibTeX → Citation Keys
   Set formula: `[auth:lower][year][veryshorttitle:lower]`
4. File → Export Library → Better BibTeX
   Tick "Keep updated" → save as `~/research-pipeline/library.bib`

### 4. Configure Obsidian

1. Open your vault in Obsidian
2. Settings → Community Plugins → disable Safe Mode
3. Browse → install "Local REST API" → enable it
4. Settings → Local REST API → copy the API key into `.env`

Create the folder structure (or run this in Git Bash / WSL / Mac / Linux terminal):

```bash
mkdir -p ~/ObsidianVault/{00_Inbox,10_Maps,20_Concepts/{Fullstack,Cyber,AI-Data,General-Arch},30_Workflows,90_Assets}
```

### 5. Set up MCP servers (run once on host)

```bash
uv tool install "git+https://github.com/54yyyu/zotero-mcp.git"
zotero-mcp setup
zotero-mcp update-db --fulltext

uv tool install notebooklm-mcp-cli
nlm login
# A browser window opens → log into your Google account → done
```

### 6. Register MCP servers in AntiGravity

In AntiGravity: Agent pane → MCP Servers → Manage → paste:

```json
{
  "mcpServers": {
    "zotero": {
      "command": "zotero-mcp",
      "env": {
        "ZOTERO_LOCAL": "true",
        "ZOTERO_API_KEY": "your-key",
        "ZOTERO_LIBRARY_ID": "your-id"
      }
    },
    "notebooklm": {
      "command": "notebooklm-mcp"
    }
  }
}
```

### 7. Build the Docker containers (first time only)

```bash
cd ~/research-pipeline
docker compose build
```

## Daily Execution (Every Research Session)

### Step 1 — Open required desktop apps

- Open Zotero (must be running for its local API on port 23119)
- Open Obsidian (must be running for REST API on port 27123)
- Open AntiGravity and load `~/research-pipeline/`

### Step 2 — Start the Docker services

```bash
cd ~/research-pipeline
docker compose up -d
```

Verify both containers are healthy:
```bash
docker compose ps
```

Expected output:
```text
NAME                  STATUS          PORTS
pipeline-watcher-1    running (healthy)
pipeline-pipeline-1   running (healthy)
```

### Step 3 — Save a paper in Zotero

Use the Zotero Connector browser extension to save any paper.
The PDF will be automatically downloaded by Zotero.
The watcher container detects it within ~2 seconds and copies
the PDF to `./staging/{cite-key}.pdf`

Confirm it arrived:
```bash
ls ./staging/
```

### Step 4 — Trigger the research agent in AntiGravity

Switch model to: `Gemini 3.1 Pro (High)`
Switch mode to: `Planning`

Paste this prompt:

---
A new PDF has arrived in `./staging/`. Run the full research pipeline:

1. Use `@mcp:zotero` to get the metadata and cite-key for the latest Zotero item
2. Check if a note with that cite-key already exists in the vault by scanning `20_Concepts/**/*.md` frontmatter
3. If it exists: stop and tell me the path. Do not duplicate.
4. If it does not exist:
   a. Use `@mcp:notebooklm` to create a notebook named `{cite-key}`,
      upload the PDF from `./staging/{cite-key}.pdf` as a source,
      and extract a structured JSON summary using this prompt:
      "Return ONLY a JSON object with keys: title, core_concept,
       why_fullstack, why_cyber, why_ai, technical_deep_dive,
       gotchas (array), code_language, code_snippet,
       mermaid_diagram (flowchart LR or sequenceDiagram only,
       max 10 nodes, no subgraph nesting)"
   b. Use that JSON to write an Obsidian note in this exact format:
      ---
      title: "{title}"
      cite-key: {cite-key}
      zotero-link: zotero://select/items/@{cite-key}
      tags:
        - {primary domain: fullstack|cyber|ai-data|architecture}
      date: {today YYYY-MM-DD}
      status: review
      ---

      ## The analogy
      {non-technical metaphor paragraph}

      ## Why it matters
      **Fullstack:** {why_fullstack}
      **Cyber:** {why_cyber}
      **AI / Data:** {why_ai}

      ## Architecture diagram
      ```mermaid
      {mermaid_diagram}
      ```

      ## Technical manual
      {technical_deep_dive}

      ### Code example
      ```{code_language}
      {code_snippet}
      ```

      ### Gotchas & security
      {gotchas as bullet list}

      ## Interconnections
      [[RelatedConcept1]]  ·  [[RelatedConcept2]]  ·  [[RelatedConcept3]]

      ---
      *Source: [[90_Assets/{cite-key}.pdf]]*

   c. Route the note to the correct Obsidian subfolder:
      `fullstack`    → `20_Concepts/Fullstack/{cite-key}.md`
      `cyber`        → `20_Concepts/Cyber/{cite-key}.md`
      `ai-data`      → `20_Concepts/AI-Data/{cite-key}.md`
      `architecture` → `20_Concepts/General-Arch/{cite-key}.md`
      `unknown`      → `00_Inbox/{cite-key}.md`

   d. Push it via the Obsidian REST API:
      `curl -X PUT -H "Authorization: Bearer $OBSIDIAN_API_KEY" -H "Content-Type: text/markdown" --data-binary @- http://localhost:27123/vault/{vault_path} <<< "{note_content}"`

5. Confirm the note exists in Obsidian and print its vault path.
---

### Step 5 — Stop Docker when done

```bash
docker compose down
```

## Troubleshooting

### "watcher container exits immediately"
Check that `ZOTERO_STORAGE_PATH` in `.env` points to a real directory:
```bash
ls $ZOTERO_STORAGE_PATH
```
If it's wrong, update `.env` and rebuild: `docker compose up -d --build`

### "pipeline can't reach Obsidian (Connection refused)"
Obsidian must be open on the host. The REST API only runs when Obsidian is running. Open Obsidian and retry:
```bash
docker compose restart pipeline
```

### "pipeline can't reach Zotero (Connection refused)"
Zotero must be open with local API enabled.
Edit → Settings → Advanced → check "Allow other applications..."
Then: `docker compose restart pipeline`

### "nlm login session expired" (NotebookLM auth fails)
Sessions last ~20 minutes. Re-authenticate on the host:
```bash
nlm login
```
The container mounts `~/.notebooklm-mcp` read-only, so it picks up the new auth immediately — no restart needed.

### "No PDF in staging after saving in Zotero"
1. Confirm the paper has a PDF attached in Zotero (not just metadata)
2. Check watcher logs: `docker compose logs watcher --tail=20`
3. Verify `ZOTERO_STORAGE_PATH` is correct in `.env`

### Linux only: "host.docker.internal not resolving"
The `docker-compose.yml` already includes `extra_hosts` for Linux.
If still failing, get the Docker bridge IP manually:
```bash
ip route | awk '/docker0/ {print $9}'
```
Then set it in `.env`: `OBSIDIAN_HOST=172.17.0.1`

## File Structure

```text
research-pipeline/
├── agents/
│   └── pipeline.ts          # Pipeline orchestration logic
├── scripts/
│   └── watcher.py           # Zotero storage file watcher
├── staging/                 # PDF handoff point (gitignored)
├── Dockerfile.watcher       # Python watcher container
├── Dockerfile.pipeline      # Node.js pipeline container
├── docker-compose.yml       # Orchestrates both services
├── .env                     # Your secrets (gitignored)
├── .env.example             # Template (committed to git)
├── .dockerignore            # Keeps secrets out of images
├── .gitignore
└── README.md                # This file
```

## Security Notes

- `.env` is never baked into Docker images (`.dockerignore` enforces this)
- Zotero storage is mounted READ-ONLY in the watcher container
- NotebookLM auth (`~/.notebooklm-mcp`) is mounted READ-ONLY
- Obsidian vault is mounted READ-WRITE only to services that produce notes

## Docker Profiles (Updated)

The repository now supports full containerized execution for the pipeline stack and an optional containerized Nestbrain desktop profile.

### Core pipeline (default)

Starts watcher + ollama + ollama-init + pipeline:

```bash
docker compose up -d
```

### Nestbrain desktop profile (optional)

Build and run Nestbrain in Docker (requires host display support such as X server/WSLg):

```bash
docker compose --profile desktop up -d nestbrain
```

#### Windows host display bridge (VcXsrv)

1. Install VcXsrv on Windows.
2. Start the X server with the helper script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_vcxsrv.ps1
```

3. Ensure these `.env` values are set:

```text
DISPLAY=host.docker.internal:0.0
QT_QPA_PLATFORM=xcb
```

4. Start desktop profile:

```bash
docker compose --profile desktop up -d nestbrain
```

If the GUI does not open, check logs:

```bash
docker compose --profile desktop logs nestbrain --tail=120
```

### Required environment variables for full dockerized runtime

- `ZOTERO_DATA_DIR` (host path containing both `storage/` and `zotero.sqlite`)
- `NOTEBOOKLM_MCP_PATH` (host path to `.notebooklm-mcp` auth cache)
- `OBSIDIAN_VAULT_PATH` (host path to vault)
- `DISPLAY` (only when using Nestbrain desktop profile)
