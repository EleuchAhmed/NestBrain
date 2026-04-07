# Known Issues

## High Priority
- `nestbrain/core/pipeline_runner.py` builds a knowledge graph from empty note and collection lists, so the returned graph payload is effectively empty or near-empty.
- `nestbrain/core/stages/notebooklm_stage.py` currently generates video only; audio generation is not implemented in the active stage even though other parts of the system expect media paths.
- `nestbrain/core/note_renderer.py` has a likely slugify bug: the current implementation uses string replacement on the pattern text instead of a real regex replacement.

## Medium Priority
- `nestbrain/core/note_renderer.py` uses brittle string-based merge logic for frontmatter and section updates. It can mis-handle notes whose formatting does not match the expected template.
- `nestbrain/core/registry.py` stores state in JSON with minimal validation. Corrupted registry files are silently reset.
- `nestbrain/core/ollama_client.py` is misnamed for what it actually does: it talks to NVIDIA NIM, not a local Ollama server.

## Resolved in Vault Manager
- `nestbrain/core/stages/semantic_auditor.py` and `nestbrain/core/stages/connection_annotator.py` now use recursive note lookup instead of assuming root-level note filenames.
- `nestbrain/core/stages/note_seeder.py` now files generated entity notes through the vault manager, so it no longer writes directly to the vault root.

## Low Priority But Hallucination-Prone
- `nestbrain/core/workflow.py` is present but appears unused by the active runner. Future agents may incorrectly treat it as canonical if they do not check `pipeline_runner.py`.
- Several docs reference folders and wrappers that are not present in the current tree, including `automation/`, `agents/`, `src/`, `mcp-servers/`, and root compatibility scripts. These references should be treated as stale.
- `CHANGELOG.md` claims the Node.js dependency was fully removed, but the `antigravity-notebooklm-mcp/` subsystem is still present and functional.
- `launcher/README.md` and `docs/architecture/REPOSITORY_INFORMATION_ARCHITECTURE.md` describe runtime paths that do not match the current `docker-compose.yml`.

## Incomplete Or Unclear Areas
- Whether `notebooklm-py` handles all NotebookLM auth and session behavior or hides extra browser automation is not visible from this repo. Internal behavior is UNKNOWN.
- The exact intended production relationship between the Python desktop app and the Node MCP server is not clearly documented in source.
- The current Docker configuration does not show the larger multi-service pipeline described by some older notes.

## Risks
- Vault path validation is deliberately broad to prevent accidental scanning of top-level folders, but if users misconfigure the vault path they may still see unexpected notes or warnings.
- The current architecture mixes a newer v2 workflow with older compatibility code. That increases the chance of changing the wrong path during maintenance.
- Generated folders such as `staging/`, `pipeline_logs/`, and build outputs can accumulate quickly if not cleaned up.
