# AI Context

## Project Summary

Nestbrain Research Pipeline is a local desktop pipeline that transforms Zotero collections into structured Markdown notes, then maps notes into a graph visualization.

Active orchestration path:

MainWindow -> PipelineWorker -> PipelineRunner -> PipelineWorkflow (workflow_engine.py) -> stage modules -> vault_manager filing -> graph build.

## Runtime and Boundaries

- Primary runtime: Python desktop app in nestbrain/.
- UI: nestbrain/ui/.
- Worker threads: nestbrain/workers/.
- Business logic and integrations: nestbrain/core/.
- Persistence: filesystem (config, registry, run archives, vault notes, logs).

## Core Technology Stack

- Python 3.11+
- PyQt6
- requests (Zotero HTTP)
- notebooklm-py (NotebookLM)
- python-dotenv
- networkx and matplotlib (graph generation)
- NVIDIA NIM endpoints via nvidia_client.py and ollama_client.py
- Optional docker compose desktop profile for containerized GUI run

## Canonical Modules

### Entry and UI

- nestbrain/main.py: application entrypoint and startup bootstrap.
- nestbrain/ui/main_window.py: user actions, worker wiring, results and error handling.
- nestbrain/workers/pipeline_worker.py: pipeline execution in background thread.
- nestbrain/workers/sync_worker.py: Zotero sync refresh.
- nestbrain/workers/graph_worker.py: graph build off UI thread.

### Pipeline and State

- nestbrain/core/pipeline_runner.py: top-level runner, vault path validation, graph creation, run archive writes, config load/save.
- nestbrain/core/workflow_engine.py: active workflow implementation.
- nestbrain/core/registry.py: collection state persistence (notebook_id, processed sources, note path).
- nestbrain/core/vault_manager.py: vault init, taxonomy classification, file move, audit logs.

### Integrations

- nestbrain/core/zotero_sync.py: collection/item sync and optional create_collection flow.
- nestbrain/core/notebooklm_bridge.py: notebook create, source ingest, synthesize, media calls.
- nestbrain/core/notebooklm_auth.py + nestbrain/core/notebooklm_browser_auth.py: NotebookLM auth caching and browser auth flow.
- nestbrain/core/nvidia_client.py: chat, embedding, ranking requests to NVIDIA NIM.
- nestbrain/core/ollama_client.py: legacy-named OpenAI-compatible NVIDIA client used by active paths.

### Stage Modules Used by workflow_engine.py

- question_planner.py
- q_and_a_loop.py
- master_synthesizer.py
- entity_extractor.py
- note_seeder.py
- vector_indexer.py
- semantic_auditor.py
- connection_annotator.py
- notewriter_stage.py

## Persistence and Outputs

- User-data config.json via get_config_path().
- User-data pipeline-registry.json via get_registry_path().
- Vault Markdown notes classified under taxonomy folders.
- vault_log.jsonl for filing audit entries.
- seeder_log.json for entity create/merge decisions.
- .nestbrain_index.json for vector index state.
- user-data runs/run_YYYYMMDD_HHMMSS.json archive entries.

## Current Legacy Surface (Report)

These files exist but are not used by active runner orchestration:

- nestbrain/core/workflow.py
- nestbrain/core/stages/notebooklm_stage.py
- nestbrain/core/stages/synthesis_stage.py
- nestbrain/core/nvidia_nim_client.py
- scripts/notebooklm_operations.py

## Generated/Disposable Folders

- pipeline_logs/
- staging/
- build/
- nestbrain/runs/ in repository snapshots (historical run captures)

Treat them as runtime artifacts, not source-of-truth architecture.
