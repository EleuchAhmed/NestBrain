"""Workflow coordinator for decomposed pipeline stages."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .notebooklm_bridge import NotebookLMBridge
from .ollama_client import OllamaClient
from .obsidian_parser import ObsidianParser
from .paths import get_registry_path
from .registry import PipelineRegistry
from .zotero_sync import ZoteroCollection, ZoteroSyncClient, ZoteroSyncError

from .stages.notebooklm_stage import (
    create_notebook,
    ingest_sources,
    interrogate_notebook,
    generate_media,
)
from .stages.synthesis_stage import run_synthesis
from .stages.notewriter_stage import (
    write_note,
    enrich_vault_notes,
    suggest_semantic_links,
)


class PipelineWorkflow:
    """Coordinates NotebookLM → Synthesis → Note Writing stages."""
    
    def __init__(self, app_root: str | Path) -> None:
        self.app_root = Path(app_root).resolve()
        self.registry_path = get_registry_path()
        self.registry = PipelineRegistry(self.registry_path)
        self.notebooklm: NotebookLMBridge | None = None
    
    async def run_full_pipeline(
        self,
        vault_path: str,
        zotero: ZoteroSyncClient,
        ollama: OllamaClient,
        selected_collection_key: str = "",
        progress_callback: Callable[[int], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Run complete pipeline: vault parsing → Zotero sync → NotebookLM → synthesis → note writing.
        
        Args:
            vault_path: Path to Obsidian vault
            zotero: ZoteroSyncClient instance
            ollama: OllamaClient instance
            selected_collection_key: Optional specific collection to process
            progress_callback: Optional progress callback (0-100)
            status_callback: Optional status callback
            
        Returns:
            Pipeline results {notes, collections, created_notes, errors}
        """
        self._emit(status_callback, "Initializing pipeline")
        self._emit(progress_callback, 5)
        
        # Parse vault
        self._emit(status_callback, "Parsing Obsidian vault")
        parser = ObsidianParser(vault_path)
        notes = parser.parse_vault()
        self._emit(progress_callback, 10)
        
        # Sync Zotero collections
        self._emit(status_callback, "Syncing Zotero collections")
        collections = []
        zotero_error = ""
        try:
            if selected_collection_key:
                self._emit(status_callback, f"Syncing: {selected_collection_key}")
                collections = zotero.sync_collections_by_keys([selected_collection_key])
            else:
                collections = zotero.sync_all()
        except ZoteroSyncError as exc:
            zotero_error = str(exc)
        self._emit(progress_callback, 20)
        
        # Process collections through stages
        created_notes = []
        stage_error = ""
        if collections:
            self._emit(status_callback, "Processing collections...")
            try:
                for idx, collection in enumerate(collections):
                    progress = int(20 + (idx / len(collections)) * 60)
                    self._emit(progress_callback, progress)
                    
                    result = await self.process_collection(
                        collection, vault_path, ollama, status_callback, progress_callback
                    )
                    if result.get("success"):
                        created_notes.append(result)
            except Exception as e:
                stage_error = str(e)
                self._emit(status_callback, f"❌ Pipeline error: {e}")
        
        self._emit(progress_callback, 80)
        
        # Enrich vault notes
        self._emit(status_callback, "Enriching vault notes...")
        try:
            await enrich_vault_notes(notes, ollama, progress_callback, status_callback)
            titles = [note.title for note in notes]
            context = "\n".join(note.summary or note.content[:700] for note in notes[:20])
            semantic_links = await suggest_semantic_links(titles, context, ollama, status_callback)
        except Exception:
            semantic_links = []
        
        self._emit(progress_callback, 100)
        self._emit(status_callback, "Pipeline complete")
        
        return {
            "notes": [asdict(note) for note in notes],
            "collections": [asdict(collection) for collection in collections],
            "created_notes": created_notes,
            "semantic_links": semantic_links,
            "errors": {
                "zotero": zotero_error,
                "pipeline": stage_error,
            },
        }
    
    async def process_collection(
        self,
        collection: ZoteroCollection,
        vault_path: str,
        ollama: OllamaClient,
        status_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[int], None] | None = None,
    ) -> dict[str, Any]:
        """Process a single collection through all pipeline stages.
        
        Stage flow:
        1. NotebookLM: create → ingest → interrogate → media
        2. Synthesis: grounded note + Ollama synthesis
        3. Note Writer: render/merge to vault
        
        Args:
            collection: ZoteroCollection to process
            vault_path: Path to Obsidian vault
            ollama: OllamaClient instance
            status_callback: Optional progress callback
            progress_callback: Optional status callback
            
        Returns:
            {success: bool, note_path?: str, sources_processed?: int, reason?: str}
        """
        try:
            # Initialize NotebookLM bridge if needed
            if not self.notebooklm:
                self.notebooklm = NotebookLMBridge(self.app_root)
            
            # Get registry entry
            reg_entry = self.registry.get_or_create(collection.key, collection.name)
            all_items = collection.items
            all_keys = [item.key for item in all_items]
            
            # --- STAGE 1: NotebookLM ---
            
            # Get or create notebook
            notebook_id = self.registry.get_notebook_id(collection.key)
            if not notebook_id:
                notebook_id = await create_notebook(
                    self.notebooklm, collection.name, status_callback
                )
                self.registry.set_notebook_id(collection.key, notebook_id)
            else:
                self._emit(status_callback, f"📓 Using cached notebook: {collection.name}")
            
            # Ingest sources
            successful_keys = await ingest_sources(
                self.notebooklm, notebook_id, all_items, status_callback
            )
            
            if not successful_keys:
                self._emit(status_callback, f"⚠️ No sources ingested for '{collection.name}'")
                return {"success": False, "reason": "No ingestable sources"}
            
            # Interrogate
            interrogation_responses = await interrogate_notebook(
                self.notebooklm, notebook_id, status_callback
            )
            
            # Generate media
            media_paths = await generate_media(
                self.notebooklm, notebook_id, collection.name, vault_path, status_callback
            )
            
            # --- STAGE 2: Synthesis ---
            
            synthesis = await run_synthesis(
                collection.name,
                notebook_id,
                interrogation_responses,
                self.notebooklm,
                ollama,
                status_callback,
            )
            
            # --- STAGE 3: Note Writer ---
            
            items_dict = [asdict(item) for item in all_items]
            note_path = await write_note(
                collection.name,
                items_dict,
                synthesis,
                media_paths,
                vault_path,
                status_callback,
            )
            
            # Update registry
            self.registry.set_obsidian_path(collection.key, note_path)
            self.registry.mark_processed(collection.key, successful_keys)
            self.registry.save()
            
            return {
                "success": True,
                "note_path": note_path,
                "sources_processed": len(successful_keys),
            }
        
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self._emit(status_callback, f"❌ Collection error: {collection.name}: {e}\n{tb}")
            return {"success": False, "reason": str(e)}
    
    def _emit(self, callback: Callable[[Any], None] | None, payload: Any) -> None:
        """Emit progress or status callback."""
        if callback:
            callback(payload)
