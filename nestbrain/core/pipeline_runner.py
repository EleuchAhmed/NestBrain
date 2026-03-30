from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

from .knowledge_graph import KnowledgeGraphBuilder
from .obsidian_parser import ObsidianNote, ObsidianParser
from .ollama_client import OllamaClient, OllamaClientError
from .zotero_sync import ZoteroCollection, ZoteroSyncClient, ZoteroSyncError


DEFAULT_CONFIG: dict[str, Any] = {
    "vault_path": "",
    "zotero_library_id": "",
    "selected_collection_key": "",
    "ollama_model": "mistral",
    "ollama_host": "http://localhost:11434",
    "zotero_host": "http://localhost:23119",
    "theme": "dark",
}


@dataclass(slots=True)
class PipelineConfig:
    vault_path: str
    zotero_library_id: str
    selected_collection_key: str
    ollama_model: str
    ollama_host: str
    zotero_host: str
    theme: str


class PipelineRunner:
    """Orchestrates Obsidian parsing, Zotero sync, Ollama enrichment, and graph generation."""

    def __init__(self, app_root: str | Path) -> None:
        self.app_root = Path(app_root).resolve()
        self.archive_dir = self.app_root / "runs"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        config: PipelineConfig,
        progress_callback: Callable[[int], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        self._emit(status_callback, "Initializing pipeline")
        self._emit(progress_callback, 5)

        parser = ObsidianParser(config.vault_path)
        zotero = ZoteroSyncClient(host=config.zotero_host, library_id=config.zotero_library_id)
        ollama = OllamaClient(host=config.ollama_host, model=config.ollama_model)
        graph_builder = KnowledgeGraphBuilder()

        self._emit(status_callback, "Parsing Obsidian vault")
        notes = parser.parse_vault()
        self._emit(progress_callback, 20)

        self._emit(status_callback, "Syncing Zotero collections")
        collections: list[ZoteroCollection] = []
        zotero_error = ""
        try:
            selected_key = config.selected_collection_key.strip()
            if selected_key:
                self._emit(status_callback, f"Syncing Zotero collection: {selected_key}")
                collections = zotero.sync_collections_by_keys([selected_key])
            else:
                collections = zotero.sync_all()
        except ZoteroSyncError as exc:
            zotero_error = str(exc)
        self._emit(progress_callback, 40)

        self._emit(status_callback, "Running local AI synthesis with Ollama")
        semantic_link_candidates: list[dict[str, str]] = []
        ollama_error = ""

        try:
            self._enrich_notes(notes, ollama, progress_callback)
            titles = [note.title for note in notes]
            context_blob = "\n".join(note.summary or note.content[:700] for note in notes[:20])
            semantic_link_candidates = ollama.suggest_links(titles, context_blob)
        except OllamaClientError as exc:
            ollama_error = str(exc)
        self._emit(progress_callback, 75)

        self._emit(status_callback, "Building knowledge graph")
        graph_payload = graph_builder.build(notes, collections, semantic_links=semantic_link_candidates)
        self._emit(progress_callback, 92)

        archive_entry = self._create_archive_entry(
            notes=notes,
            collections=collections,
            graph_payload=graph_payload,
            errors={
                "zotero": zotero_error,
                "ollama": ollama_error,
            },
        )
        self._emit(progress_callback, 100)
        self._emit(status_callback, "Pipeline complete")

        return {
            "notes": [asdict(note) for note in notes],
            "collections": [asdict(collection) for collection in collections],
            "graph": graph_payload,
            "archive_entry": archive_entry,
            "errors": {
                "zotero": zotero_error,
                "ollama": ollama_error,
            },
        }

    def load_archive(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for run_file in sorted(self.archive_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(run_file.read_text(encoding="utf-8"))
                entries.append(payload)
            except Exception:
                continue
        return entries

    def _enrich_notes(
        self,
        notes: list[ObsidianNote],
        ollama: OllamaClient,
        progress_callback: Callable[[int], None] | None,
    ) -> None:
        if not notes:
            return

        max_notes = min(len(notes), 40)
        for index, note in enumerate(notes[:max_notes]):
            note.summary = ollama.summarize_text(note.content)
            note.semantic_tags = ollama.generate_semantic_tags(note.content)
            relative = (index + 1) / max_notes
            self._emit(progress_callback, int(40 + relative * 30))

    def _create_archive_entry(
        self,
        notes: list[ObsidianNote],
        collections: list[ZoteroCollection],
        graph_payload: dict[str, Any],
        errors: dict[str, str],
    ) -> dict[str, Any]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "note_count": len(notes),
            "collection_count": len(collections),
            "reference_count": sum(len(collection.items) for collection in collections),
            "graph_nodes": len(graph_payload.get("nodes", [])),
            "graph_edges": len(graph_payload.get("edges", [])),
            "errors": errors,
        }

        file_name = datetime.now().strftime("run_%Y%m%d_%H%M%S.json")
        run_file = self.archive_dir / file_name
        run_file.write_text(json.dumps(entry, indent=2), encoding="utf-8")

        return entry

    def _emit(self, callback: Callable[[Any], None] | None, payload: Any) -> None:
        if callback:
            callback(payload)


def ensure_config(app_root: str | Path) -> Path:
    root = Path(app_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    config_path = root / "config.json"

    if not config_path.exists():
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")

    return config_path


def load_config(config_path: str | Path) -> PipelineConfig:
    path = Path(config_path)
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")

    payload = json.loads(path.read_text(encoding="utf-8"))
    merged = {**DEFAULT_CONFIG, **payload}

    return PipelineConfig(
        vault_path=str(merged.get("vault_path", "")),
        zotero_library_id=str(merged.get("zotero_library_id", "")),
        selected_collection_key=str(merged.get("selected_collection_key", "")),
        ollama_model=str(merged.get("ollama_model", "mistral")),
        ollama_host=str(merged.get("ollama_host", "http://localhost:11434")),
        zotero_host=str(merged.get("zotero_host", "http://localhost:23119")),
        theme=str(merged.get("theme", "dark")),
    )


def save_config(config_path: str | Path, config: PipelineConfig) -> None:
    payload = {
        "vault_path": config.vault_path,
        "zotero_library_id": config.zotero_library_id,
        "selected_collection_key": config.selected_collection_key,
        "ollama_model": config.ollama_model,
        "ollama_host": config.ollama_host,
        "zotero_host": config.zotero_host,
        "theme": config.theme,
    }
    Path(config_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
