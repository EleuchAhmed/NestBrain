# Repository Information Architecture

This document defines the canonical repository layout and startup flow.

## 1) Canonical Execution Entry Point

Primary Windows launcher (equivalent executable entrypoint):
- launcher/windows/start-application.cmd

Secondary launchers:
- launcher/windows/start-research-pipeline.vbs
- launcher/windows/start-nestbrain-desktop.vbs
- launcher/windows/start-notebooklm-authentication.bat

Compatibility wrappers at repository root:
- Start-ResearchPipeline.vbs
- Run-Nestbrain.vbs
- authenticate.bat

## 2) Hierarchical Runtime Flow

input -> automation ingestion -> feature orchestration -> synthesis -> output

- input: Zotero storage and metadata
- automation ingestion: automation/watcher (canonical) + scripts/watcher.py (compatibility wrapper)
- orchestration: agents/pipeline.ts -> src/features/pipeline/workflow.ts
- synthesis and note build: src/features/pipeline/stages/*
- output: Obsidian vault + staging artifacts + pipeline-registry.json

## 3) Folder Intent Rules

Top-level folder responsibilities:
- launcher: user-facing startup/launch files only
- automation: process automation entrypoints
- src: production TypeScript implementation
- nestbrain: Python desktop application
- agents: thin runtime adapters
- mcp-servers: local MCP server entrypoints
- scripts: legacy compatibility wrappers only
- docs: architecture and operational documentation
- staging: transient inputs and generated raw artifacts
- pipeline_logs: runtime logs

## 4) Notes for Contributors

- Keep root launch files as wrappers only.
- Add new logic to src/features or nestbrain/core, not to launcher or scripts.
- Keep dependency direction clean: features can depend on services/core/config; reverse imports are not allowed.
