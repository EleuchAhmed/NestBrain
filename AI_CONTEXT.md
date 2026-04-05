# AI Context

## Project Summary
- Nestbrain Research Pipeline is a local research-to-knowledge system that turns Zotero sources into Obsidian notes.
- The current codebase contains two active subsystems:
  - A Python desktop application in `nestbrain/` that is the primary runtime path.
  - A TypeScript NotebookLM MCP server in `antigravity-notebooklm-mcp/` that is a separate companion toolchain.
- The system is designed to ingest Zotero collections, query NotebookLM, synthesize notes with NVIDIA NIM models, and write structured Markdown into an Obsidian vault.

## Main Goal
- Convert research sources into connected, durable knowledge artifacts.
- Preserve processing state per Zotero collection.
- Enrich the vault with semantic links, concept notes, and graph visualizations.

## Tech Stack
- Python 3.11+
- PyQt6 desktop UI
- requests for Zotero HTTP access
- watchdog for local vault change monitoring
- PyYAML for Obsidian frontmatter parsing
- networkx and matplotlib for graph visualization
- notebooklm-py for native NotebookLM access
- python-dotenv for environment loading
- NVIDIA NIM via an OpenAI-compatible client
- TypeScript and Node.js in the MCP server
- @modelcontextprotocol/sdk, axios, puppeteer-extra, zod
- Docker Compose and a Windows launcher layer

## High-Level Architecture
- The Python app is a GUI-driven orchestrator with background workers.
- The desktop UI lives in `nestbrain/ui/`.
- The orchestration layer lives in `nestbrain/core/`.
- Background work is isolated in `nestbrain/workers/`.
- Persistent runtime state is stored in files under the repo or the vault.
- The TypeScript MCP server is a separate NotebookLM control plane built around stdio tools and reverse-engineered RPC calls.

## Main Folders

### `nestbrain/`
- Primary Python application.
- Key responsibilities:
  - Desktop startup
  - Configuration loading and saving
  - Pipeline orchestration
  - Vault parsing and graph generation
  - Zotero synchronization
  - NotebookLM access and synthesis
- Key files:
  - `main.py` - application entry point
  - `config.json` - saved UI and pipeline settings
  - `pipeline-registry.json` - collection processing state
  - `core/pipeline_runner.py` - top-level pipeline driver
  - `core/v2_workflow.py` - active multi-stage workflow
  - `core/workflow.py` - legacy workflow path, currently unused by `pipeline_runner.py`

### `nestbrain/core/`
- Business logic, external service adapters, and note and graph processing.
- Key modules:
  - `zotero_sync.py` - Zotero API client and collection and item sync
  - `notebooklm_bridge.py` - native NotebookLM bridge using notebooklm-py
  - `ollama_client.py` - despite the name, this is an NVIDIA NIM and OpenAI-compatible client
  - `obsidian_parser.py` - scans Markdown notes in the vault
  - `knowledge_graph.py` - builds graph payloads for the UI
  - `note_renderer.py` - renders and merges Obsidian notes
  - `registry.py` - collection state persistence
  - `stages/` - decomposed pipeline steps used by `v2_workflow.py`

### `nestbrain/core/stages/`
- The active v2 pipeline is split into smaller responsibilities.
- Key files:
  - `notebooklm_stage.py` - create notebook, ingest sources, interrogate, generate media
  - `synthesis_stage.py` - combine NotebookLM output with NVIDIA model synthesis
  - `notewriter_stage.py` - write or merge notes into the vault
  - `question_planner.py` - generate a research taxonomy
  - `q_and_a_loop.py` - iterative question and answer loop
  - `master_synthesizer.py` - turn research history into a master note and enforce inline first-mention wikilinks
  - `entity_extractor.py` - extract scored IT entities and gate forwarding by confidence
  - `note_seeder.py` - semantic duplicate check against existing titles/aliases before creating new notes
  - `vector_indexer.py` - embed notes and find similar notes
  - `semantic_auditor.py` - rerank similar notes to reduce false positives
  - `connection_annotator.py` - append connection explanations to related notes

### `nestbrain/ui/`
- PyQt6 presentation layer.
- Key files:
  - `main_window.py` - main application window and wiring
  - `workspace.py` - central content area and views
  - `sidebar.py` - navigation panel
  - `zotero_panel.py` - Zotero collections and sync UI
  - `brain_map_view.py` - graph visualization

### `nestbrain/workers/`
- Threaded background execution for GUI responsiveness.
- Key files:
  - `pipeline_worker.py` - runs the pipeline in a worker thread
  - `sync_worker.py` - refreshes Zotero collection data
  - `graph_worker.py` - builds graph payloads off the UI thread

### `antigravity-notebooklm-mcp/`
- Separate Node.js and TypeScript MCP server for NotebookLM.
- It exposes router-style MCP tools over stdio.
- Key files:
  - `src/index.ts` - MCP server entry point and tool routing
  - `src/api-client.ts` - reverse-engineered NotebookLM web client
  - `src/orchestrator.ts` - deep research and artifact generation flows
  - `src/browser-auth.ts` - automated browser authentication helper
  - `src/auth-cli.ts` - manual auth helper
  - `src/verify-all.ts` and `src/verify-research.ts` - validation utilities
- `build/` is generated output, not source.

### `launcher/windows/`
- Windows startup entry points only.
- Key files:
  - `start-application.cmd`
  - `start-nestbrain-desktop.vbs`
  - `start-research-pipeline.vbs`
  - `start-notebooklm-authentication.bat`

### `scripts/`
- Legacy compatibility and packaging helpers.
- Key file:
  - `notebooklm_operations.py` - legacy wrapper around the NotebookLM bridge entrypoint
- `scripts/build/` and similar build output folders are generated artifacts.

### `docker/`
- Docker image definitions.
- Current repository state only shows `Dockerfile.nestbrain`.

### `docs/`
- Architecture and repository notes.
- Important for context, but some documents are stale relative to the current tree.

### `staging/`
- Transient NotebookLM response artifacts, HTML captures, and intermediate JSON files.
- Treat as generated data.

### `pipeline_logs/`
- Runtime logs.
- Treat as generated data.

## Key Modules And Roles
- `nestbrain/main.py` - loads config, opens the Qt app, launches `MainWindow`.
- `nestbrain/core/pipeline_runner.py` - validates vault settings, runs the workflow, archives run metadata.
- `nestbrain/core/v2_workflow.py` - active orchestration path for the current Python pipeline.
- `nestbrain/core/workflow.py` - earlier workflow decomposition; appears to be unused by the current runner.
- `nestbrain/core/notebooklm_bridge.py` - async bridge to NotebookLM using cached auth tokens.
- `nestbrain/core/zotero_sync.py` - fetches collections and items from Zotero and can create collections.
- `nestbrain/core/note_renderer.py` - creates the master Markdown note and merge updates.
- `nestbrain/core/knowledge_graph.py` - converts notes, references, and semantic links into a graph payload.
- `nestbrain/ui/main_window.py` - wires pipeline actions, Zotero sync, archive loading, and the brain map.
- `antigravity-notebooklm-mcp/src/index.ts` - routes MCP tools to NotebookLM client calls.

## Critical Flows

### Python Desktop Pipeline
1. User opens the app via `nestbrain.main` or a Windows launcher.
2. `MainWindow` loads config, starts Zotero sync, and renders the vault overview.
3. The user starts the pipeline from the UI.
4. `PipelineWorker` runs `PipelineRunner` in a background thread.
5. `PipelineRunner` validates the vault path and constructs service clients.
6. `PipelineWorkflowV2` executes the multi-stage pipeline.
7. Zotero collections and items are synced.
8. NotebookLM notebooks are created or reused.
9. Sources are ingested, interrogated, and synthesized.
10. Entity extraction emits `{entity, confidence, justification}` and only passes confidence >= 0.75.
11. Seeder duplicate decisions are logged to `seeder_log.json` and duplicate entities are linked to existing notes.
12. New entity notes are created only when no semantic duplicate exists.
13. Notes are written into the Obsidian vault.
14. Run metadata is saved to `nestbrain/runs/` and the registry is updated.

### UI Graph Flow
1. Vault notes are parsed by `ObsidianParser`.
2. `GraphWorker` builds graph data.
3. `BrainMapView` renders the graph in the UI.
4. Zotero sync updates the collection panel separately.

### NotebookLM MCP Flow
1. An MCP client connects to `antigravity-notebooklm-mcp/src/index.ts` over stdio.
2. The server loads auth tokens from `~/.notebooklm-mcp/auth.json` or environment variables.
3. Tool calls are routed to `NotebookLMClient` and `NotebookOrchestrator`.
4. The server can list notebooks, manage sources, query notebooks, run deep research, and create artifacts.

## External Integrations
- Zotero local API at `http://localhost:23119`.
- Zotero Web API when collection creation needs remote fallback.
- NotebookLM via notebooklm-py in Python and a direct web client in TypeScript.
- NVIDIA NIM at `https://integrate.api.nvidia.com/v1`.
- Obsidian vault as a filesystem-backed Markdown store.
- Docker Compose for containerized local runs.
- VcXsrv for Windows X11 rendering when using the desktop Docker profile.

## Known Limitations Or Missing Parts
- The repository contains stale documentation that references folders and wrappers that are not present in the current tree, including `automation/`, `agents/`, `src/`, `mcp-servers/`, and some root wrapper scripts. Mark these as UNKNOWN if encountered elsewhere.
- The current `docker-compose.yml` only defines the `nestbrain` desktop service; several docs describe a larger service set that is not in the file.
- `NotebookLMBridge` depends on `notebooklm-py`, but the internal auth and RPC behavior is largely opaque from this repo.
- The current v2 Python workflow is more complete than the older `workflow.py`, but both files exist.
- Some pipeline stages are partially implemented or asymmetrical, especially media generation and note enrichment.
- The brain map payload can be sparse depending on what the workflow returns.

## AI Agent Quick Start
- Start with `nestbrain/main.py`, `nestbrain/core/pipeline_runner.py`, and `nestbrain/core/v2_workflow.py`.
- Treat `nestbrain/` as the primary runtime and `antigravity-notebooklm-mcp/` as a separate companion service.
- Keep UI code in `nestbrain/ui/`, background work in `nestbrain/workers/`, and business logic in `nestbrain/core/`.
- Do not trust older docs blindly; verify current files before changing architecture.
- Preserve registry, vault path, and auth file conventions unless you are updating every consumer.
