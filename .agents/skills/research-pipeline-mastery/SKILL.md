---
name: research-pipeline-mastery
description: 'Use when working on Nestbrain research-pipeline tasks: architecture tracing, v2 stage changes, pipeline debugging, Zotero/NotebookLM/NVIDIA integration checks, vault note generation, graph updates, launcher behavior, and safe extension planning.'
argument-hint: 'Task focus: pipeline | ui | integrations | debugging | testing | docs'
user-invocable: true
---

# Research Pipeline Mastery

## What This Skill Produces
- Accurate, code-verified changes for the Nestbrain desktop app and v2 research pipeline.
- Fast routing to the correct subsystem before editing.
- Completion checks that confirm runtime behavior, not just static code changes.

## Project Facts To Anchor On
- Primary runtime is Python desktop in nestbrain/.
- Canonical pipeline entrypoint is nestbrain/core/pipeline_runner.py.
- Active workflow is nestbrain/core/v2_workflow.py (workflow.py is legacy unless runner changes).
- UI lives in nestbrain/ui/, background work in nestbrain/workers/, business logic and integrations in nestbrain/core/.
- Persistent collection state is pipeline-registry.json (schema changes require migration handling).
- Vault output is the source of truth for generated notes; filing and classification go through nestbrain/core/vault_manager.py.
- Generated artifacts and logs (for example pipeline_logs/ and build outputs) are disposable unless task says otherwise.

## When To Use
- Add or modify any behavior in the v2 pipeline layers.
- Diagnose failures in run flow: Zotero sync, NotebookLM ingest/Q&A, synthesis, note writing, graph updates.
- Extend note rendering, semantic linking, or vault filing behavior.
- Change launcher, Docker, or startup behavior that affects local execution.
- Review architecture correctness before implementation.

## Decision Routing
1. If request touches pipeline orchestration:
- Start in nestbrain/core/pipeline_runner.py then trace into nestbrain/core/v2_workflow.py.

2. If request touches one v2 stage behavior:
- Edit the relevant module in nestbrain/core/stages/ and verify call sites in v2_workflow.py.

3. If request touches note output paths, classification, or filing:
- Route through nestbrain/core/vault_manager.py and keep note_renderer + write/merge paths aligned.

4. If request touches UI responsiveness or long-running actions:
- Keep blocking logic in nestbrain/workers/ and signals in nestbrain/ui/.

5. If request touches graph structure or rendering:
- Update both nestbrain/core/knowledge_graph.py and nestbrain/ui/brain_map_view.py as a pair.

6. If request touches startup/packaging only:
- Keep launcher/windows scripts thin wrappers and avoid moving business logic there.

## Standard Workflow
1. Confirm the exact outcome and identify affected subsystem(s): pipeline, UI, integration, launcher, docs.
2. Read authoritative files first:
- README.md
- ARCHITECTURE.md
- DEV_GUIDELINES.md
- nestbrain/core/pipeline_runner.py
- nestbrain/core/v2_workflow.py
3. Trace real code path before edits:
- Entry point -> runner -> workflow -> stage(s) -> renderer/writer -> vault manager -> registry/archive.
4. Apply minimal edits at the smallest responsible boundary.
5. Validate behavior with targeted commands and tests.
6. Re-check for regressions in neighboring components.
7. Summarize changed files, behavior impact, and any residual risk.

## Pipeline Debug Procedure
1. Reproduce with source run:
- python -m nestbrain.main
2. If run fails early, check configuration and vault validation logic in pipeline_runner.py.
3. Check integration boundaries in order:
- Zotero sync (zotero_sync.py)
- NotebookLM bridge/auth (notebooklm_bridge.py and auth modules)
- NVIDIA NIM client availability (nvidia_nim_client.py)
4. For per-collection failures, inspect v2_workflow process_collection_v2 path and stage status messages.
5. Inspect run outputs:
- nestbrain/runs/*.json
- pipeline_logs/
- vault audit logs written by vault_manager.py
6. Verify registry consistency:
- notebook ID mapping
- processed source keys
- obsidian/media paths

## Extension Patterns
- New pipeline capability: prefer a new stage in nestbrain/core/stages/ and wire it in v2_workflow.py.
- New UI action: signal/slot wiring in ui/, execution in workers/, logic in core/.
- New Zotero behavior: implement in ZoteroSyncClient instead of UI-side ad hoc calls.
- New note enrichment: update both create and merge paths together.

## Quality Gates (Done Criteria)
- Architecture gate:
- Change respects UI/worker/core boundaries.
- Correctness gate:
- Workflow path still runs from runner to completion or fails with actionable errors.
- Data gate:
- Registry and vault outputs stay compatible.
- Safety gate:
- No unrelated refactors or schema changes without migration.
- Validation gate:
- Relevant tests pass (or explicit note if tests could not be executed).

## Common Failure Patterns
- Editing legacy workflow.py while expecting runner behavior changes.
- Writing vault paths directly in stages instead of routing through vault manager policies.
- Updating graph generation without corresponding UI graph view handling.
- Trusting stale docs that mention missing folders (agents/, automation/, src/ root).

## Quick Command Set
```bash
python -m nestbrain.main
pytest -q
python -m pytest test_pipeline_cli.py -q
python -m pytest test_v2_components.py -q
python -m pytest test_vault_manager.py -q
```

## Completion Checklist
- Target subsystem identified and correct files updated.
- Entry-point trace verified for the changed flow.
- Tests or reproduction steps executed and outcomes captured.
- Risks and assumptions documented if external services block full verification.
