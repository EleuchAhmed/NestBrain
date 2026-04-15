"""Workflow coordinator for the NestBrain pipeline (NVIDIA NIM)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from .notebooklm_bridge import NotebookLMBridge
from .notebooklm_auth import NotebookLMAuthRequiredError
from .ollama_client import NvidiaLLMClient
from .note_parser import MarkdownNoteParser
from .paths import get_registry_path
from .registry import PipelineRegistry
from .zotero_sync import ZoteroCollection, ZoteroSyncClient
from .note_renderer import SynthesisResult
from .nvidia_client import nvidia_client
from .vault_manager import find_note_path
from .utils import to_slug

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


class PipelineWorkflow:
    """Coordinates the NVIDIA NIM based pipeline."""

    def __init__(self, app_root: str | Path) -> None:
        self.app_root = Path(app_root).resolve()
        self.registry_path = get_registry_path()
        self.registry = PipelineRegistry(self.registry_path)
        self.notebooklm: NotebookLMBridge | None = None

        self.planner = QuestionPlanner()
        self.synthesizer = MasterSynthesizer()
        self.extractor = EntityExtractor()

    async def run_full_pipeline(
        self,
        vault_path: str,
        zotero: ZoteroSyncClient,
        ollama: NvidiaLLMClient,
        selected_collection_key: str = "",
        progress_callback: Callable[[int], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Run the complete pipeline."""

        self._emit(status_callback, "Initializing pipeline")
        self._emit(progress_callback, 5)

        parser = MarkdownNoteParser(vault_path)
        notes = parser.parse_vault()

        self.seeder = NoteSeeder(vault_path)
        self.indexer = VectorIndexer(vault_path)
        self.auditor = SemanticAuditor(vault_path)
        self.annotator = ConnectionAnnotator(vault_path)
        self._emit(progress_callback, 10)

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

                result = await self.process_collection(
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

    async def process_collection(
        self,
        collection: ZoteroCollection,
        vault_path: str,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        try:
            if not self.notebooklm:
                self.notebooklm = NotebookLMBridge(self.app_root)

            collection_slug = collection.slug or to_slug(collection.display_name or collection.name)
            collection_display_name = collection.display_name or collection.name

            self.registry.get_or_create(collection_slug, collection_display_name)
            all_items = collection.items
            all_keys = [item.key for item in all_items]
            new_source_keys = self.registry.get_new_sources(collection_slug, all_keys)
            new_items = [item for item in all_items if item.key in set(new_source_keys)]

            notebook_id = self.registry.get_notebook_id(collection_slug)
            if not notebook_id:
                self._emit(status_callback, f"Creating NotebookLM notebook for {collection_display_name}")
                notebook_id = await self.notebooklm.create_notebook(collection_display_name)
                self.registry.set_notebook_id(collection_slug, notebook_id)
                self.registry.save()

            if new_items:
                self._emit(status_callback, f"Ingesting {len(new_items)} new sources into NotebookLM")
                successful_keys: list[str] = []
                for idx, item in enumerate(new_items):
                    logger.debug("Processing item %s/%s: %s", idx + 1, len(new_items), item.title[:50])
                    source_content = f"Title: {item.title}\n\nAbstract: {item.abstract}"
                    if item.url:
                        source_content += f"\n\nURL: {item.url}"
                    logger.debug("About to call ingest_text for %s", item.key)
                    ingested = await self.notebooklm.ingest_text(
                        notebook_id,
                        item.title or "Untitled Source",
                        source_content,
                    )
                    logger.debug("ingest_text returned %s for %s", ingested, item.key)
                    if ingested:
                        successful_keys.append(item.key)
                if successful_keys:
                    self.registry.mark_processed(collection_slug, successful_keys)
                    self.registry.save()
                else:
                    msg = f"No new sources ingested successfully for {collection_display_name}."
                    warnings.append(msg)
                    self._emit(status_callback, f"Warning: {msg}")
            else:
                self._emit(status_callback, f"No new sources to ingest for {collection_display_name}")

            self._emit(status_callback, f"L1: Planning Research for {collection_display_name}")
            logger.debug("Building context summary from %s items", len(new_items or all_items) or 0)
            context_summary = self._build_context_summary(new_items or all_items)
            logger.debug("Calling question_planner.generate_taxonomy for %s", collection_display_name)
            loop = asyncio.get_event_loop()
            taxonomy = await loop.run_in_executor(
                None,
                lambda: self.planner.generate_taxonomy(collection_display_name, context_summary)
            )
            logger.debug("Received %s taxonomy questions", len(taxonomy))
            if self.planner.used_fallback:
                msg = f"Question planner fallback used for {collection_display_name}: {self.planner.last_error}"
                warnings.append(msg)
                self._emit(status_callback, f"Warning: {msg}")

            self._emit(status_callback, f"L1: Iterative Q&A loops ({len(taxonomy)} paths)")
            logger.debug("Creating QAndALoop instance for %s", collection_display_name)
            qa_loop = QAndALoop(self.notebooklm)
            logger.debug("Calling execute_research with %s questions", len(taxonomy))
            qa_history = await qa_loop.execute_research(notebook_id, taxonomy)
            logger.debug("Received %s Q&A history entries", len(qa_history))

            self._emit(status_callback, "L1: Synthesizing Master Note")
            master_note_content = self.synthesizer.synthesize(collection_display_name, qa_history)
            if self.synthesizer.used_fallback:
                msg = f"Master synthesizer fallback used for {collection_display_name}: {self.synthesizer.last_error}"
                warnings.append(msg)
                self._emit(status_callback, f"Warning: {msg}")

            deep_dive_content = master_note_content
            if self.synthesizer.used_fallback:
                deep_dive_content = self._build_structured_deep_dive(collection_display_name, qa_history)

            self._emit(status_callback, "L2: Extracting knowledge entities")
            entities = self.extractor.extract_entities(master_note_content)
            if self.extractor.used_fallback:
                msg = f"Entity extractor fallback used for {collection_display_name}: {self.extractor.last_error}"
                warnings.append(msg)
                self._emit(status_callback, f"Warning: {msg}")
            if not entities:
                msg = f"No entities extracted for {collection_display_name}; mini-note creation skipped."
                warnings.append(msg)
                self._emit(status_callback, f"Warning: {msg}")
            entities = self._dedupe_entities(entities)
            self.seeder.reset_link_overrides()

            for term in entities:
                self._emit(status_callback, f"L2: Seeding/Patching entity '{term}'")
                self.seeder.process_extracted_term(term, deep_dive_content, collection_display_name)
                seeder_result = dict(self.seeder.last_result or {})
                if seeder_result.get("action") in {"created", "merge"}:
                    self._propagate_note(
                        note_title=str(seeder_result.get("title") or term),
                        note_path=str(seeder_result.get("note_path") or ""),
                        vault_path=vault_path,
                        status_callback=status_callback,
                    )

            deep_dive_content = self.synthesizer.weave_inline_wikilinks(
                deep_dive_content,
                entities,
                alias_map=self.seeder.get_link_overrides(),
            )
            link_overrides = self.seeder.get_link_overrides()

            synthesis_payload = SynthesisResult(
                academic_synthesis=(
                    f"# {collection_display_name}\n\n"
                    "Auto-generated by PipelineWorkflow. Detailed synthesis is in the Deep Dive section."
                ),
                conceptual_deep_dive=deep_dive_content,
                actionable_knowledge=self._build_actionable_takeaways(entities, link_overrides),
                knowledge_connections=self._build_knowledge_connections(entities, link_overrides),
                critical_evaluation=self._build_critical_evaluation(qa_history),
                glossary=self._build_glossary(entities),
            )
            items_dict = [asdict(item) for item in all_items]
            note_path = await write_note(
                collection_slug=collection_slug,
                collection_display_name=collection_display_name,
                items=items_dict,
                synthesis=synthesis_payload,
                media_paths={},
                vault_path=vault_path,
                status_callback=status_callback,
            )

            if not note_path:
                msg = (
                    f"Classification failed for {collection_display_name}; note filing was skipped. "
                    "See classification_failures.jsonl in app logs."
                )
                warnings.append(msg)
                self._emit(status_callback, f"Warning: {msg}")

            if note_path:
                self._propagate_note(
                    note_title=collection_display_name,
                    note_path=str(Path(vault_path) / note_path),
                    vault_path=vault_path,
                    status_callback=status_callback,
                )

            if note_path:
                self.registry.set_note_path(collection_slug, note_path)
                self.registry.save()

            return {"success": True, "note_path": note_path, "warnings": warnings}

        except NotebookLMAuthRequiredError as e:
            msg = f"NotebookLM authentication required for {collection_display_name}: {e}"
            warnings.append(msg)
            self._emit(status_callback, f"Warning: {msg}")
            logger.warning(msg)
            return {"success": False, "reason": str(e), "warnings": warnings}

        except Exception as e:
            logger.error(f"Collection processing failed: {e}")
            return {"success": False, "reason": str(e), "warnings": warnings}

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

    def _propagate_note(
        self,
        note_title: str,
        note_path: str,
        vault_path: str,
        status_callback: Callable[[str], None] | None = None,
    ) -> None:
        source_path = Path(note_path)
        if not source_path.is_absolute():
            source_path = Path(vault_path) / note_path
        if not source_path.exists():
            resolved = find_note_path(note_title, vault_path)
            if resolved is None or not resolved.exists():
                return
            source_path = resolved

        note_content = source_path.read_text(encoding="utf-8")

        self._emit(status_callback, "L3: Vector Indexing")
        new_vec = self.indexer.embed_new_note(note_title, note_content)
        if not new_vec:
            return

        self._emit(status_callback, "L3: Semantic K-NN Search")
        matches = self.indexer.find_similar_notes(new_vec, top_k=5)

        self._emit(status_callback, "L3: Auditing Connections")
        survivors = self.auditor.audit_connections(note_content, matches)

        related_targets: list[tuple[str, float]] = []
        for related_title, score in survivors:
            related_path = find_note_path(related_title, vault_path)
            if related_path is None:
                continue
            related_targets.append((str(related_path), score))

        if related_targets:
            self._emit(status_callback, "L3: Cross-annotating Graph")
            self.annotator.annotate_connections(note_title, note_content, related_targets)

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

    def _build_actionable_takeaways(self, entities: list[str], alias_map: dict[str, str] | None = None) -> str:
        if not entities:
            return "- Identify concrete implementation steps from the synthesized deep dive."
        alias_map = {str(k).strip().lower(): str(v).strip() for k, v in (alias_map or {}).items() if str(k).strip() and str(v).strip()}
        top = entities[:5]
        return "\n".join(
            f"- Build or revise notes around [[{alias_map.get(entity.lower(), entity)}]]."
            for entity in top
        )

    def _build_knowledge_connections(self, entities: list[str], alias_map: dict[str, str] | None = None) -> str:
        if not entities:
            return "- No semantic links available yet."
        alias_map = {str(k).strip().lower(): str(v).strip() for k, v in (alias_map or {}).items() if str(k).strip() and str(v).strip()}
        return "\n".join(f"- [[{alias_map.get(entity.lower(), entity)}]]" for entity in entities[:20])

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
        for entry in qa_history:
            question = (entry.get("question") or "").lower()
            answer = (entry.get("answer") or "").strip()
            if not answer:
                continue
            if any(k in question for k in ["what is", "why", "foundational"]):
                sections["Foundations"].append(answer)
            elif any(k in question for k in ["architecture", "workflow", "system", "component"]):
                sections["Architecture and Workflow"].append(answer)
            elif any(k in question for k in ["implement", "how", "mechanism", "integration"]):
                sections["Implementation Details"].append(answer)
            elif any(k in question for k in ["use case", "application", "example"]):
                sections["Use Cases and Applications"].append(answer)
            elif any(k in question for k in ["risk", "tradeoff", "limitation", "edge case"]):
                sections["Tradeoffs and Risks"].append(answer)
            else:
                sections["Implementation Details"].append(answer)

        blocks = [f"# {subject}", "", "## Executive Summary", "Model synthesis failed, so this note was built from raw research responses."]
        for heading, items in sections.items():
            blocks.append("")
            blocks.append(f"## {heading}")
            if items:
                blocks.extend([f"- {item}" for item in items[:8]])
            else:
                blocks.append("- No evidence captured for this section.")
        return "\n".join(blocks).strip()

    def _emit(self, callback: Callable[[Any], None] | None, payload: Any) -> None:
        if callback:
            callback(payload)
