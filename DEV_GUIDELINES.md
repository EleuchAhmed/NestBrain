# Dev Guidelines

## Naming Conventions
- Python modules and functions use snake_case.
- Python classes use PascalCase.
- Qt signal names should stay descriptive and action-oriented.
- Preserve existing file names unless there is a strong compatibility reason to rename them.
- Keep the current folder convention for generated notes: `20_Concepts/{domain}/{slug}.md`.

## Code Style Rules
- Keep UI code in `nestbrain/ui/`.
- Keep background or blocking logic in `nestbrain/workers/`.
- Keep business logic, integrations, and note processing in `nestbrain/core/`.
- Keep vault creation, classification, and filing policy in `nestbrain/core/vault_manager.py`.
- Keep Windows launchers and scripts thin; they should only start the app or delegate to canonical code.
- Preserve existing serialization formats unless every reader is updated together.

## Architectural Constraints
- `PipelineRunner` is the top-level Python orchestration entry point.
- `PipelineWorkflow` in `workflow_engine.py` is the active workflow implementation used by the runner.
- `workflow.py` is legacy and should not be treated as the primary flow unless the runner is explicitly changed.
- `pipeline-registry.json` is the persistent collection state store; changing its schema requires migration logic.
- The note vault is the primary output sink. Avoid writing arbitrary new file types into the vault root.
- The `My Brain` vault root should stay clean; taxonomy folders are created by the classifier on demand.
- The NotebookLM auth cache is app-managed, with compatibility fallback for legacy `~/.notebooklm-mcp/auth.json` tokens.
- The Python bridge uses `notebooklm-py` for NotebookLM operations.

## What Must Not Be Changed Lightly
- The registry JSON shape without a migration plan.
- The vault output path conventions used by note rendering and the graph view.
- The launcher files’ role as wrappers only.
- The current separation between UI, workers, and core logic.

## Safe Extension Rules
- Add new pipeline behavior as a new stage module in `nestbrain/core/stages/` when possible.
- Add UI interactions by wiring new signals in `nestbrain/ui/` and dispatching work to a worker thread.
- Add Zotero-facing behavior through `ZoteroSyncClient` rather than ad hoc HTTP calls in UI code.
- Add note filing behavior through `vault_manager.py` instead of duplicating path logic in stages.
- If you modify note rendering, update both the create and merge paths together.
- If you modify graph data, update `KnowledgeGraphBuilder` and `BrainMapView` together.

## Operational Rules
- Treat generated folders like `staging/`, `pipeline_logs/`, and build outputs as disposable.
- Do not assume docs are current; verify source before following old path references.
- Use the repo’s existing service boundaries before introducing new abstractions.

## Hallucination Guards
- If a path is mentioned in older docs but not present in the current tree, mark it as UNKNOWN instead of inventing it.
- If a behavior is only implied by a doc and not visible in code, verify the code first.
- If a feature exists in the roadmap but not in source, treat it as planned work, not implemented behavior.

## When Extending the System
- For Python pipeline changes, start in `nestbrain/core/pipeline_runner.py` and trace into `workflow_engine.py`.
- For UI changes, start in `nestbrain/ui/main_window.py` and the relevant view module.
- For launch behavior, keep changes in `launcher/windows/` and avoid mixing in runtime logic.
