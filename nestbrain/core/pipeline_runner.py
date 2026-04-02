"""Pipeline orchestrator: delegates to workflow coordinator stages."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

from .knowledge_graph import KnowledgeGraphBuilder
from .obsidian_parser import ObsidianParser
from .ollama_client import OllamaClient
from .zotero_sync import ZoteroSyncClient, ZoteroSyncError
from .v2_workflow import PipelineWorkflowV2 as PipelineWorkflow


DEFAULT_CONFIG: dict[str, Any] = {
    "vault_path": "",
    "zotero_library_id": "",
    "zotero_api_key": "",
    "selected_collection_key": "",
    "ollama_model": "deepseek-ai/deepseek-r1",
    "ollama_host": "https://integrate.api.nvidia.com/v1",
    "zotero_host": "http://localhost:23119",
    "theme": "dark",
}


@dataclass(slots=True)
class PipelineConfig:
    vault_path: str
    zotero_library_id: str
    zotero_api_key: str
    selected_collection_key: str
    ollama_model: str
    ollama_host: str
    zotero_host: str
    theme: str


class PipelineRunner:
    """Orchestrates pipeline via workflow stages: NotebookLM → Synthesis → Note Writing."""

    def __init__(self, app_root: str | Path) -> None:
        self.app_root = Path(app_root).resolve()
        self.archive_dir = self.app_root / "runs"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Delegate to workflow coordinator
        self.workflow = PipelineWorkflow(self.app_root)

    def run(
        self,
        config: PipelineConfig,
        progress_callback: Callable[[int], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Run full pipeline: parse vault → sync Zotero → NotebookLM → synthesis → write.
        
        Returns:
            {notes, collections, graph, archive_entry, created_notes, errors}
        """
        return asyncio.run(self._run_async(config, progress_callback, status_callback))

    async def _run_async(
        self,
        config: PipelineConfig,
        progress_callback: Callable[[int], None] | None,
        status_callback: Callable[[str], None] | None,
    ) -> dict[str, Any]:
        """Async version using workflow coordinator."""
        self._emit(status_callback, "Initializing pipeline")
        self._emit(progress_callback, 5)

        # Validate vault before proceeding
        vault_validation = self._validate_vault_path(config.vault_path)
        if vault_validation["error"]:
            self._emit(status_callback, f"Configuration error: {vault_validation['error']}")
            return {
                "notes": [],
                "collections": [],
                "graph": {},
                "archive_entry": None,
                "created_notes": [],
                "errors": {
                    "zotero": "",
                    "ollama": "",
                    "vault": vault_validation["error"],
                },
            }

        # Initialize services
        zotero = ZoteroSyncClient(
            host=config.zotero_host,
            library_id=config.zotero_library_id,
            api_key=config.zotero_api_key,
        )
        ollama = OllamaClient(host=config.ollama_host, model=config.ollama_model)
        graph_builder = KnowledgeGraphBuilder()
        
        # Delegate to workflow
        workflow_result = await self.workflow.run_full_pipeline(
            vault_path=config.vault_path,
            zotero=zotero,
            ollama=ollama,
            selected_collection_key=config.selected_collection_key,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )
        
        # Build knowledge graph from workflow results
        self._emit(status_callback, "Building knowledge graph")
        graph_payload = graph_builder.build(
            notes=workflow_result.get("notes", []),
            collections=workflow_result.get("collections", []),
            semantic_links=workflow_result.get("semantic_links", [])
        )
        
        # Create archive entry
        archive_entry = self._create_archive_entry(
            note_count=len(workflow_result.get("notes", [])),
            collection_count=len(workflow_result.get("collections", [])),
            graph_nodes=len(graph_payload.get("nodes", [])),
            graph_edges=len(graph_payload.get("edges", [])),
            errors=workflow_result.get("errors", {}),
        )
        
        self._emit(progress_callback, 100)
        self._emit(status_callback, "Pipeline complete")
        
        return {
            "notes": workflow_result.get("notes", []),
            "collections": workflow_result.get("collections", []),
            "graph": graph_payload,
            "archive_entry": archive_entry,
            "created_notes": workflow_result.get("created_notes", []),
            "errors": workflow_result.get("errors", {}),
        }

    def load_archive(self) -> list[dict[str, Any]]:
        """Load archived pipeline runs."""
        entries: list[dict[str, Any]] = []
        for run_file in sorted(self.archive_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(run_file.read_text(encoding="utf-8"))
                entries.append(payload)
            except Exception:
                continue
        return entries

    def _create_archive_entry(
        self,
        note_count: int,
        collection_count: int,
        graph_nodes: int,
        graph_edges: int,
        errors: dict[str, str],
    ) -> dict[str, Any]:
        """Create archive entry for this run."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "note_count": note_count,
            "collection_count": collection_count,
            "reference_count": 0,
            "graph_nodes": graph_nodes,
            "graph_edges": graph_edges,
            "errors": errors,
        }

        file_name = datetime.now().strftime("run_%Y%m%d_%H%M%S.json")
        run_file = self.archive_dir / file_name
        run_file.write_text(json.dumps(entry, indent=2), encoding="utf-8")

        return entry

    def _validate_vault_path(self, vault_path: str) -> dict[str, Any]:
        """Validate vault path before parsing. Rejects broad roots like Desktop."""
        if not vault_path or not vault_path.strip():
            return {"error": "Vault path not configured. Set it in Settings."}
        
        path = Path(vault_path).expanduser().resolve()
        if not path.exists():
            return {"error": f"Vault folder does not exist: {vault_path}"}
        
        if not path.is_dir():
            return {"error": f"Vault path is not a directory: {vault_path}"}
        
        # Check if this looks like a root folder
        home = Path.home()
        suspicious_roots = {
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
            home,
        }
        onedrive = home / "OneDrive"
        if onedrive.exists():
            suspicious_roots.add(onedrive)
        
        if path in suspicious_roots:
            return {"error": f"Vault path '{path.name}' is too broad. Please set it to your actual Obsidian vault (e.g., 'tech knowledge')."}
        
        return {"error": None, "path": str(path)}

    def _emit(self, callback: Callable[[Any], None] | None, payload: Any) -> None:
        """Emit progress or status callback."""
        if callback:
            callback(payload)


def ensure_config(app_root: str | Path) -> Path:
    """Ensure config file exists at expected location."""
    root = Path(app_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "config.json"

    if not config_path.exists():
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")

    return config_path


def load_config(config_path: str | Path) -> PipelineConfig:
    """Load pipeline configuration from JSON file."""
    path = Path(config_path)
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")

    payload = json.loads(path.read_text(encoding="utf-8"))
    merged = {**DEFAULT_CONFIG, **payload}

    return PipelineConfig(
        vault_path=str(merged.get("vault_path", "")),
        zotero_library_id=str(merged.get("zotero_library_id", "")),
        zotero_api_key=str(merged.get("zotero_api_key", "")),
        selected_collection_key=str(merged.get("selected_collection_key", "")),
        ollama_model=str(merged.get("ollama_model", "deepseek-ai/deepseek-v3.1")),
        ollama_host=str(merged.get("ollama_host", "https://integrate.api.nvidia.com/v1")),
        zotero_host=str(merged.get("zotero_host", "http://localhost:23119")),
        theme=str(merged.get("theme", "dark")),
    )


def save_config(config_path: str | Path, config: PipelineConfig) -> None:
    """Save pipeline configuration to JSON file."""
    payload = {
        "vault_path": config.vault_path,
        "zotero_library_id": config.zotero_library_id,
        "zotero_api_key": config.zotero_api_key,
        "selected_collection_key": config.selected_collection_key,
        "ollama_model": config.ollama_model,
        "ollama_host": config.ollama_host,
        "zotero_host": config.zotero_host,
        "theme": config.theme,
    }
    Path(config_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
