from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .notebooklm_auth import _get_auth_file_path, has_cached_auth_tokens
from .pipeline_runner import PipelineConfig, PipelineRunner
from .zotero_sync import ZoteroCollection, ZoteroItem, ZoteroSyncClient


class NestbrainAppService:
    """Thin application service facade for UI and worker coordination."""

    def __init__(self, app_root: str | Path) -> None:
        self.app_root = Path(app_root).resolve()
        self._runner = PipelineRunner(self.app_root)

    def validate_vault_path(self, vault_path: str) -> dict[str, Any]:
        return self._runner.validate_vault_path(vault_path)

    def run_pipeline(
        self,
        config: PipelineConfig,
        progress_callback: Callable[[int], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        return self._runner.run(config, progress_callback=progress_callback, status_callback=status_callback)

    def load_archive(self) -> list[dict[str, Any]]:
        return self._runner.load_archive()

    def create_collection(self, config: PipelineConfig, name: str) -> ZoteroCollection:
        client = self._create_zotero_client(config)
        return client.create_collection(name)

    def get_collection_items(self, config: PipelineConfig, collection_key: str) -> list[dict[str, Any]]:
        client = self._create_zotero_client(config)
        return [asdict(item) for item in client.get_items_for_collection(collection_key)]

    def sync_collections(self, config: PipelineConfig) -> list[dict[str, Any]]:
        client = self._create_zotero_client(config)
        return [asdict(collection) for collection in client.sync_all()]

    def startup_health_check(self, config: PipelineConfig) -> list[str]:
        issues: list[str] = []

        vault_validation = self.validate_vault_path(config.vault_path)
        if vault_validation.get("error"):
            issues.append(vault_validation["error"])

        if not config.nvidia_api_key.strip():
            issues.append("NVIDIA API key is missing.")

        if not config.zotero_library_id.strip():
            issues.append("Zotero library ID is missing.")

        auth_file = _get_auth_file_path()
        if not auth_file.exists():
            issues.append("NotebookLM auth cache is missing.")
        elif not has_cached_auth_tokens():
            issues.append("NotebookLM auth cache is invalid or incomplete. Please re-authenticate.")

        return issues

    def _create_zotero_client(self, config: PipelineConfig) -> ZoteroSyncClient:
        return ZoteroSyncClient(
            host=config.zotero_host,
            library_id=config.zotero_library_id,
            api_key=config.zotero_api_key,
        )
