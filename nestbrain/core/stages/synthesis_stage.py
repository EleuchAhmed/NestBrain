"""Synthesis stage: grounded note + Ollama synthesis for content sections."""

from __future__ import annotations

from typing import Any, Callable

from ..notebooklm_bridge import NotebookLMBridge
from ..note_renderer import SynthesisResult
from ..ollama_client import OllamaClient


async def run_synthesis(
    collection_name: str,
    notebook_id: str,
    interrogation_responses: list[str],
    bridge: NotebookLMBridge | None,
    ollama: OllamaClient,
    status_callback: Callable[[str], None] | None = None,
) -> SynthesisResult:
    """Run synthesis via NotebookLM grounding + Ollama for 6 sections.
    
    Args:
        collection_name: Name of the collection
        notebook_id: NotebookLM notebook ID
        interrogation_responses: List of query responses
        bridge: Optional NotebookLMBridge for grounded note
        ollama: OllamaClient for synthesis
        status_callback: Optional progress callback
        
    Returns:
        SynthesisResult with all 6 content sections
    """
    synthesis = SynthesisResult()
    
    # Get grounded note from NotebookLM
    try:
        if status_callback:
            status_callback("📜 Getting grounded synthesis from NotebookLM...")
        
        if bridge:
            grounded = await bridge.synthesize(
                notebook_id,
                "Create a comprehensive research note covering: Executive Summary, Core Principles, Technical Details, and Practical Applications.",
            )
            synthesis.conceptual_deep_dive = grounded
    except Exception:
        synthesis.conceptual_deep_dive = "NotebookLM synthesis unavailable."
    
    # Combine context from interrogation + grounded note
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
            if status_callback:
                status_callback(f"🤖 Ollama: {prompt[:40]}...")
            
            # Truncate context to 5000 chars for API limits
            response = ollama.generate(
                f"{prompt}\n\nContext:\n{combined_context[:5000]}"
            )
            setattr(synthesis, field_name, response)
        except Exception as e:
            if status_callback:
                status_callback(f"⚠️ Synthesis failed for {field_name}")
            setattr(synthesis, field_name, f"Error: {str(e)}")
    
    return synthesis
