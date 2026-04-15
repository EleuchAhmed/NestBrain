# Architecture

## Architecture Style

- Primary runtime is a local Python desktop app in nestbrain/.
- UI runs in PyQt6 and dispatches blocking work to worker threads.
- Pipeline orchestration is filesystem-backed and stateful through JSON plus Markdown vault artifacts.
- Current repository is not a multi-service microservice graph; docker compose currently defines one optional desktop service.

## Canonical Runtime Chain

```text
User action in MainWindow
  -> PipelineWorker.run()
  -> PipelineRunner.run()
  -> PipelineRunner._run_async()
  -> PipelineWorkflow.run_full_pipeline()
  -> PipelineWorkflow.process_collection() per collection
  -> stage modules in nestbrain/core/stages/
  -> write_note() -> vault_manager.classify_and_file()
  -> KnowledgeGraphBuilder.build()
  -> UI refresh and archive persistence
```

## Active Module Ownership

- Entry point: nestbrain/main.py
- UI orchestration: nestbrain/ui/main_window.py
- Background execution: nestbrain/workers/pipeline_worker.py, nestbrain/workers/sync_worker.py, nestbrain/workers/graph_worker.py
- Top-level pipeline runner: nestbrain/core/pipeline_runner.py
- Active workflow coordinator: nestbrain/core/workflow_engine.py
- Collection registry state: nestbrain/core/registry.py
- Vault initialization and filing policy: nestbrain/core/vault_manager.py
- NotebookLM integration: nestbrain/core/notebooklm_bridge.py and nestbrain/core/notebooklm_auth.py
- Zotero integration: nestbrain/core/zotero_sync.py
- Graph construction: nestbrain/core/knowledge_graph.py
- Graph rendering: nestbrain/ui/brain_map_view.py

## Data and Control Flow

### Startup and Configuration

1. nestbrain/main.py loads environment via dotenv and sets up logging.
2. ensure_config() in nestbrain/core/pipeline_runner.py creates config file if missing.
3. init_vault() in nestbrain/core/vault_manager.py creates default My Brain vault and root README.
4. load_config() materializes PipelineConfig for MainWindow.

### UI to Worker Flow

1. User starts the pipeline from MainWindow._start_pipeline().
2. MainWindow creates a QThread and PipelineWorker.
3. PipelineWorker.run() invokes PipelineRunner.run() with progress/status callbacks.
4. Worker emits result/error/finished signals back to UI.

### Runner and Workflow Flow

1. PipelineRunner._run_async() validates vault path.
2. Runner initializes ZoteroSyncClient and OllamaClient plus KnowledgeGraphBuilder.
3. Runner delegates pipeline logic to PipelineWorkflow.run_full_pipeline().
4. Workflow parses vault notes through MarkdownNoteParser.parse_vault().
5. Workflow syncs collections from Zotero (all or selected key).
6. For each collection, process_collection() performs notebook provisioning, ingest, research, synthesis, extraction, seeding, writing, and propagation.
7. Runner builds graph payload and archives run metadata.

### Per-Collection Processing

PipelineWorkflow.process_collection() performs these steps:

1. Registry bootstrap via PipelineRegistry.get_or_create().
2. Source delta detection via get_new_sources().
3. Notebook creation when notebook_id is missing.
4. Source ingestion via NotebookLMBridge.ingest_text() and registry mark_processed().
5. Taxonomy planning via QuestionPlanner.generate_taxonomy().
6. Iterative research via QAndALoop.execute_research().
7. Deep-dive synthesis via MasterSynthesizer.synthesize().
8. Entity extraction via EntityExtractor.extract_entities().
9. Entity create-or-merge through NoteSeeder.process_extracted_term().
10. Collection note rendering and filing via write_note() and classify_and_file().
11. L3 propagation: VectorIndexer.embed_new_note() -> VectorIndexer.find_similar_notes() -> SemanticAuditor.audit_connections() -> ConnectionAnnotator.annotate_connections().
12. Registry note path update via set_note_path().

### Graph and Archive Flow

1. Runner coerces notes and collections into parser dataclasses.
2. KnowledgeGraphBuilder.build() creates graph payload.
3. PipelineRunner._create_archive_entry() writes run_YYYYMMDD_HHMMSS.json into user-data runs directory.
4. UI consumes graph and status payload through MainWindow result handlers.

## Persistence Model

- Config file: user-data config.json from get_config_path().
- Registry: user-data pipeline-registry.json from get_registry_path().
- Vault notes: classified Markdown files in configured vault root.
- Vault audit: vault_log.jsonl.
- Seeder decisions: seeder_log.json.
- Embedding index: .nestbrain_index.json.
- Run archive snapshots: user-data runs/*.json.

## External Integrations

- Zotero local API and optional web API fallback for create_collection.
- NotebookLM native Python client (notebooklm-py).
- NVIDIA NIM endpoints for chat, embeddings, and ranking.
- Optional Docker desktop profile with VcXsrv for GUI display on Windows.

## Legacy and Dead-Code Surface (Report Only)

These files are present in the repository but are not part of the active PipelineRunner -> workflow_engine path:

- nestbrain/core/workflow.py
- nestbrain/core/stages/notebooklm_stage.py
- nestbrain/core/stages/synthesis_stage.py
- nestbrain/core/nvidia_nim_client.py
- scripts/notebooklm_operations.py

They are retained in-tree but should not be treated as canonical implementation.

## Known Boundaries

- notebooklm-py internals are external to this repository.
- The compose stack in docker/docker-compose.yml defines one service (nestbrain) for desktop profile startup.
- Generated folders such as pipeline_logs/, staging/, and build outputs are disposable runtime artifacts, not source-of-truth logic.
