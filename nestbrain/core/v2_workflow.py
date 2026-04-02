"""Workflow coordinator for the NestBrain v2 Pipeline (NVIDIA NIM)."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .notebooklm_bridge import NotebookLMBridge
from .ollama_client import OllamaClient
from .obsidian_parser import ObsidianParser
from .registry import PipelineRegistry
from .zotero_sync import ZoteroCollection, ZoteroSyncClient

# V2 Stages
from .stages.question_planner import QuestionPlanner
from .stages.q_and_a_loop import QAndALoop
from .stages.master_synthesizer import MasterSynthesizer
from .stages.entity_extractor import EntityExtractor
from .stages.note_seeder import NoteSeeder
from .stages.vector_indexer import VectorIndexer
from .stages.semantic_auditor import SemanticAuditor
from .stages.connection_annotator import ConnectionAnnotator

logger = logging.getLogger(__name__)

class PipelineWorkflowV2:
    """Coordinates NVIDIA NIM based v2 pipeline."""
    
    def __init__(self, app_root: str | Path) -> None:
        self.app_root = Path(app_root).resolve()
        self.registry_path = self.app_root / "pipeline-registry.json"
        self.registry = PipelineRegistry(self.registry_path)
        self.notebooklm: NotebookLMBridge | None = None
        
        # Instantiate v2 models (NVIDIA APIs)
        self.planner = QuestionPlanner()
        self.synthesizer = MasterSynthesizer()
        self.extractor = EntityExtractor()
        
    async def run_full_pipeline(
        self,
        vault_path: str,
        zotero: ZoteroSyncClient,
        ollama: OllamaClient, # Kept for backward compat / UI
        selected_collection_key: str = "",
        progress_callback: Callable[[int], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Run complete V2 pipeline"""
        
        self._emit(status_callback, "Initializing V2 NVIDIA pipeline")
        self._emit(progress_callback, 5)

        # Parse vault (legacy logic to get basic graph state if needed)
        parser = ObsidianParser(vault_path)
        notes = parser.parse_vault()
        
        # Initialize V2 Vault classes
        self.seeder = NoteSeeder(vault_path)
        self.indexer = VectorIndexer(vault_path)
        self.auditor = SemanticAuditor(vault_path)
        self.annotator = ConnectionAnnotator(vault_path)
        self._emit(progress_callback, 10)

        # Sync Zotero
        self._emit(status_callback, "Syncing Zotero collections")
        try:
            if selected_collection_key:
                collections = zotero.sync_collections_by_keys([selected_collection_key])
            else:
                collections = zotero.sync_all()
        except Exception as exc:
            return {"errors": {"zotero": str(exc)}}
            
        self._emit(progress_callback, 20)

        created_notes = []
        if collections:
            for idx, collection in enumerate(collections):
                progress = int(20 + (idx / len(collections)) * 60)
                self._emit(progress_callback, progress)
                
                result = await self.process_collection_v2(
                    collection, vault_path, status_callback
                )
                if result.get("success"):
                    created_notes.append(result)

        self._emit(progress_callback, 100)
        self._emit(status_callback, "Pipeline complete")

        return {
            "notes": [asdict(note) for note in notes],
            "collections": [asdict(c) for c in collections],
            "created_notes": created_notes,
            "errors": {},
        }

    async def process_collection_v2(
        self,
        collection: ZoteroCollection,
        vault_path: str,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        try:
            if not self.notebooklm:
                self.notebooklm = NotebookLMBridge(self.app_root)
            
            # Ensure registry entry exists
            self.registry.get_or_create(collection.key, collection.name)
            
            # NotebookLM Setup
            notebook_id = self.registry.get_notebook_id(collection.key)
            if not notebook_id:
                self._emit(status_callback, f"Creating NotebookLM notebook for {collection.name}")
                notebook_id = await self.notebooklm.create_notebook(collection.name)
                self.registry.set_notebook_id(collection.key, notebook_id)
                self.registry.save()
                
                # Ingestion logic
                self._emit(status_callback, f"Ingesting {len(collection.items)} sources into NotebookLM")
                for item in collection.items:
                    # Combine title and abstract as text source
                    source_content = f"Title: {item.title}\n\nAbstract: {item.abstract}"
                    if item.url:
                        source_content += f"\n\nURL: {item.url}"
                    
                    await self.notebooklm.ingest_text(notebook_id, item.title or "Untitled Source", source_content)
                
                self.registry.save()
            # LAYER 1: Research & Synthesis
            self._emit(status_callback, f"L1: Planning Research for {collection.name}")
            
            # 1. Question Planner (Architect)
            taxonomy = self.planner.generate_taxonomy(collection.name)
            
            # 2. Q&A Loop (Researcher)
            self._emit(status_callback, f"L1: Iterative Q&A loops ({len(taxonomy)} paths)")
            qa_loop = QAndALoop(self.notebooklm)
            qa_history = await qa_loop.execute_research(notebook_id, taxonomy)
            
            # 3. Master Synthesis (Author)
            self._emit(status_callback, "L1: Synthesizing Master Note")
            master_note_content = self.synthesizer.synthesize(collection.name, qa_history)
            
            # Save Master Note
            safe_name = collection.name.replace("/", "-").replace(":", " -")
            note_path = Path(vault_path) / f"{safe_name}.md"
            note_path.write_text(master_note_content, encoding="utf-8")

            # LAYER 2: Entity Growth
            self._emit(status_callback, "L2: Extracting knowledge entities")
            entities = self.extractor.extract_entities(master_note_content)
            
            for term in entities:
                self._emit(status_callback, f"L2: Seeding/Patching entity '{term}'")
                self.seeder.process_extracted_term(term, master_note_content, collection.name)

            # LAYER 3: Vault Propagation
            self._emit(status_callback, "L3: Vector Indexing")
            new_vec = self.indexer.embed_new_note(collection.name, master_note_content)
            
            self._emit(status_callback, "L3: Semantic K-NN Search")
            matches = self.indexer.find_similar_notes(new_vec, top_k=5)
            
            self._emit(status_callback, "L3: Auditing Connections")
            survivors = self.auditor.audit_connections(master_note_content, matches)
            
            self._emit(status_callback, "L3: Cross-annotating Graph")
            self.annotator.annotate_connections(collection.name, master_note_content, survivors)
            
            # Update registry with note path and save
            self.registry.set_obsidian_path(collection.key, str(note_path))
            self.registry.save()

            return {"success": True, "note_path": str(note_path)}

        except Exception as e:
            logger.error(f"Collection processing failed: {e}")
            return {"success": False, "reason": str(e)}

    def _emit(self, callback: Callable[[Any], None] | None, payload: Any) -> None:
        if callback:
            callback(payload)
