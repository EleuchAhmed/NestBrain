# Architecture

## Architecture Style
- Hybrid local application architecture.
- Primary runtime: GUI desktop orchestrator with background worker threads.
- Persistence: filesystem-based state, Markdown vault files, JSON registry files, and generated artifact folders.
- Companion subsystem: a separate Node.js MCP server for direct NotebookLM control.
- The repository is not a microservice system in the current tree; it is a local app plus one companion server.

## Module Interaction Diagram

```text
User
  -> Windows launcher or python -m nestbrain.main
  -> PyQt6 MainWindow
  -> PipelineWorker / SyncWorker / GraphWorker
  -> PipelineRunner
  -> PipelineWorkflowV2
      -> ZoteroSyncClient
      -> NotebookLMBridge
      -> stage modules in nestbrain/core/stages/
      -> OllamaClient (NVIDIA NIM)
      -> ObsidianParser
      -> NoteSeeder / VectorIndexer / SemanticAuditor / ConnectionAnnotator
  -> Obsidian vault files + pipeline-registry.json + runs/

MCP client
  -> antigravity-notebooklm-mcp/src/index.ts
  -> NotebookLMClient
  -> NotebookLM web app RPCs
  -> NotebookLM auth cache at ~/.notebooklm-mcp/auth.json
```

## Data Flow

### Python Desktop Flow
1. Config is loaded from `nestbrain/config.json` and environment variables.
2. The UI reads the vault, Zotero status, and archive history.
3. When the user starts the pipeline, the worker thread invokes `PipelineRunner.run()`.
4. `PipelineRunner` validates the vault path and creates service clients.
5. `PipelineWorkflowV2` syncs Zotero collections and items.
6. For each collection, the workflow creates or reuses a NotebookLM notebook.
7. Source content is ingested into NotebookLM.
8. The question planner generates a taxonomy of research prompts.
9. The Q and A loop interrogates NotebookLM repeatedly.
10. The synthesizer turns the research history into a master note.
11. The synthesizer enforces inline first-mention wikilinks and removes trailing link-list sections.
12. Entity extraction returns scored technical entities and only forwards entries with confidence >= 0.75.
13. The seeder performs pre-seeding semantic duplicate research using existing note titles and aliases.
14. Duplicate entities are skipped, logged, and flagged as link overrides for the synthesizer.
15. Unmatched entities create new term notes; existing notes are not mutated during seeding.
16. The vector indexer embeds the note and stores local similarity state.
17. The semantic auditor filters candidate related notes.
18. The connection annotator appends semantic linkage text to related notes.
19. The note writer writes the final Markdown into the vault.
20. The pipeline runner archives summary metadata and the UI refreshes the graph.

### Graph Flow
1. `ObsidianParser` scans the vault for Markdown notes.
2. `KnowledgeGraphBuilder` converts notes, references, and semantic links into nodes and edges.
3. `BrainMapView` renders the graph using NetworkX and Matplotlib.

### MCP Flow
1. `src/index.ts` initializes the MCP server over stdio.
2. Auth tokens are loaded from local cache or environment variables.
3. Tool requests are normalized into router-style actions.
4. `NotebookLMClient` handles low-level RPC request construction and parsing.
5. `NotebookOrchestrator` handles multi-step research and artifact workflows.

## Entry Points
- `nestbrain/main.py` - Python GUI entry point.
- `launcher/windows/start-application.cmd` - Windows launcher wrapper for the GUI.
- `launcher/windows/start-nestbrain-desktop.vbs` - Windows launcher that starts the Python app from `.venv`.
- `launcher/windows/start-research-pipeline.vbs` - Windows launcher that starts VcXsrv and Docker Compose desktop profile.
- `antigravity-notebooklm-mcp/src/index.ts` - MCP server entry point.
- `antigravity-notebooklm-mcp/src/browser-auth.ts` - browser-based authentication CLI.
- `antigravity-notebooklm-mcp/src/auth-cli.ts` - manual token entry CLI.

## External Integrations
- Zotero local API and Web API.
- NotebookLM native client library in Python.
- NotebookLM web RPCs in TypeScript.
- NVIDIA NIM chat/completions, embeddings, and ranking endpoints.
- Obsidian vault filesystem.
- Docker and VcXsrv for Windows GUI container support.

## Current Constraints
- The current `docker-compose.yml` only defines the `nestbrain` desktop service.
- Several repository docs mention additional services and directories that are not present in the current tree.
- The active Python workflow is `v2_workflow.py`; `workflow.py` remains in the tree but is not the path used by `PipelineRunner`.
- `notebooklm_stage.py` currently handles video generation only; audio is not part of the active stage implementation.

## Subsystem Notes

### Python Desktop App
- Best understood as a local orchestration monolith with worker-thread isolation.
- UI and business logic are intentionally separated.
- Runtime state is mostly on disk.
- Seeder decisions are persisted in `seeder_log.json` in the Obsidian vault for traceability.

### TypeScript MCP Server
- Best understood as a companion control plane, not the main desktop app.
- Uses a router pattern to minimize the number of exposed tools.
- Talks directly to NotebookLM via reverse-engineered RPC structures.

## UNKNOWN
- Exact internal behavior of notebooklm-py is not defined in this repo.
- Exact NotebookLM RPC schema details beyond the calls used here are UNKNOWN.
- Whether the Python desktop app and the MCP server are intended to be run together in production is unclear from current source alone.
