# Structure Map

## Root

- README.md: setup, features, structure, runtime data model.
- ARCHITECTURE.md: source-of-truth architecture and runtime chain.
- DEV_GUIDELINES.md: coding and boundary constraints.
- AI_CONTEXT.md: condensed implementation context.
- KNOWN_ISSUES.md: active risks and legacy-surface notes.
- pipeline_context.md: design-target document (not canonical runtime spec).
- CHANGELOG.md: repository change history.
- docker/: container configuration for optional desktop profile.
- launcher/: Windows startup wrappers.
- nestbrain/: primary Python runtime.
- scripts/: build and legacy wrappers.
- pipeline_logs/, staging/, build/: generated artifacts.

## nestbrain/

Primary desktop runtime package.

- main.py: app startup and MainWindow initialization.
- config.json: repository-local config template artifact.
- pipeline-registry.json: repository-local registry snapshot artifact.
- requirements.txt: runtime dependencies.

### nestbrain/core/

Business logic, integrations, workflow orchestration, persistence rules.

- pipeline_runner.py: top-level orchestration and run archive creation.
- workflow_engine.py: active collection pipeline coordinator.
- workflow.py: legacy workflow path (not active runner target).
- registry.py: persistent collection state store.
- vault_manager.py: vault init, classification, file routing, audit logs.
- note_parser.py: Markdown vault parse.
- note_renderer.py: master note render and merge logic.
- knowledge_graph.py: graph payload construction.
- zotero_sync.py: Zotero collection and item operations.
- notebooklm_bridge.py: NotebookLM operations.
- notebooklm_auth.py and notebooklm_browser_auth.py: auth cache and browser auth.
- nvidia_client.py: NVIDIA NIM client for chat, embeddings, ranking.
- ollama_client.py: legacy-named NVIDIA-compatible OpenAI client used in active code.
- nvidia_nim_client.py: likely dead duplicate client surface.

### nestbrain/core/stages/

Active stage modules imported by workflow_engine.py:

- question_planner.py
- q_and_a_loop.py
- master_synthesizer.py
- entity_extractor.py
- note_seeder.py
- vector_indexer.py
- semantic_auditor.py
- connection_annotator.py
- notewriter_stage.py

Legacy stage modules still present:

- notebooklm_stage.py
- synthesis_stage.py

### nestbrain/ui/

PyQt presentation layer and view wiring.

- main_window.py
- workspace.py
- sidebar.py
- zotero_panel.py
- brain_map_view.py
- theme.py and UI helper modules

### nestbrain/workers/

Background worker threads.

- pipeline_worker.py
- sync_worker.py
- graph_worker.py

### nestbrain/runs/

Repository run snapshots captured during local execution history.

## launcher/

Startup wrappers only.

- launcher/README.md
- launcher/windows/start-application.cmd
- launcher/windows/start-nestbrain-desktop.cmd
- launcher/windows/start-nestbrain-desktop.vbs
- launcher/windows/start-research-pipeline.vbs

## scripts/

Build and legacy wrapper folder.

- scripts/build.bat
- scripts/build.spec
- scripts/notebooklm_operations.py (legacy compatibility wrapper)
- scripts/start_vcxsrv.ps1

## docker/

- docker/docker-compose.yml: currently defines one service (nestbrain) behind desktop profile.
- docker/Dockerfile.nestbrain: container image for desktop runtime.

## Generated/Disposable Artifacts

- pipeline_logs/
- staging/
- build/
- scripts/build/

These are not canonical implementation sources.

## Not Present in Current Tree

These paths appear in older references but are not present in this repository:

- automation/
- agents/ (top-level runtime folder)
- src/ at repo root
- mcp-servers/
