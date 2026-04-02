# Structure Map

## Root
- `README.md` - top-level overview, but some statements are stale relative to the current tree.
- `CHANGELOG.md` - migration notes and release history.
- `v2_context.md` - design intent for the v2 multi-layer knowledge graph workflow.
- `docker-compose.yml` - current Docker entry configuration.
- `docs/` - architecture documentation.
- `launcher/` - startup wrappers for Windows.
- `nestbrain/` - primary Python application.
- `antigravity-notebooklm-mcp/` - companion TypeScript NotebookLM MCP server.
- `scripts/` - legacy compatibility and build helpers.
- `docker/` - Dockerfile definitions.
- `staging/` - generated NotebookLM artifacts and captures.
- `pipeline_logs/` - generated logs.

## `nestbrain/`
- Purpose: desktop app, pipeline orchestration, vault processing, and visualization.
- Key files:
  - `main.py` - bootstraps the Qt application.
  - `config.json` - persistent user settings.
  - `pipeline-registry.json` - per-collection pipeline state.
  - `requirements.txt` - Python dependencies.
- Relationships:
  - `main.py` creates `MainWindow` from `ui/main_window.py`.
  - `ui/` calls into `core/` through worker objects.
  - `core/` uses `workers/` only through signal and slot orchestration.

### `nestbrain/core/`
- Purpose: business logic and service integration.
- Key files:
  - `pipeline_runner.py` - pipeline entry logic and run archive creation.
  - `v2_workflow.py` - active orchestration of the decomposed research pipeline.
  - `workflow.py` - older workflow coordinator, likely legacy.
  - `zotero_sync.py` - Zotero client and data models.
  - `notebooklm_bridge.py` - NotebookLM operations.
  - `ollama_client.py` - NVIDIA NIM client wrapper.
  - `obsidian_parser.py` - vault scanning and note extraction.
  - `knowledge_graph.py` - graph payload builder.
  - `note_renderer.py` - note template rendering and merging.
  - `registry.py` - registry persistence for collections.
  - `stages/` - v2 stage modules.
- Relationships:
  - `pipeline_runner.py` owns the top-level orchestration.
  - `v2_workflow.py` composes the stage modules.
  - `registry.py` is shared by the workflow and runner.

### `nestbrain/core/stages/`
- Purpose: smaller units of the v2 pipeline.
- Key files:
  - `question_planner.py` - builds the question taxonomy.
  - `q_and_a_loop.py` - runs NotebookLM question loops.
  - `master_synthesizer.py` - turns Q and A into a master note.
  - `entity_extractor.py` - extracts linked entities.
  - `note_seeder.py` - creates or patches entity notes.
  - `vector_indexer.py` - semantic indexing and similarity search.
  - `semantic_auditor.py` - reranking and false-positive reduction.
  - `connection_annotator.py` - writes semantic relationship annotations.
  - `notebooklm_stage.py` - NotebookLM operations for collection processing.
  - `synthesis_stage.py` - synthesis orchestration.
  - `notewriter_stage.py` - final note write and merge logic.
- Relationships:
  - `v2_workflow.py` imports these modules directly.
  - The stage split reflects the current research pipeline decomposition.

### `nestbrain/ui/`
- Purpose: visual interface and user interaction.
- Key files:
  - `main_window.py` - main shell and wiring.
  - `workspace.py` - home, notes, archive, and brain views.
  - `sidebar.py` - navigation.
  - `zotero_panel.py` - Zotero controls and collection list.
  - `brain_map_view.py` - graph canvas.
- Relationships:
  - `main_window.py` coordinates UI state and background workers.
  - `workspace.py` renders results produced by the core pipeline.

### `nestbrain/workers/`
- Purpose: run blocking work off the UI thread.
- Key files:
  - `pipeline_worker.py`
  - `sync_worker.py`
  - `graph_worker.py`
- Relationships:
  - Each worker converts core results into Qt signals.

### `nestbrain/runs/`
- Purpose: archived run payloads.
- Relationship:
  - Created and read by `PipelineRunner`.

### `nestbrain/assets/`
- Purpose: static resources and generated media storage used by the desktop app.

## `antigravity-notebooklm-mcp/`
- Purpose: standalone NotebookLM MCP server and tooling.
- Key files:
  - `src/index.ts` - stdio server and tool router.
  - `src/api-client.ts` - direct NotebookLM client.
  - `src/orchestrator.ts` - deep research and artifact orchestration.
  - `src/browser-auth.ts` - browser login helper.
  - `src/auth-cli.ts` - manual auth helper.
  - `src/constants.ts` - RPC identifiers and enums.
  - `src/verify-all.ts` and `src/verify-research.ts` - validation helpers.
- Relationships:
  - `index.ts` instantiates the client and orchestrator.
  - `orchestrator.ts` depends on `api-client.ts` and `constants.ts`.
  - `browser-auth.ts` writes auth tokens to the local NotebookLM cache.

## `launcher/`
- Purpose: user-facing startup entry points.
- Key files:
  - `windows/start-application.cmd`
  - `windows/start-nestbrain-desktop.vbs`
  - `windows/start-research-pipeline.vbs`
  - `windows/start-notebooklm-authentication.bat`
- Relationships:
  - These wrappers should stay thin and should not hold business logic.

## `scripts/`
- Purpose: compatibility wrappers and build packaging.
- Key files:
  - `notebooklm_operations.py`
  - `build.bat`
  - `build.spec`
- Relationships:
  - Current docs treat this folder as legacy or compatibility-oriented.

## `docker/`
- Purpose: container definitions.
- Key file:
  - `Dockerfile.nestbrain`

## `docs/`
- Purpose: architecture and repository reference docs.
- Important file:
  - `architecture/REPOSITORY_INFORMATION_ARCHITECTURE.md`
- Relationships:
  - Some docs are stale; verify against source before using them as truth.

## `staging/`
- Purpose: transient NotebookLM output files, HTML captures, and JSON artifacts.
- Relationship:
  - Safe to treat as generated data.

## `pipeline_logs/`
- Purpose: runtime logs.
- Relationship:
  - Generated output; not source of truth.

## Not Present In Current Tree
- `automation/`
- `agents/`
- `src/` at the repo root
- `mcp-servers/`
- root compatibility wrappers such as `Start-ResearchPipeline.vbs`, `Run-Nestbrain.vbs`, and `authenticate.bat`

These paths are referenced by some docs but do not exist in the current workspace.
