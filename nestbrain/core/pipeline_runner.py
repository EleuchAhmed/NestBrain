"""Pipeline orchestrator: delegates to workflow coordinator stages."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

from .knowledge_graph import KnowledgeGraphBuilder
from .note_parser import MarkdownNote
from .ollama_client import NvidiaLLMClient
from .paths import get_config_path, get_runs_dir
from .vault_manager import audit_unclassified_notes
from .zotero_sync import ZoteroCollection, ZoteroItem, ZoteroSyncClient, ZoteroSyncError
from .workflow_engine import PipelineWorkflow


DEFAULT_CONFIG: dict[str, Any] = {
    "vault_path": "",
    "vault_initialized": False,
    "zotero_library_id": "",
    "zotero_api_key": "",
    "selected_collection_key": "",
    "nvidia_api_key": "",
    "ollama_host": "https://integrate.api.nvidia.com/v1",
    "zotero_host": "http://localhost:23119",
    "theme": "dark",
}


@dataclass(slots=True)
class PipelineConfig:
    vault_path: str
    vault_initialized: bool
    zotero_library_id: str
    zotero_api_key: str
    selected_collection_key: str
    nvidia_api_key: str
    ollama_host: str
    zotero_host: str
    theme: str


class PipelineRunner:
    """Orchestrates pipeline via workflow stages: NotebookLM → Synthesis → Note Writing."""

    def __init__(self, app_root: str | Path) -> None:
        self.app_root = Path(app_root).resolve()
        self.archive_dir = get_runs_dir()
        
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
        ollama = NvidiaLLMClient(host=config.ollama_host, api_key=config.nvidia_api_key)
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
        notes = self._coerce_notes(workflow_result.get("notes", []))
        collections = self._coerce_collections(workflow_result.get("collections", []))
        graph_payload = graph_builder.build(
            notes=notes,
            collections=collections,
            semantic_links=workflow_result.get("semantic_links", [])
        )
        
        # Create archive entry
        archive_entry = self._create_archive_entry(
            note_count=len(workflow_result.get("notes", [])),
            collection_count=len(workflow_result.get("collections", [])),
            graph_nodes=len(graph_payload.get("nodes", [])),
            graph_edges=len(graph_payload.get("edges", [])),
            errors=workflow_result.get("errors", {}),
            classification_audit=audit_unclassified_notes(config.vault_path),
        )
        
        self._emit(progress_callback, 100)
        self._emit(status_callback, "Pipeline complete")
        
        return {
            "notes": workflow_result.get("notes", []),
            "collections": workflow_result.get("collections", []),
            "graph": graph_payload,
            "archive_entry": archive_entry,
            "classification_audit": archive_entry.get("classification_audit", {}),
            "created_notes": workflow_result.get("created_notes", []),
            "errors": workflow_result.get("errors", {}),
        }

    def _coerce_notes(self, payload: list[Any]) -> list[MarkdownNote]:
        notes: list[MarkdownNote] = []
        for item in payload:
            if isinstance(item, MarkdownNote):
                notes.append(item)
                continue
            if not isinstance(item, dict):
                continue
            notes.append(
                MarkdownNote(
                    path=str(item.get("path", "")),
                    title=str(item.get("title", "Untitled")),
                    tags=[str(tag) for tag in item.get("tags", []) if str(tag).strip()],
                    wikilinks=[str(link) for link in item.get("wikilinks", []) if str(link).strip()],
                    last_modified=str(item.get("last_modified", "")),
                    metadata=item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {},
                    content=str(item.get("content", "")),
                    summary=str(item.get("summary", "")),
                    semantic_tags=[str(tag) for tag in item.get("semantic_tags", []) if str(tag).strip()],
                )
            )
        return notes

    def _coerce_collections(self, payload: list[Any]) -> list[ZoteroCollection]:
        collections: list[ZoteroCollection] = []
        for item in payload:
            if isinstance(item, ZoteroCollection):
                collections.append(item)
                continue
            if not isinstance(item, dict):
                continue

            raw_items = item.get("items", [])
            parsed_items: list[ZoteroItem] = []
            for source in raw_items if isinstance(raw_items, list) else []:
                if isinstance(source, ZoteroItem):
                    parsed_items.append(source)
                    continue
                if not isinstance(source, dict):
                    continue
                parsed_items.append(
                    ZoteroItem(
                        key=str(source.get("key", "")),
                        title=str(source.get("title", "Untitled Reference")),
                        item_type=str(source.get("item_type", "item")),
                        creators=[str(creator) for creator in source.get("creators", []) if str(creator).strip()],
                        date=str(source.get("date", "")),
                        url=str(source.get("url", "")),
                        abstract=str(source.get("abstract", "")),
                        collection_key=str(source.get("collection_key", "")),
                    )
                )

            collections.append(
                ZoteroCollection(
                    key=str(item.get("key", "")),
                    name=str(item.get("name") or item.get("display_name") or "Untitled Collection"),
                    slug=str(item.get("slug", "")),
                    display_name=str(item.get("display_name", "")),
                    item_count=int(item.get("item_count", len(parsed_items)) or len(parsed_items)),
                    last_modified=str(item.get("last_modified", "")),
                    status=str(item.get("status", "Idle")),
                    items=parsed_items,
                )
            )
        return collections

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
        classification_audit: dict[str, Any] | None = None,
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
            "classification_audit": classification_audit or {"has_unclassified": False, "count": 0, "notes": []},
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
            return {"error": f"Vault path '{path.name}' is too broad. Please set it to your actual note vault (e.g., 'tech knowledge')."}

        # Ensure the app can write output files into this vault.
        try:
            probe = path / ".nestbrain-write-test.tmp"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except Exception as exc:
            return {"error": f"Vault path is not writable: {exc}"}
        
        return {"error": None, "path": str(path)}

    def validate_vault_path(self, vault_path: str) -> dict[str, Any]:
        """Public wrapper so UI does not rely on private implementation details."""
        return self._validate_vault_path(vault_path)

    def _emit(self, callback: Callable[[Any], None] | None, payload: Any) -> None:
        """Emit progress or status callback."""
        if callback:
            callback(payload)


def ensure_config(app_root: str | Path) -> Path:
    """Ensure config file exists at expected location."""
    _ = Path(app_root).resolve()  # Kept for backward-compatible call sites.
    config_path = get_config_path()

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
            vault_initialized=bool(merged.get("vault_initialized", False)),
        zotero_library_id=str(merged.get("zotero_library_id", "")),
        zotero_api_key=str(merged.get("zotero_api_key", "")),
        selected_collection_key=str(merged.get("selected_collection_key", "")),
        nvidia_api_key=str(merged.get("nvidia_api_key", "")),
        ollama_host=str(merged.get("ollama_host", "https://integrate.api.nvidia.com/v1")),
        zotero_host=str(merged.get("zotero_host", "http://localhost:23119")),
        theme=str(merged.get("theme", "dark")),
    )


def save_config(config_path: str | Path, config: PipelineConfig) -> None:
    """Save pipeline configuration to JSON file."""
    payload = {
        "vault_path": config.vault_path,
        "vault_initialized": config.vault_initialized,
        "zotero_library_id": config.zotero_library_id,
        "zotero_api_key": config.zotero_api_key,
        "selected_collection_key": config.selected_collection_key,
        "nvidia_api_key": config.nvidia_api_key,
        "ollama_host": config.ollama_host,
        "zotero_host": config.zotero_host,
        "theme": config.theme,
    }
    Path(config_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
