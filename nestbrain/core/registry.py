"""Registry for tracking processed Zotero sources per collection."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class CollectionRegistryEntry:
    """Track state for a single Zotero collection."""
    
    name: str
    notebook_id: str = ""
    obsidian_path: str = ""
    processed_sources: list[str] = field(default_factory=list)
    media_paths: dict[str, str] = field(default_factory=dict)  # type -> path
    last_updated: str = ""


class PipelineRegistry:
    """Persistence layer for collection processing state."""

    def __init__(self, registry_file: str | Path):
        self.registry_file = Path(registry_file)
        self.data: dict[str, CollectionRegistryEntry] = {}
        self.load()

    def load(self) -> None:
        """Load registry from disk."""
        if not self.registry_file.exists():
            self.data = {}
            return
        
        try:
            raw = json.loads(self.registry_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Registry must be a JSON object")
            self.data = {
                key: CollectionRegistryEntry(**value)
                for key, value in raw.items()
            }
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # Log corruption but continue with empty registry
            print(f"Warning: Registry file corrupted, resetting. Error: {e}")
            self.data = {}

    def save(self) -> None:
        """Save registry to disk."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        raw = {key: asdict(entry) for key, entry in self.data.items()}
        self.registry_file.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def get_or_create(self, collection_key: str, collection_name: str) -> CollectionRegistryEntry:
        """Get existing or create new registry entry."""
        if collection_key not in self.data:
            self.data[collection_key] = CollectionRegistryEntry(name=collection_name)
        return self.data[collection_key]

    def mark_processed(self, collection_key: str, source_keys: list[str]) -> None:
        """Mark source keys as processed for a collection."""
        if collection_key in self.data:
            current = set(self.data[collection_key].processed_sources)
            current.update(source_keys)
            self.data[collection_key].processed_sources = sorted(current)
            self.data[collection_key].last_updated = datetime.now().isoformat()

    def get_new_sources(self, collection_key: str, all_source_keys: list[str]) -> list[str]:
        """Get list of new sources not yet processed."""
        if collection_key not in self.data:
            return all_source_keys
        
        processed = set(self.data[collection_key].processed_sources)
        return [key for key in all_source_keys if key not in processed]

    def get_notebook_id(self, collection_key: str) -> str:
        """Get cached notebook ID for this collection."""
        entry = self.data.get(collection_key)
        return entry.notebook_id if entry else ""

    def set_notebook_id(self, collection_key: str, notebook_id: str) -> None:
        """Cache notebook ID for this collection."""
        if collection_key not in self.data:
            self.data[collection_key] = CollectionRegistryEntry(name="Unknown")
        self.data[collection_key].notebook_id = notebook_id

    def set_obsidian_path(self, collection_key: str, path: str) -> None:
        """Cache Obsidian note path for this collection."""
        if collection_key in self.data:
            self.data[collection_key].obsidian_path = path

    def set_media_path(self, collection_key: str, media_type: str, path: str) -> None:
        """Cache media artifact path (audio/video)."""
        if collection_key in self.data:
            self.data[collection_key].media_paths[media_type] = path
