# Known Issues

## High Priority
- Empty or near-empty graph payloads can occur when the vault has no parsed notes and Zotero sync returns no collections or items. This is expected behavior for empty input state, but UX messaging can be improved.
- Registry recovery in `nestbrain/core/registry.py` intentionally resets on corruption after backup. This protects runtime continuity but can hide persistent upstream write errors if not monitored.

## Medium Priority
- `nestbrain/core/registry.py` stores state in JSON with minimal validation. Corrupted registry files are reset after error logging.

## Resolved in Vault Manager
- `nestbrain/core/stages/semantic_auditor.py` and `nestbrain/core/stages/connection_annotator.py` now use recursive note lookup instead of assuming root-level note filenames.
- `nestbrain/core/stages/note_seeder.py` now files generated entity notes through the vault manager, so it no longer writes directly to the vault root.
- Slug conversion concerns are resolved in active code paths: `to_slug` in `nestbrain/core/utils.py` uses regex normalization and is the canonical slug utility.
- Legacy claim that `notebooklm_stage.py` lacks audio generation is stale; that module includes audio generation logic, but it is not the active runner path.

## Low Priority But Hallucination-Prone
- `nestbrain/core/workflow.py` is present but appears unused by the active runner. Future agents may incorrectly treat it as canonical if they do not check `pipeline_runner.py`.
- Additional legacy modules that are likely dead relative to active orchestration: `nestbrain/core/stages/notebooklm_stage.py`, `nestbrain/core/stages/synthesis_stage.py`, `nestbrain/core/nvidia_nim_client.py`, and `scripts/notebooklm_operations.py`.

## Incomplete Or Unclear Areas
- Whether `notebooklm-py` handles all NotebookLM auth and session behavior or hides extra browser automation is not visible from this repo. Internal behavior is UNKNOWN.
- The current Docker configuration does not show the larger multi-service pipeline described by some older notes.

## Risks
- Vault path validation is deliberately broad to prevent accidental scanning of top-level folders, but if users misconfigure the vault path they may still see unexpected notes or warnings.
- The current architecture mixes a newer workflow engine with older compatibility code. That increases the chance of changing the wrong path during maintenance.
- Generated folders such as `staging/`, `pipeline_logs/`, and build outputs can accumulate quickly if not cleaned up.
