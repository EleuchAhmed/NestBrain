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
from .note_renderer import SynthesisResult
from .nvidia_client import nvidia_client

# V2 Stages
from .stages.question_planner import QuestionPlanner
from .stages.q_and_a_loop import QAndALoop
from .stages.master_synthesizer import MasterSynthesizer
from .stages.entity_extractor import EntityExtractor
from .stages.note_seeder import NoteSeeder
from .stages.vector_indexer import VectorIndexer
from .stages.semantic_auditor import SemanticAuditor
from .stages.connection_annotator import ConnectionAnnotator
from .stages.notewriter_stage import write_note

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
        pipeline_warnings: list[str] = []
        if not nvidia_client.is_configured():
            warning = (
                "NVIDIA_API_KEY is missing. Planner/synthesizer/entity extraction may run in fallback mode, "
                "which can reduce note quality."
            )
            pipeline_warnings.append(warning)
            self._emit(status_callback, f"Warning: {warning}")

        if collections:
            for idx, collection in enumerate(collections):
                progress = int(20 + (idx / len(collections)) * 60)
                self._emit(progress_callback, progress)
                
                result = await self.process_collection_v2(
                    collection, vault_path, status_callback
                )
                if result.get("success"):
                    created_notes.append(result)
                if result.get("warnings"):
                    pipeline_warnings.extend(result["warnings"])

        self._emit(progress_callback, 100)
        self._emit(status_callback, "Pipeline complete")

        return {
            "notes": [asdict(note) for note in notes],
            "collections": [asdict(c) for c in collections],
            "created_notes": created_notes,
            "errors": {"warnings": sorted(set(pipeline_warnings))},
        }

    async def process_collection_v2(
        self,
        collection: ZoteroCollection,
        vault_path: str,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        try:
            warnings: list[str] = []
            if not self.notebooklm:
                self.notebooklm = NotebookLMBridge(self.app_root)
            
            # Ensure registry entry exists
            self.registry.get_or_create(collection.key, collection.name)
            all_items = collection.items
            all_keys = [item.key for item in all_items]
            new_source_keys = self.registry.get_new_sources(collection.key, all_keys)
            new_items = [item for item in all_items if item.key in set(new_source_keys)]
            
            # NotebookLM Setup
            notebook_id = self.registry.get_notebook_id(collection.key)
            if not notebook_id:
                self._emit(status_callback, f"Creating NotebookLM notebook for {collection.name}")
                notebook_id = await self.notebooklm.create_notebook(collection.name)
                self.registry.set_notebook_id(collection.key, notebook_id)
                self.registry.save()

            # Ingestion logic always runs for newly discovered sources
            if new_items:
                self._emit(status_callback, f"Ingesting {len(new_items)} new sources into NotebookLM")
                successful_keys: list[str] = []
                for idx, item in enumerate(new_items):
                    print(f"DEBUG:V2:INGEST_ITEM_{idx} - Processing item {idx+1}/{len(new_items)}: {item.title[:50]}")
                    source_content = f"Title: {item.title}\n\nAbstract: {item.abstract}"
                    if item.url:
                        source_content += f"\n\nURL: {item.url}"
                    print(f"DEBUG:V2:INGEST_CALLING_{idx} - About to call ingest_text")
                    ingested = await self.notebooklm.ingest_text(
                        notebook_id,
                        item.title or "Untitled Source",
                        source_content,
                    )
                    print(f"DEBUG:V2:INGEST_COMPLETE_{idx} - ingest_text returned {ingested}")
                    if ingested:
                        successful_keys.append(item.key)
                if successful_keys:
                    self.registry.mark_processed(collection.key, successful_keys)
                    self.registry.save()
                else:
                    msg = f"No new sources ingested successfully for {collection.name}."
                    warnings.append(msg)
                    self._emit(status_callback, f"Warning: {msg}")
            else:
                self._emit(status_callback, f"No new sources to ingest for {collection.name}")

            # LAYER 1: Research & Synthesis
            self._emit(status_callback, f"L1: Planning Research for {collection.name}")
            
            # 1. Question Planner (Architect)
            print(f"DEBUG:V2:CONTEXT_BUILDING - Building context summary from {len(new_items or all_items) or 0} items")
            context_summary = self._build_context_summary(new_items or all_items)
            print(f"DEBUG:V2:CALLING_PLANNER - About to call question_planner.generate_taxonomy")
            # Run the synchronous CPU/IO-bound function in a thread pool to avoid blocking the async event loop
            loop = asyncio.get_event_loop()
            taxonomy = await loop.run_in_executor(
                None,
                lambda: self.planner.generate_taxonomy(collection.name, context_summary)
            )
            print(f"DEBUG:V2:PLANNER_RETURNED - Received {len(taxonomy)} taxonomy questions")
            if self.planner.used_fallback:
                msg = f"Question planner fallback used for {collection.name}: {self.planner.last_error}"
                warnings.append(msg)
                self._emit(status_callback, f"Warning: {msg}")
            
            # 2. Q&A Loop (Researcher)
            self._emit(status_callback, f"L1: Iterative Q&A loops ({len(taxonomy)} paths)")
            print(f"DEBUG:V2:CREATING_QA_LOOP - Creating QAndALoop instance")
            qa_loop = QAndALoop(self.notebooklm)
            print(f"DEBUG:V2:CALLING_QA_LOOP - About to call execute_research with {len(taxonomy)} questions")
            qa_history = await qa_loop.execute_research(notebook_id, taxonomy)
            print(f"DEBUG:V2:QA_LOOP_RETURNED - Received {len(qa_history)} Q&A history entries")
            
            # 3. Master Synthesis (Author)
            self._emit(status_callback, "L1: Synthesizing Master Note")
            master_note_content = self.synthesizer.synthesize(collection.name, qa_history)
            if self.synthesizer.used_fallback:
                msg = f"Master synthesizer fallback used for {collection.name}: {self.synthesizer.last_error}"
                warnings.append(msg)
                self._emit(status_callback, f"Warning: {msg}")

            deep_dive_content = master_note_content
            if self.synthesizer.used_fallback:
                deep_dive_content = self._build_structured_deep_dive(collection.name, qa_history)
            
            # LAYER 2: Entity Growth
            self._emit(status_callback, "L2: Extracting knowledge entities")
            entities = self.extractor.extract_entities(master_note_content)
            if self.extractor.used_fallback:
                msg = f"Entity extractor fallback used for {collection.name}: {self.extractor.last_error}"
                warnings.append(msg)
                self._emit(status_callback, f"Warning: {msg}")
            if not entities:
                msg = f"No entities extracted for {collection.name}; mini-note creation skipped."
                warnings.append(msg)
                self._emit(status_callback, f"Warning: {msg}")
            entities = self._dedupe_entities(entities)
            
            for term in entities:
                self._emit(status_callback, f"L2: Seeding/Patching entity '{term}'")
                self.seeder.process_extracted_term(term, deep_dive_content, collection.name)

            # Save a structured note into the standard vault hierarchy.
            synthesis_payload = SynthesisResult(
                academic_synthesis=(
                    f"# {collection.name}\n\n"
                    "Auto-generated by PipelineWorkflowV2. Detailed synthesis is in the Deep Dive section."
                ),
                conceptual_deep_dive=deep_dive_content,
                actionable_knowledge=self._build_actionable_takeaways(entities),
                knowledge_connections=self._build_knowledge_connections(entities),
                critical_evaluation=self._build_critical_evaluation(qa_history),
                glossary=self._build_glossary(entities),
            )
            items_dict = [asdict(item) for item in all_items]
            note_path = await write_note(
                collection.name,
                items_dict,
                synthesis_payload,
                media_paths={},
                vault_path=vault_path,
                status_callback=status_callback,
            )

            # LAYER 3: Vault Propagation
            self._emit(status_callback, "L3: Vector Indexing")
            new_vec = self.indexer.embed_new_note(collection.name, deep_dive_content)
            
            self._emit(status_callback, "L3: Semantic K-NN Search")
            matches = self.indexer.find_similar_notes(new_vec, top_k=5)
            
            self._emit(status_callback, "L3: Auditing Connections")
            survivors = self.auditor.audit_connections(deep_dive_content, matches)
            
            self._emit(status_callback, "L3: Cross-annotating Graph")
            self.annotator.annotate_connections(collection.name, deep_dive_content, survivors)
            
            # Update registry with note path and save
            self.registry.set_obsidian_path(collection.key, note_path)
            self.registry.save()

            return {"success": True, "note_path": note_path, "warnings": warnings}

        except Exception as e:
            logger.error(f"Collection processing failed: {e}")
            return {"success": False, "reason": str(e)}

    def _build_context_summary(self, items: list[Any]) -> str:
        """Build compact source context to help planner generate less-generic questions."""
        snippets: list[str] = []
        for item in items[:8]:
            title = (getattr(item, "title", "") or "").strip()
            abstract = (getattr(item, "abstract", "") or "").strip()
            if title:
                snippets.append(f"Title: {title}")
            if abstract:
                snippets.append(f"Abstract: {abstract[:320]}")
        return "\n".join(snippets)

    def _dedupe_entities(self, entities: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for entity in entities:
            cleaned = " ".join(entity.split()).strip(" -")
            if len(cleaned) < 3:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
            if len(deduped) >= 30:
                break
        return deduped

    def _build_actionable_takeaways(self, entities: list[str]) -> str:
        if not entities:
            return "- Identify concrete implementation steps from the synthesized deep dive."
        top = entities[:5]
        return "\n".join(f"- Build or revise notes around [[{entity}]]." for entity in top)

    def _build_knowledge_connections(self, entities: list[str]) -> str:
        if not entities:
            return "- No semantic links available yet."
        return "\n".join(f"- [[{entity}]]" for entity in entities[:20])

    def _build_critical_evaluation(self, qa_history: list[dict[str, str]]) -> str:
        if not qa_history:
            return "- No Q&A evidence was produced; validate source ingestion and NotebookLM connectivity."
        return (
            "- Validate claims that appear in only one source.\n"
            "- Re-run Q&A for sections that returned shallow answers.\n"
            "- Confirm that newly added Zotero sources were ingested in this run."
        )

    def _build_glossary(self, entities: list[str]) -> str:
        if not entities:
            return "- No glossary terms extracted."
        return "\n".join(f"- **{entity}**" for entity in entities[:20])

    def _build_structured_deep_dive(self, subject: str, qa_history: list[dict[str, str]]) -> str:
        """Build a deterministic structured deep-dive when model synthesis fails."""
        if not qa_history:
            return (
                f"## Overview\n{subject} research was initiated, but no Q&A content was produced.\n\n"
                "## Next Actions\n"
                "- Verify NotebookLM ingestion and authentication.\n"
                "- Re-run the pipeline after confirming source availability."
            )

        sections: dict[str, list[str]] = {
            "Foundations": [],
            "Architecture and Workflow": [],
            "Implementation Details": [],
            "Use Cases and Applications": [],
            "Tradeoffs and Risks": [],
        }

        for qa in qa_history[:16]:
            question = (qa.get("question") or "").strip()
            answer = (qa.get("answer") or "").strip()
            if not question or not answer:
                continue
            lower = question.lower()
            target = "Foundations"
            if any(k in lower for k in ["architecture", "design", "system", "workflow"]):
                target = "Architecture and Workflow"
            elif any(k in lower for k in ["how", "implement", "technical", "mechanism", "integration"]):
                target = "Implementation Details"
            elif any(k in lower for k in ["use case", "application", "when should", "adopt", "deploy"]):
                target = "Use Cases and Applications"
            elif any(k in lower for k in ["limitation", "tradeoff", "risk", "challenge", "edge case"]):
                target = "Tradeoffs and Risks"

            sections[target].append(f"### {question}\n{answer}")

        blocks: list[str] = [f"## Subject\n{subject}"]
        for name, entries in sections.items():
            if not entries:
                continue
            blocks.append(f"## {name}\n\n" + "\n\n".join(entries))

        blocks.append(
            "## Follow-up Checklist\n"
            "- Validate each key claim against source citations.\n"
            "- Expand sparse sections in the next run with targeted questions."
        )
        return "\n\n".join(blocks)

    def _emit(self, callback: Callable[[Any], None] | None, payload: Any) -> None:
        if callback:
            callback(payload)
