"""Registry for tracking processed Zotero sources per collection."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .utils import to_slug

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CollectionRegistryEntry:
    """Track state for a single Zotero collection."""
    
    name: str
    notebook_id: str = ""
    note_path: str = ""
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
            registry_text = self.registry_file.read_text(encoding="utf-8")
            raw = json.loads(registry_text)
            if not isinstance(raw, dict):
                raise ValueError("Registry must be a JSON object")

            migrated_raw, migrated = self._migrate_legacy_keys(raw)
            self.data = {
                key: CollectionRegistryEntry(**value)
                for key, value in migrated_raw.items()
            }

            if migrated:
                self.save()
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # Log corruption as a critical error but continue with empty registry
            logger.error("CRITICAL: Registry file corrupted, resetting database. Persistent errors may indicate disk issues: %s", e)
            self._backup_corrupted_registry()
            self.data = {}

    def save(self) -> None:
        """Save registry to disk safely using an atomic write."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        raw = {key: asdict(entry) for key, entry in self.data.items()}
        
        temp_file = self.registry_file.with_suffix('.tmp')
        try:
            temp_file.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            temp_file.replace(self.registry_file)
        except Exception as e:
            logger.error("CRITICAL: Failed to write registry to disk: %s", e)
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise

    def get_or_create(self, collection_slug: str, collection_name: str) -> CollectionRegistryEntry:
        """Get existing or create new registry entry."""
        resolved_slug = self._resolve_slug_key(collection_slug)
        if resolved_slug not in self.data:
            self.data[resolved_slug] = CollectionRegistryEntry(name=collection_name)
        else:
            self.data[resolved_slug].name = collection_name
        return self.data[resolved_slug]

    def mark_processed(self, collection_slug: str, source_keys: list[str]) -> None:
        """Mark source keys as processed for a collection."""
        resolved_slug = self._resolve_slug_key(collection_slug)
        if resolved_slug in self.data:
            current = set(self.data[resolved_slug].processed_sources)
            current.update(source_keys)
            self.data[resolved_slug].processed_sources = sorted(current)
            self.data[resolved_slug].last_updated = datetime.now().isoformat()

    def get_new_sources(self, collection_slug: str, all_source_keys: list[str]) -> list[str]:
        """Get list of new sources not yet processed."""
        resolved_slug = self._resolve_slug_key(collection_slug)
        if resolved_slug not in self.data:
            return all_source_keys
        
        processed = set(self.data[resolved_slug].processed_sources)
        return [key for key in all_source_keys if key not in processed]

    def get_notebook_id(self, collection_slug: str) -> str:
        """Get cached notebook ID for this collection."""
        resolved_slug = self._resolve_slug_key(collection_slug)
        entry = self.data.get(resolved_slug)
        return entry.notebook_id if entry else ""

    def set_notebook_id(self, collection_slug: str, notebook_id: str) -> None:
        """Cache notebook ID for this collection."""
        resolved_slug = self._resolve_slug_key(collection_slug)
        if resolved_slug not in self.data:
            self.data[resolved_slug] = CollectionRegistryEntry(name="Unknown")
        self.data[resolved_slug].notebook_id = notebook_id

    def set_note_path(self, collection_slug: str, path: str) -> None:
        """Cache note path for this collection."""
        resolved_slug = self._resolve_slug_key(collection_slug)
        if resolved_slug in self.data:
            self.data[resolved_slug].note_path = path

    def set_media_path(self, collection_slug: str, media_type: str, path: str) -> None:
        """Cache media artifact path (audio/video)."""
        resolved_slug = self._resolve_slug_key(collection_slug)
        if resolved_slug in self.data:
            self.data[resolved_slug].media_paths[media_type] = path

    def _migrate_legacy_keys(self, raw: dict[str, object]) -> tuple[dict[str, dict[str, object]], bool]:
        """Migrate legacy registry keys to slug form once on startup."""
        migrated = False
        normalized: dict[str, dict[str, object]] = {}

        for key, value in raw.items():
            if not isinstance(value, dict):
                migrated = True
                continue

            payload = dict(value)
            display_name = str(payload.get("name") or "").strip() or str(key).strip() or "Untitled Collection"
            payload["name"] = display_name
            slug_key = to_slug(display_name)

            if key != slug_key or " " in key:
                migrated = True

            existing = normalized.get(slug_key)
            if existing is not None:
                migrated = True
                existing_sources = set(existing.get("processed_sources", []) or [])
                incoming_sources = set(payload.get("processed_sources", []) or [])
                payload["processed_sources"] = sorted(existing_sources.union(incoming_sources))

                payload["notebook_id"] = str(existing.get("notebook_id") or payload.get("notebook_id") or "")
                legacy_key = "".join(("ob", "sidian", "_path"))
                payload["note_path"] = str(existing.get("note_path") or payload.get("note_path") or existing.get(legacy_key) or payload.get(legacy_key) or "")

                existing_media = existing.get("media_paths") if isinstance(existing.get("media_paths"), dict) else {}
                incoming_media = payload.get("media_paths") if isinstance(payload.get("media_paths"), dict) else {}
                payload["media_paths"] = {**existing_media, **incoming_media}

                payload["last_updated"] = str(existing.get("last_updated") or payload.get("last_updated") or "")

            normalized[slug_key] = payload

        return normalized, migrated

    def _resolve_slug_key(self, collection_slug: str) -> str:
        """Resolve slug key and migrate older key forms lazily on first access."""
        requested_slug = to_slug(collection_slug)
        if requested_slug in self.data:
            return requested_slug

        for existing_key, entry in list(self.data.items()):
            if to_slug(entry.name) != requested_slug:
                continue
            if existing_key == requested_slug:
                return requested_slug
            self.data[requested_slug] = entry
            del self.data[existing_key]
            self.save()
            return requested_slug

        return requested_slug

    def _backup_corrupted_registry(self) -> None:
        """Persist a backup of a corrupted registry file for forensic debugging."""
        if not self.registry_file.exists():
            return
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = self.registry_file.with_name(f"pipeline-registry.corrupt_{timestamp}.json")
            backup.write_text(self.registry_file.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception as e:
            logger.error("CRITICAL: Failed to backup corrupted registry at %s. Error: %s", self.registry_file, e)
