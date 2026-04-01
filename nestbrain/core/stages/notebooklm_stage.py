"""NotebookLM stage: notebook creation, source ingestion, interrogation, media generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..notebooklm_bridge import NotebookLMBridge
from ..note_renderer import slugify


NOTEBOOKLM_QUERIES = [
    "What are the core foundational principles discussed across all sources?",
    "What are the key technical implementation details and best practices?",
    "What are the practical applications and use cases?",
    "What are the critical limitations, challenges, or edge cases?",
    "How do these concepts relate to broader industry trends and emerging technologies?",
]


async def create_notebook(
    bridge: NotebookLMBridge,
    collection_name: str,
    status_callback: Callable[[str], None] | None = None,
) -> str:
    """Create a new NotebookLM notebook for a collection.
    
    Args:
        bridge: NotebookLMBridge instance
        collection_name: Name of the collection
        status_callback: Optional progress callback
        
    Returns:
        Notebook ID
    """
    if status_callback:
        status_callback(f"📓 Creating NotebookLM notebook for '{collection_name}'...")
    return await bridge.create_notebook(collection_name)


async def ingest_sources(
    bridge: NotebookLMBridge,
    notebook_id: str,
    items: list[Any],
    status_callback: Callable[[str], None] | None = None,
) -> list[str]:
    """Ingest sources into a NotebookLM notebook.
    
    Supports PDF files, URLs, and abstract text fallback.
    
    Args:
        bridge: NotebookLMBridge instance
        notebook_id: Target notebook ID
        items: List of ZoteroItem objects
        status_callback: Optional progress callback
        
    Returns:
        List of successfully ingested item keys
    """
    if status_callback:
        status_callback(f"📄 Ingesting {len(items)} sources into NotebookLM...")
    
    successful_keys = []
    for item in items:
        ingested = False
        
        # Try PDF first
        if item.pdfPath and Path(item.pdfPath).exists():
            ingested = await bridge.ingest_file(notebook_id, item.pdfPath)
        # Fall back to URL
        elif item.url:
            ingested = await bridge.ingest_url(notebook_id, item.url)
        # Final fallback: abstract text
        elif item.abstract:
            content = f"# {item.title}\n"
            if item.authors:
                content += f"**Authors:** {item.authors}\n"
            if item.date:
                content += f"**Date:** {item.date}\n"
            content += f"\n## Abstract\n{item.abstract}"
            ingested = await bridge.ingest_text(notebook_id, item.title, content)
        
        if ingested:
            successful_keys.append(item.key)
    
    return successful_keys


async def interrogate_notebook(
    bridge: NotebookLMBridge,
    notebook_id: str,
    status_callback: Callable[[str], None] | None = None,
) -> list[str]:
    """Run interrogation queries on a NotebookLM notebook.
    
    Executes all NOTEBOOKLM_QUERIES and returns responses.
    
    Args:
        bridge: NotebookLMBridge instance
        notebook_id: Target notebook ID
        status_callback: Optional progress callback
        
    Returns:
        List of interrogation responses
    """
    if status_callback:
        status_callback(f"🔍 Running interrogation on {len(NOTEBOOKLM_QUERIES)} queries...")
    
    interrogation_responses = []
    for query in NOTEBOOKLM_QUERIES:
        responses = await bridge.interrogate(notebook_id, [query])
        interrogation_responses.extend(responses)
    
    return interrogation_responses


async def generate_media(
    bridge: NotebookLMBridge,
    notebook_id: str,
    collection_name: str,
    vault_path: str,
    status_callback: Callable[[str], None] | None = None,
) -> dict[str, str]:
    """Generate media (video/audio) for a NotebookLM notebook.
    
    Downloads artifacts to vault assets directory.
    
    Args:
        bridge: NotebookLMBridge instance
        notebook_id: Target notebook ID
        collection_name: Collection name for filename
        vault_path: Path to Obsidian vault
        status_callback: Optional progress callback
        
    Returns:
        Dictionary with "video" and "audio" paths (or empty if failed)
    """
    media_paths = {}
    
    try:
        if status_callback:
            status_callback("🎬 Generating video explainer...")
        
        video_result = await bridge.generate_media(notebook_id, "video")
        if video_result.get("status") == "success" and video_result.get("artifactId"):
            video_path = Path(vault_path) / "assets" / f"{slugify(collection_name)}-overview.mp4"
            video_path.parent.mkdir(parents=True, exist_ok=True)
            
            downloaded = await bridge.download_media(
                notebook_id, "video", video_result["artifactId"], str(video_path)
            )
            if downloaded:
                media_paths["video"] = f"assets/{video_path.name}"
    except Exception as e:
        if status_callback:
            status_callback(f"⚠️ Video generation failed: {e}")
    
    return media_paths
