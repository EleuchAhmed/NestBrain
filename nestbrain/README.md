# Nestbrain Desktop Application

Purpose: Python desktop application and visualization layer for interactive research workflows.

The runtime vault is managed by `nestbrain/core/vault_manager.py`. On first launch the app creates `My Brain` under the Nestbrain app-data directory, stores the absolute path in config, and lets the classifier create taxonomy folders on demand.

## Major Subfolders

- core: orchestration, pipeline coordination, graph building, integrations
- ui: desktop presentation layer
- workers: background task execution
- assets: static resources and styles
- runs: archived run outputs
- vault_manager.py: first-launch vault initialization, classification, filing, and audit logging

## Rules

- UI code belongs in ui only.
- Business/workflow orchestration belongs in core.
- Long-running/background behavior belongs in workers.
- Runtime artifacts belong in runs; keep source code out of runs.
- Do not hardcode vault paths; use the config value populated by `vault_manager.py`.
