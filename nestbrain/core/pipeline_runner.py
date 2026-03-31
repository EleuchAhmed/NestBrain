from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

from .knowledge_graph import KnowledgeGraphBuilder
from .notebooklm_bridge import NotebookLMBridge
from .obsidian_parser import ObsidianNote, ObsidianParser
from .ollama_client import OllamaClient, OllamaClientError
from .registry import PipelineRegistry
from .zotero_sync import ZoteroCollection, ZoteroSyncClient, ZoteroSyncError
from .note_renderer import (
    SynthesisResult,
    classify_domain,
    render_master_note,
    merge_into_existing_note,
    slugify,
)


# NotebookLM Interrogation queries
NOTEBOOKLM_QUERIES = [
    "What are the core foundational principles discussed across all sources?",
    "What are the key technical implementation details and best practices?",
    "What are the practical applications and use cases?",
    "What are the critical limitations, challenges, or edge cases?",
    "How do these concepts relate to broader industry trends and emerging technologies?",
]


DEFAULT_CONFIG: dict[str, Any] = {
    "vault_path": "",
    "zotero_library_id": "",
    "zotero_api_key": "",
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
    zotero_api_key: str
    selected_collection_key: str
    ollama_model: str
    ollama_host: str
    zotero_host: str
    theme: str


class PipelineRunner:
    """Orchestrates Obsidian parsing, Zotero sync, NotebookLM interrogation, DeepSeek synthesis, and Obsidian writing."""

    def __init__(self, app_root: str | Path) -> None:
        self.app_root = Path(app_root).resolve()
        self.archive_dir = self.app_root / "runs"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize registry for source deduplication
        self.registry_path = self.app_root / "pipeline-registry.json"
        self.registry = PipelineRegistry(self.registry_path)
        
        # NotebookLM bridge
        self.notebooklm: NotebookLMBridge | None = None

    def run(
        self,
        config: PipelineConfig,
        progress_callback: Callable[[int], None] | None = None,
        status_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Run full pipeline: parse vault → sync Zotero → NotebookLM → synthesis → Obsidian write."""
        # Run async pipeline in sync wrapper
        return asyncio.run(self._run_async(config, progress_callback, status_callback))

    async def _run_async(
        self,
        config: PipelineConfig,
        progress_callback: Callable[[int], None] | None,
        status_callback: Callable[[str], None] | None,
    ) -> dict[str, Any]:
        """Async version of full pipeline."""
        self._emit(status_callback, "Initializing pipeline")
        self._emit(progress_callback, 5)

        # Validate vault path before parsing
        vault_validation = self._validate_vault_path(config.vault_path)
        if vault_validation["error"]:
            self._emit(status_callback, f"Configuration error: {vault_validation['error']}")
            return {
                "notes": [],
                "collections": [],
                "graph": {},
                "archive_entry": None,
                "created_notes": [],
                "errors": {
                    "zotero": "",
                    "ollama": "",
                    "vault": vault_validation["error"],
                },
            }

        parser = ObsidianParser(config.vault_path)
        zotero = ZoteroSyncClient(
            host=config.zotero_host,
            library_id=config.zotero_library_id,
            api_key=config.zotero_api_key,
        )
        ollama = OllamaClient(host=config.ollama_host, model=config.ollama_model)
        graph_builder = KnowledgeGraphBuilder()

        self._emit(status_callback, "Parsing Obsidian vault")
        notes = parser.parse_vault()
        self._emit(progress_callback, 10)

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
        self._emit(progress_callback, 20)

        # Process collections through NotebookLM pipeline
        created_notes = []
        notebooklm_error = ""
        if collections:
            self._emit(status_callback, "Processing collections through NotebookLM...")
            try:
                for idx, collection in enumerate(collections):
                    progress = int(20 + (idx / len(collections)) * 60)
                    self._emit(progress_callback, progress)
                    
                    result = await self._process_collection_with_notebooklm(
                        collection, config, ollama, status_callback, progress_callback
                    )
                    if result.get("success"):
                        created_notes.append(result)
            except Exception as e:
                notebooklm_error = str(e)
                self._emit(status_callback, f"⚠️ NotebookLM processing error: {e}")

        self._emit(progress_callback, 80)

        # Enrich vault notes with semantic tags
        semantic_link_candidates: list[dict[str, str]] = []
        self._emit(status_callback, "Enriching vault analysis...")
        try:
            self._enrich_notes(notes, ollama, progress_callback)
            titles = [note.title for note in notes]
            context_blob = "\n".join(note.summary or note.content[:700] for note in notes[:20])
            semantic_link_candidates = ollama.suggest_links(titles, context_blob)
        except OllamaClientError as exc:
            notebooklm_error = str(exc)
        except Exception as exc:
            notebooklm_error = str(exc)
        self._emit(progress_callback, 85)

        # Build knowledge graph
        self._emit(status_callback, "Building knowledge graph")
        graph_payload = graph_builder.build(notes, collections, semantic_links=semantic_link_candidates)
        self._emit(progress_callback, 90)

        # Create archive entry
        archive_entry = self._create_archive_entry(
            notes=notes,
            collections=collections,
            graph_payload=graph_payload,
            errors={
                "zotero": zotero_error,
                "ollama": notebooklm_error,
            },
        )
        self._emit(progress_callback, 100)
        self._emit(status_callback, "Pipeline complete")

        return {
            "notes": [asdict(note) for note in notes],
            "collections": [asdict(collection) for collection in collections],
            "graph": graph_payload,
            "archive_entry": archive_entry,
            "created_notes": created_notes,
            "errors": {
                "zotero": zotero_error,
                "ollama": notebooklm_error,
                "vault": "",
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

    def _validate_vault_path(self, vault_path: str) -> dict[str, Any]:
        """Validate vault path before parsing. Rejects broad roots like Desktop."""
        if not vault_path or not vault_path.strip():
            return {"error": "Vault path not configured. Set it in Settings."}
        
        path = Path(vault_path).expanduser().resolve()
        if not path.exists():
            return {"error": f"Vault folder does not exist: {vault_path}"}
        
        if not path.is_dir():
            return {"error": f"Vault path is not a directory: {vault_path}"}
        
        # Check if this looks like a root folder (Desktop, Documents, Downloads, etc.)
        # These are too broad and will pick up unrelated content
        home = Path.home()
        suspicious_roots = {home / "Desktop", home / "Documents", home / "Downloads", home, home / "OneDrive" if (home / "OneDrive").exists() else None}
        suspicious_roots = {p for p in suspicious_roots if p is not None}
        
        if path in suspicious_roots:
            return {"error": f"Vault path '{path.name}' is too broad and will include irrelevant folders. Please set it to your actual Obsidian vault (e.g., 'tech knowledge')."}
        
        # Check for Obsidian vault marker (.obsidian folder) or .obsidian.json
        has_obsidian_marker = (path / ".obsidian").exists() or (path / ".obsidian.json").exists()
        if not has_obsidian_marker:
            # Allow it but warn
            pass
        
        return {"error": None, "path": str(path)}

    async def _process_collection_with_notebooklm(
        self,
        collection: ZoteroCollection,
        config: PipelineConfig,
        ollama: OllamaClient,
        status_callback: Callable[[str], None] | None,
        progress_callback: Callable[[int], None] | None,
    ) -> dict[str, Any]:
        """Process a single collection through NotebookLM → Synthesis → Obsidian write."""
        
        if not self.notebooklm:
            self.notebooklm = NotebookLMBridge(self.app_root)
        
        try:
            # Get collection state from registry
            reg_entry = self.registry.get_or_create(collection.key, collection.name)
            all_items = collection.items
            all_keys = [item.key for item in all_items]
            
            # Get notebook ID from cache or create new
            notebook_id = self.registry.get_notebook_id(collection.key)
            if not notebook_id:
                self._emit(status_callback, f"📓 Creating NotebookLM notebook for '{collection.name}'...")
                notebook_id = await self.notebooklm.create_notebook(collection.name)
                self.registry.set_notebook_id(collection.key, notebook_id)
            else:
                self._emit(status_callback, f"📓 Using cached notebook for '{collection.name}'...")
            
            # Ingest sources
            self._emit(status_callback, f"📄 Ingesting {len(all_items)} sources into NotebookLM...")
            successful_keys = []
            for item in all_items:
                ingested = False
                if item.pdfPath and Path(item.pdfPath).exists():
                    ingested = await self.notebooklm.ingest_file(notebook_id, item.pdfPath)
                elif item.url:
                    ingested = await self.notebooklm.ingest_url(notebook_id, item.url)
                elif item.abstract:
                    content = f"# {item.title}\n"
                    if item.authors:
                        content += f"**Authors:** {item.authors}\n"
                    if item.date:
                        content += f"**Date:** {item.date}\n"
                    content += f"\n## Abstract\n{item.abstract}"
                    ingested = await self.notebooklm.ingest_text(notebook_id, item.title, content)
                
                if ingested:
                    successful_keys.append(item.key)
            
            if not successful_keys:
                self._emit(status_callback, f"⚠️ No sources ingested for '{collection.name}'")
                return {"success": False, "reason": "No ingestable sources"}
            
            # Interrogate NotebookLM
            self._emit(status_callback, f"🔍 Running interrogation on {len(NOTEBOOKLM_QUERIES)} queries...")
            interrogation_responses = []
            for query in NOTEBOOKLM_QUERIES:
                responses = await self.notebooklm.interrogate(notebook_id, [query])
                interrogation_responses.extend(responses)
            
            # Generate media (audio/video)
            media_paths = {}
            try:
                self._emit(status_callback, "🎬 Generating video explainer...")
                video_result = await self.notebooklm.generate_media(notebook_id, "video")
                if video_result.get("status") == "success" and video_result.get("artifactId"):
                    video_path = (
                        Path(config.vault_path) / "assets" 
                        / f"{slugify(collection.name)}-overview.mp4"
                    )
                    video_path.parent.mkdir(parents=True, exist_ok=True)
                    downloaded = await self.notebooklm.download_media(
                        notebook_id, "video", video_result["artifactId"], str(video_path)
                    )
                    if downloaded:
                        media_paths["video"] = f"assets/{video_path.name}"
                        self.registry.set_media_path(collection.key, "video", media_paths["video"])
            except Exception as e:
                self._emit(status_callback, f"⚠️ Video generation failed: {e}")
            
            # Get synthesis from NotebookLM and Ollama
            self._emit(status_callback, "🧠 Running synthesis...")
            synthesis = await self._run_synthesis(
                collection.name, notebook_id, interrogation_responses, ollama, status_callback
            )
            
            # Render and write note to Obsidian vault
            self._emit(status_callback, f"✍️ Writing note to Obsidian vault...")
            domain = classify_domain(collection.name)
            slug = slugify(collection.name)
            note_path = Path(config.vault_path) / "20_Concepts" / domain / f"{slug}.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to simple dict format for renderer
            items_dict = [asdict(item) for item in all_items]
            
            if note_path.exists():
                existing = note_path.read_text(encoding="utf-8")
                note_content = merge_into_existing_note(
                    existing, items_dict, synthesis, media_paths, items_dict
                )
            else:
                note_content = render_master_note(
                    collection.name, items_dict, synthesis, media_paths
                )
            
            note_path.write_text(note_content, encoding="utf-8")
            self.registry.set_obsidian_path(collection.key, str(note_path.relative_to(config.vault_path)))
            
            # Update registry
            self.registry.mark_processed(collection.key, successful_keys)
            self.registry.save()
            
            return {
                "success": True,
                "note_path": str(note_path),
                "sources_processed": len(successful_keys),
            }
        
        except Exception as e:
            self._emit(status_callback, f"❌ Error processing collection '{collection.name}': {e}")
            return {"success": False, "reason": str(e)}

    async def _run_synthesis(
        self,
        collection_name: str,
        notebook_id: str,
        interrogation_responses: list[str],
        ollama: OllamaClient,
        status_callback: Callable[[str], None] | None,
    ) -> SynthesisResult:
        """Run synthesis via NotebookLM grounding + Ollama for 6 sections."""
        
        synthesis = SynthesisResult()
        
        try:
            # Get grounded note from NotebookLM
            self._emit(status_callback, "📜 Getting grounded synthesis from NotebookLM...")
            if self.notebooklm:
                grounded = await self.notebooklm.synthesize(
                    notebook_id,
                    "Create a comprehensive research note covering: Executive Summary, Core Principles, Technical Details, and Practical Applications.",
                )
                synthesis.conceptual_deep_dive = grounded
        except Exception:
            synthesis.conceptual_deep_dive = "NotebookLM synthesis unavailable."
        
        # Combine context
        combined_context = "\n\n---\n\n".join(interrogation_responses)
        combined_context += f"\n\n{synthesis.conceptual_deep_dive}"
        
        # Ollama synthesis for remaining sections
        synthesis_tasks = [
            ("academic_synthesis", f"Generate YAML frontmatter and TL;DR for '{collection_name}' research note."),
            ("actionable_knowledge", f"Extract 5-10 actionable takeaways and practical guidance from this research on {collection_name}."),
            ("knowledge_connections", f"Suggest 5-8 semantic wikilinks ([[Topic]]) related to {collection_name}."),
            ("critical_evaluation", f"Provide a balanced critical evaluation of {collection_name}, including limitations and edge cases."),
            ("glossary", f"Define 5-10 key technical terms from {collection_name}."),
        ]
        
        for field_name, prompt in synthesis_tasks:
            try:
                self._emit(status_callback, f"🤖 Ollama: {prompt[:40]}...")
                response = ollama.generate(
                    f"{prompt}\n\nContext:\n{combined_context[:5000]}"
                )
                setattr(synthesis, field_name, response)
            except Exception as e:
                self._emit(status_callback, f"⚠️ Synthesis failed for {field_name}")
                setattr(synthesis, field_name, f"Error: {str(e)}")
        
        return synthesis

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
        zotero_api_key=str(merged.get("zotero_api_key", "")),
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
        "zotero_api_key": config.zotero_api_key,
        "selected_collection_key": config.selected_collection_key,
        "ollama_model": config.ollama_model,
        "ollama_host": config.ollama_host,
        "zotero_host": config.zotero_host,
        "theme": config.theme,
    }
    Path(config_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
