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
- Keep Windows launchers and scripts thin; they should only start the app or delegate to canonical code.
- Keep the TypeScript MCP server router-based; prefer extending existing tools over adding many new top-level tools.
- Preserve existing serialization formats unless every reader is updated together.

## Architectural Constraints
- `PipelineRunner` is the top-level Python orchestration entry point.
- `PipelineWorkflowV2` is the active workflow implementation used by the runner.
- `workflow.py` is legacy and should not be treated as the primary flow unless the runner is explicitly changed.
- `pipeline-registry.json` is the persistent collection state store; changing its schema requires migration logic.
- The Obsidian vault is the primary output sink. Avoid writing arbitrary new file types into the vault root.
- The NotebookLM auth cache lives under `~/.notebooklm-mcp/auth.json` for the Node server.
- The Python bridge uses `notebooklm-py`; the TypeScript server uses a reverse-engineered NotebookLM web client. Keep those responsibilities separate.

## What Must Not Be Changed Lightly
- The registry JSON shape without a migration plan.
- The vault output path conventions used by note rendering and the graph view.
- The launcher files’ role as wrappers only.
- The router-style MCP tool layout in `antigravity-notebooklm-mcp/`.
- The auth cache location and field expectations used by the MCP server.
- The current separation between UI, workers, and core logic.

## Safe Extension Rules
- Add new pipeline behavior as a new stage module in `nestbrain/core/stages/` when possible.
- Add UI interactions by wiring new signals in `nestbrain/ui/` and dispatching work to a worker thread.
- Add Zotero-facing behavior through `ZoteroSyncClient` rather than ad hoc HTTP calls in UI code.
- Add new NotebookLM capabilities in the MCP server by extending an existing router action before creating new top-level tools.
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
- For Python pipeline changes, start in `nestbrain/core/pipeline_runner.py` and trace into `v2_workflow.py`.
- For UI changes, start in `nestbrain/ui/main_window.py` and the relevant view module.
- For MCP changes, start in `antigravity-notebooklm-mcp/src/index.ts` and the client and orchestrator pair.
- For launch behavior, keep changes in `launcher/windows/` and avoid mixing in runtime logic.
