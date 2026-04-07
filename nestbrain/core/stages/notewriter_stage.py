"""Note writer stage: domain classification, rendering/merging notes, vault enrichment."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Callable
from ..note_renderer import (
    SynthesisResult,
    classify_domain,
    render_master_note,
    merge_into_existing_note,
    slugify,
)
from ..vault_manager import classify_and_file
from ..obsidian_parser import ObsidianNote
from ..ollama_client import OllamaClient


async def write_note(
    collection_name: str,
    items: list[dict[str, Any]],
    synthesis: SynthesisResult,
    media_paths: dict[str, str],
    vault_path: str,
    status_callback: Callable[[str], None] | None = None,
) -> str:
    """Write or merge note to Obsidian vault.
    
    Args:
        collection_name: Name of the collection
        items: List of items (as dicts)
        synthesis: Synthesis result
        media_paths: Dictionary with media artifact paths
        vault_path: Path to Obsidian vault root
        status_callback: Optional progress callback
        
    Returns:
        Path to written note (relative to vault)
    """
    if status_callback:
        status_callback("✍️ Writing note to Obsidian vault...")
    
    domain = classify_domain(collection_name)
    slug = slugify(collection_name)
    legacy_dir = Path(vault_path) / "20_Concepts" / domain
    legacy_dir.mkdir(parents=True, exist_ok=True)
    legacy_note_path = legacy_dir / f"{slug}.md"
    
    if legacy_note_path.exists():
        existing = legacy_note_path.read_text(encoding="utf-8")
        note_content = merge_into_existing_note(existing, items, synthesis, media_paths, items)
    else:
        note_content = render_master_note(collection_name, items, synthesis, media_paths)
    
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        suffix=".md",
        prefix=f".{slug}.",
        dir=vault_path,
    ) as handle:
        handle.write(note_content)
        temp_note_path = handle.name

    final_path = Path(classify_and_file(temp_note_path))
    return str(final_path.relative_to(vault_path))


async def enrich_vault_notes(
    notes: list[ObsidianNote],
    ollama: OllamaClient,
    progress_callback: Callable[[int], None] | None = None,
    status_callback: Callable[[str], None] | None = None,
) -> None:
    """Enrich existing vault notes with summaries and semantic tags via AI.
    
    Args:
        notes: List of ObsidianNote objects to enrich
        ollama: OllamaClient for synthesis
        progress_callback: Optional progress callback (0-100)
        status_callback: Optional status callback
    """
    if not notes:
        return
    
    if status_callback:
        status_callback("Enriching vault notes with AI analysis...")
    
    max_notes = min(len(notes), 40)
    for index, note in enumerate(notes[:max_notes]):
        try:
            note.summary = ollama.summarize_text(note.content)
            note.semantic_tags = ollama.generate_semantic_tags(note.content)
        except Exception:
            # Gracefully skip on error
            note.summary = ""
            note.semantic_tags = []
        
        relative = (index + 1) / max_notes
        if progress_callback:
            progress_callback(int(40 + relative * 30))


async def suggest_semantic_links(
    note_titles: list[str],
    context_blob: str,
    ollama: OllamaClient,
    status_callback: Callable[[str], None] | None = None,
) -> list[dict[str, str]]:
    """Suggest semantic links (wikilinks) between vault notes.
    
    Args:
        note_titles: List of note titles to link
        context_blob: Combined context from notes
        ollama: OllamaClient for suggestions
        status_callback: Optional progress callback
        
    Returns:
        List of suggested links {source, target, reason}
    """
    if status_callback:
        status_callback("Suggesting semantic links...")
    
    try:
        return ollama.suggest_links(note_titles, context_blob)
    except Exception:
        return []
