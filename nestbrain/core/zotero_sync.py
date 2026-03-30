from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import requests


class ZoteroSyncError(Exception):
    pass


@dataclass(slots=True)
class ZoteroItem:
    key: str
    title: str
    item_type: str
    creators: list[str] = field(default_factory=list)
    date: str = ""
    url: str = ""
    abstract: str = ""
    collection_key: str = ""


@dataclass(slots=True)
class ZoteroCollection:
    key: str
    name: str
    item_count: int
    last_modified: str
    status: str = "Idle"
    items: list[ZoteroItem] = field(default_factory=list)


class ZoteroSyncClient:
    """Connector for local Zotero API (default host: http://localhost:23119/api)."""

    def __init__(self, host: str = "http://localhost:23119", library_id: str = "", timeout: int = 15) -> None:
        self.host = host.rstrip("/")
        self.library_id = library_id.strip()
        self.timeout = timeout

    def check_connection(self) -> bool:
        try:
            _ = self.get_collections()
            return True
        except ZoteroSyncError:
            return False

    def get_collections(self) -> list[ZoteroCollection]:
        data = self._request_json(
            [
                "/api/users/0/collections?format=json",
                "/api/collections?format=json",
            ]
        )

        collections: list[ZoteroCollection] = []
        for raw in data:
            payload = raw.get("data", raw) if isinstance(raw, dict) else {}
            key = str(payload.get("key", "")).strip()
            name = str(payload.get("name") or payload.get("collectionName") or "Untitled Collection")
            item_count = int(payload.get("numItems", 0) or 0)
            modified = self._normalize_modified(payload)
            if key:
                collections.append(
                    ZoteroCollection(
                        key=key,
                        name=name,
                        item_count=item_count,
                        last_modified=modified,
                        status="Idle",
                    )
                )

        return sorted(collections, key=lambda collection: collection.name.lower())

    def get_items_for_collection(self, collection_key: str) -> list[ZoteroItem]:
        endpoint_options = [
            f"/api/users/0/collections/{collection_key}/items/top?format=json",
            f"/api/collections/{collection_key}/items/top?format=json",
            f"/api/items?collection={collection_key}&format=json",
        ]
        data = self._request_json(endpoint_options)

        items: list[ZoteroItem] = []
        for raw in data:
            payload = raw.get("data", raw) if isinstance(raw, dict) else {}
            key = str(payload.get("key", "")).strip()
            if not key:
                continue

            # Filter out child items (attachments, notes) to get only top-level research items
            item_type = str(payload.get("itemType", "item")).lower()
            if item_type in ("attachment", "note"):
                continue

            creators: list[str] = []
            for creator in payload.get("creators", []):
                if not isinstance(creator, dict):
                    continue
                first_name = str(creator.get("firstName", "")).strip()
                last_name = str(creator.get("lastName", "")).strip()
                combined = f"{first_name} {last_name}".strip()
                if combined:
                    creators.append(combined)

            items.append(
                ZoteroItem(
                    key=key,
                    title=str(payload.get("title") or "Untitled Reference"),
                    item_type=item_type,
                    creators=creators,
                    date=str(payload.get("date") or ""),
                    url=str(payload.get("url") or ""),
                    abstract=str(payload.get("abstractNote") or ""),
                    collection_key=collection_key,
                )
            )

        return items

    def sync_all(self) -> list[ZoteroCollection]:
        collections = self.get_collections()
        return self._sync_collection_objects(collections)

    def sync_collections_by_keys(self, collection_keys: list[str]) -> list[ZoteroCollection]:
        requested = {key.strip() for key in collection_keys if key.strip()}
        if not requested:
            return self.sync_all()

        available = self.get_collections()
        filtered = [collection for collection in available if collection.key in requested]
        if not filtered:
            raise ZoteroSyncError(f"No matching Zotero collections for keys: {', '.join(sorted(requested))}")

        return self._sync_collection_objects(filtered)

    def _sync_collection_objects(self, collections: list[ZoteroCollection]) -> list[ZoteroCollection]:
        for collection in collections:
            collection.status = "Syncing"
            items = self.get_items_for_collection(collection.key)
            collection.items = items
            collection.item_count = len(items)
            collection.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            collection.status = "Idle"

        return collections

    def _request_json(self, path_options: list[str]) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for path in path_options:
            url = f"{self.host}{path}"
            try:
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    return payload
                if isinstance(payload, dict):
                    return [payload]
                return []
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                continue

        raise ZoteroSyncError(f"Unable to fetch from Zotero local API at {self.host}: {last_error}")

    def _normalize_modified(self, payload: dict[str, Any]) -> str:
        modified = payload.get("dateModified") or payload.get("lastModified")
        if isinstance(modified, str) and modified.strip():
            return modified.strip()
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
