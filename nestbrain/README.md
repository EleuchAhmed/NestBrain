# Nestbrain Desktop Application

Purpose: Python desktop application and visualization layer for interactive research workflows.

## Major Subfolders

- core: orchestration, pipeline coordination, graph building, integrations
- ui: desktop presentation layer
- workers: background task execution
- assets: static resources and styles
- runs: archived run outputs

## Rules

- UI code belongs in ui only.
- Business/workflow orchestration belongs in core.
- Long-running/background behavior belongs in workers.
- Runtime artifacts belong in runs; keep source code out of runs.
