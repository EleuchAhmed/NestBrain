# Nestbrain Research Pipeline

Nestbrain is a Python and PyQt6 desktop application that converts Zotero collections into structured Markdown knowledge notes. The active runtime path is:

MainWindow -> PipelineWorker -> PipelineRunner -> PipelineWorkflow (workflow_engine.py) -> stage modules -> vault_manager classification and filing.

## Core Features

- Desktop-first orchestration in nestbrain/main.py and nestbrain/ui/main_window.py.
- Threaded execution with Qt workers in nestbrain/workers/pipeline_worker.py, nestbrain/workers/sync_worker.py, and nestbrain/workers/graph_worker.py.
- Zotero sync and optional collection creation through nestbrain/core/zotero_sync.py.
- Native NotebookLM operations via notebooklm-py through nestbrain/core/notebooklm_bridge.py.
- NVIDIA-backed planning, synthesis, extraction, classification, and embeddings through nestbrain/core/nvidia_client.py and nestbrain/core/ollama_client.py.
- Structured pipeline stages in nestbrain/core/stages/ (question planner, Q&A loop, master synthesizer, entity extractor, note seeder, vector indexer, semantic auditor, connection annotator, note writer).
- Vault filing and taxonomy classification in nestbrain/core/vault_manager.py.
- Graph construction in nestbrain/core/knowledge_graph.py and rendering in nestbrain/ui/brain_map_view.py.
- Persistent run, registry, and audit outputs: config.json, pipeline-registry.json, runs/*.json, vault_log.jsonl, seeder_log.json.

## Installation and Setup (Source)

### Prerequisites

1. Python 3.11 or newer.
2. Zotero running locally (default host http://localhost:23119).
3. NVIDIA API key for NIM-backed model calls.
4. NotebookLM account for authentication.

### Setup Steps

```bash
# 1) Clone
git clone https://github.com/EleuchAhmed/NestBrain.git
cd NestBrain

# 2) Create and activate virtual environment (required by launcher scripts)
python -m venv .venv
.venv\Scripts\activate

# 3) Install dependencies
pip install -r nestbrain/requirements.txt
playwright install chromium

# 4) Optional: create local env file
copy .env.example .env

# 5) Start desktop app
python -m nestbrain.main
```

### First Run Checklist

1. Open Settings and confirm vault path.
2. Add Zotero Library ID and Zotero API key if needed.
3. Add NVIDIA API key in settings (or NVIDIA_API_KEY in environment).
4. Run NotebookLM authentication from Settings.

Notes:

- The app persists operational settings in the user-data config JSON, not only in .env.
- .env is used for environment-backed credentials and local Docker startup values.
- NotebookLM auth now defaults to trusted-browser-first mode with automatic fallback.
- Optional overrides:
	- `NOTEBOOKLM_AUTH_MODE=auto|trusted|playwright`
	- `NOTEBOOKLM_CHROMIUM_EXECUTABLE=C:\\Path\\To\\chrome.exe`

## Launcher and Docker Runtime

- launcher/windows/start-nestbrain-desktop.vbs starts the app from .venv/Scripts/pythonw.exe.
- launcher/windows/start-research-pipeline.vbs starts VcXsrv and then runs docker compose -f docker/docker-compose.yml --profile desktop up -d.
- docker/docker-compose.yml currently defines one service: nestbrain (desktop profile).

## Packaging

Build the standalone executable with:

```cmd
.\scripts\build.bat
```

Output binary: scripts/dist/Nestbrain.exe.

## Project Structure (Current)

```text
research-pipeline/
	README.md
	ARCHITECTURE.md
	DEV_GUIDELINES.md
	AI_CONTEXT.md
	KNOWN_ISSUES.md
	STRUCTURE_MAP.md
	pipeline_context.md
	launcher/
		README.md
		windows/
			start-application.cmd
			start-nestbrain-desktop.vbs
			start-research-pipeline.vbs
	docker/
		docker-compose.yml
		Dockerfile.nestbrain
	scripts/
		README.md
		build.bat
		build.spec
		notebooklm_operations.py (legacy compatibility wrapper)
	nestbrain/
		main.py
		core/
			pipeline_runner.py
			workflow_engine.py (active)
			workflow.py (legacy path)
			vault_manager.py
			registry.py
			note_parser.py
			knowledge_graph.py
			notebooklm_bridge.py
			zotero_sync.py
			nvidia_client.py
			ollama_client.py
			stages/
				question_planner.py
				q_and_a_loop.py
				master_synthesizer.py
				entity_extractor.py
				note_seeder.py
				vector_indexer.py
				semantic_auditor.py
				connection_annotator.py
				notewriter_stage.py
				notebooklm_stage.py (legacy stage module)
				synthesis_stage.py (legacy stage module)
		ui/
			main_window.py
			workspace.py
			sidebar.py
			zotero_panel.py
			brain_map_view.py
		workers/
			pipeline_worker.py
			sync_worker.py
			graph_worker.py
		runs/
			run_YYYYMMDD_HHMMSS.json
	pipeline_logs/ (generated)
	staging/ (generated)
	build/ (generated)
```

## Runtime State and Persistence

- User config path is managed via nestbrain/core/paths.py and saved by load_config/save_config in nestbrain/core/pipeline_runner.py.
- Collection processing state is persisted with PipelineRegistry in nestbrain/core/registry.py.
- Vault notes are classified and filed by classify_and_file in nestbrain/core/vault_manager.py.
- Classification audit lines are appended to vault_log.jsonl.
- Seeder decisions are appended to seeder_log.json.
- Run archive snapshots are created in user-data runs directory by PipelineRunner._create_archive_entry.

## Dead Code and Legacy Surface (Report)

The following files remain in-tree but are not part of the active runner path and should be treated as legacy until removed in a separate cleanup task:

- nestbrain/core/workflow.py
- nestbrain/core/stages/notebooklm_stage.py
- nestbrain/core/stages/synthesis_stage.py
- nestbrain/core/nvidia_nim_client.py
- scripts/notebooklm_operations.py

Also note that test_note_renderer_registry_media.py includes legacy imports for notebooklm_stage and should be reviewed in a dedicated test cleanup pass.

## License

MIT
