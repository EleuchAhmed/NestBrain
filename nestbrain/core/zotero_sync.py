from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import os
import time
from typing import Any
from urllib.parse import urlparse

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

    def __init__(
        self,
        host: str = "http://localhost:23119",
        library_id: str = "",
        api_key: str = "",
        timeout: int = 15,
        retries: int = 3,
        backoff_seconds: float = 0.5,
    ) -> None:
        self.host = host.rstrip("/")
        self.library_id = library_id.strip()
        self.api_key = (api_key or os.getenv("ZOTERO_API_KEY", "")).strip()
        self.timeout = timeout
        self.retries = max(1, retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.session = requests.Session()

    def check_connection(self) -> bool:
        try:
            _ = self.get_collections()
            return True
        except ZoteroSyncError:
            return False

    def get_collections(self) -> list[ZoteroCollection]:
        endpoint_options: list[str] = []
        for scope in self._library_scopes():
            endpoint_options.append(f"/api/{scope}/collections?format=json")
        endpoint_options.append("/api/collections?format=json")

        data = self._request_json(endpoint_options)

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
        endpoint_options: list[str] = []
        for scope in self._library_scopes():
            endpoint_options.append(f"/api/{scope}/collections/{collection_key}/items/top?format=json")
        endpoint_options.extend(
            [
                f"/api/collections/{collection_key}/items/top?format=json",
                f"/api/items?collection={collection_key}&format=json",
            ]
        )
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

    def create_collection(self, name: str, parent_collection_key: str = "") -> ZoteroCollection:
        clean_name = name.strip()
        if not clean_name:
            raise ZoteroSyncError("Collection name cannot be empty")

        payload: dict[str, Any] = {"name": clean_name}
        if parent_collection_key.strip():
            payload["parentCollection"] = parent_collection_key.strip()

        try:
            response_payload = self._post_json(
                [f"/api/{scope}/collections" for scope in self._library_scopes()] + ["/api/collections"],
                [payload, [payload]],
            )
        except ZoteroSyncError as local_error:
            response_payload = self._create_collection_via_web_api(payload, local_error)

        created_key = self._extract_created_key(response_payload)
        collections = self.get_collections()

        if created_key:
            for collection in collections:
                if collection.key == created_key:
                    return collection

        # Fallback: return most likely match by exact name
        exact_name_matches = [collection for collection in collections if collection.name.strip().lower() == clean_name.lower()]
        if exact_name_matches:
            return exact_name_matches[0]

        return ZoteroCollection(
            key=created_key or "",
            name=clean_name,
            item_count=0,
            last_modified=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="Idle",
        )

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
                response = self._request_with_retry("GET", url, timeout=self.timeout)
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

    def _post_json(self, path_options: list[str], payload_options: list[Any]) -> Any:
        last_error: Exception | None = None
        headers = {"Content-Type": "application/json"}

        for path in path_options:
            url = f"{self.host}{path}"
            for payload in payload_options:
                try:
                    response = self._request_with_retry(
                        "POST",
                        url,
                        json=payload,
                        headers=headers,
                        timeout=self.timeout,
                    )
                    response.raise_for_status()

                    if not response.text.strip():
                        return {}

                    try:
                        return response.json()
                    except ValueError:
                        return {"raw": response.text}
                except requests.RequestException as exc:
                    last_error = exc
                    continue

        raise ZoteroSyncError(f"Unable to create collection in Zotero at {self.host}: {last_error}")

    def _extract_created_key(self, payload: Any) -> str:
        if isinstance(payload, dict):
            for direct_key in ("key", "collectionKey", "id"):
                candidate = str(payload.get(direct_key, "")).strip()
                if candidate:
                    return candidate

            successful = payload.get("successful")
            if isinstance(successful, dict):
                for value in successful.values():
                    candidate = str(value).strip()
                    if candidate:
                        return candidate

            for value in payload.values():
                candidate = self._extract_created_key(value)
                if candidate:
                    return candidate

        if isinstance(payload, list):
            for item in payload:
                candidate = self._extract_created_key(item)
                if candidate:
                    return candidate

        return ""

    def _create_collection_via_web_api(self, payload: dict[str, Any], local_error: Exception) -> Any:
        library_scope = self._primary_remote_library_scope()
        if not library_scope:
            raise ZoteroSyncError(
                "Local Zotero API does not support creating collections here, and no Zotero library ID is set. "
                "Set 'Zotero Library ID' in Settings (e.g., users/123456 or groups/98765)."
            ) from local_error

        if not self.api_key:
            raise ZoteroSyncError(
                "Local Zotero API is read-only for collection creation. "
                "Provide a write-enabled Zotero API key in Settings to create collections via zotero.org."
            ) from local_error

        url = f"https://api.zotero.org/{library_scope}/collections"
        headers = {
            "Zotero-API-Key": self.api_key,
            "Zotero-API-Version": "3",
            "Content-Type": "application/json",
        }

        # Zotero Web API expects an array of collection objects.
        body = [payload]

        try:
            response = self._request_with_retry(
                "POST",
                url,
                json=body,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            if not response.text.strip():
                return {}
            try:
                return response.json()
            except ValueError:
                return {"raw": response.text}
        except requests.RequestException as exc:
            raise ZoteroSyncError(
                f"Failed to create collection via Zotero Web API ({library_scope}): {exc}"
            ) from exc

    def _primary_remote_library_scope(self) -> str:
        for scope in self._library_scopes():
            if scope.startswith("users/") and scope != "users/0":
                return scope
            if scope.startswith("groups/"):
                return scope
        return ""

    def _normalize_modified(self, payload: dict[str, Any]) -> str:
        modified = payload.get("dateModified") or payload.get("lastModified")
        if isinstance(modified, str) and modified.strip():
            return modified.strip()
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _library_scopes(self) -> list[str]:
        raw = self.library_id.strip()
        scopes: list[str] = []

        def add_scope(scope: str) -> None:
            clean = scope.strip().strip("/")
            if clean and clean not in scopes:
                scopes.append(clean)

        if raw:
            lowered = raw.lower()

            if lowered.startswith("http://") or lowered.startswith("https://"):
                parsed = urlparse(raw)
                parts = [part for part in parsed.path.split("/") if part]
                for idx, part in enumerate(parts):
                    token = part.lower()
                    if token in {"users", "groups"} and idx + 1 < len(parts):
                        identifier = parts[idx + 1].strip()
                        if identifier:
                            add_scope(f"{token}/{identifier}")

            if lowered.startswith("users/") or lowered.startswith("groups/"):
                add_scope(lowered)

            if raw.isdigit():
                add_scope(f"users/{raw}")
                add_scope(f"groups/{raw}")

        add_scope("users/0")
        return scopes

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Send an HTTP request with simple exponential backoff for transient failures."""
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                return self.session.request(method=method, url=url, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                if attempt == self.retries - 1:
                    break
                sleep_for = self.backoff_seconds * (2 ** attempt)
                if sleep_for > 0:
                    time.sleep(sleep_for)

        raise ZoteroSyncError(f"Request failed after retries for {url}: {last_error}")
