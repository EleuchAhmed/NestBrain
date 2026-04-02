"""Note rendering and synthesis for Obsidian vault integration."""

from __future__ import annotations

import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SynthesisResult:
    """Synthesis output from DeepSeek synthesis pipeline."""
    
    academic_synthesis: str = ""
    conceptual_deep_dive: str = ""
    actionable_knowledge: str = ""
    knowledge_connections: str = ""
    critical_evaluation: str = ""
    glossary: str = ""


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    # First convert to lowercase and remove non-alphanumeric/space characters
    text = text.lower()
    text = re.sub(r"[^a-z0-9\- ]", "", text)
    # Replace multiple spaces with single hyphen
    text = re.sub(r" +", "-", text)
    # Replace multiple hyphens with single hyphen
    text = re.sub(r"-+", "-", text)
    # Strip leading/trailing hyphens
    return text.strip("-")


def classify_domain(collection_name: str) -> str:
    """Classify collection into a domain folder."""
    lower = collection_name.lower()
    
    if any(x in lower for x in ["llm", "ai", "ml", "data", "deep", "fine", "agent"]):
        return "AI-Data"
    if any(x in lower for x in ["cyber", "security", "pentest"]):
        return "Cyber"
    if any(x in lower for x in ["full", "web", "react", "node"]):
        return "Fullstack"
    
    return "General-Arch"


def build_sources_table(items: list[dict[str, Any]]) -> str:
    """Generate markdown table of sources."""
    rows = [
        "| # | Title | Type | Key | Date Added |",
        "|---|-------|------|-----|------------|",
    ]
    
    for i, item in enumerate(items, 1):
        item_type = item.get("item_type", "article")
        if item_type == "videoRecording":
            type_emoji = "🎥 Video"
        elif item_type == "webpage":
            type_emoji = "🌐 URL"
        elif item_type == "journalArticle":
            type_emoji = "📄 Paper"
        else:
            type_emoji = "📄 PDF"
        
        rows.append(f"| {i} | {item.get('title', 'Untitled')} | {type_emoji} | {item.get('key', 'N/A')} | {item.get('date', 'N/A')} |")
    
    return "\n".join(rows)


def render_master_note(
    collection_name: str,
    items: list[dict[str, Any]],
    synthesis: SynthesisResult,
    media_paths: dict[str, str],
) -> str:
    """Render complete Obsidian note with frontmatter, media, synthesis, and sources."""
    
    now = datetime.now().isoformat()
    slug = slugify(collection_name)
    
    # Media section
    media_lines = ["## 🎬 NotebookLM Audio/Video Overview"]
    if media_paths.get("video"):
        media_lines.append(f"### 🎥 Video Explainer\n![[{media_paths['video']}]]")
    else:
        media_lines.append("> _Video summary not yet generated._")
    
    if media_paths.get("audio"):
        media_lines.append(f"### 🎧 Audio Deep Dive\n![[{media_paths['audio']}]]")
    else:
        media_lines.append("> _Audio overview not yet generated._")
    
    media_lines.append("> *Auto-generated overview of all sources in this collection downloaded from NotebookLM.*")
    media_section = "\n\n".join(media_lines)
    
    # Update log
    update_log = f"""## 🕐 Update Log

| Date | Sources Added | Summary of Changes |
|------|--------------|-------------------|
| {now.split("T")[0]} | {", ".join(item.get('key', 'N/A') for item in items)} | Initial note creation with {len(items)} sources |
"""
    
    # Full note
    note = f"""{synthesis.academic_synthesis}

# {collection_name} — Master Knowledge Note

{media_section}

---

## 📚 Sources Index

{build_sources_table(items)}

---

## 🧠 Conceptual Deep Dive

{synthesis.conceptual_deep_dive}

---

## 🛠️ Actionable Takeaways

{synthesis.actionable_knowledge}

---

## ⚖️ Critical Evaluation

{synthesis.critical_evaluation}

---

## 📖 Glossary

{synthesis.glossary}

---

## 🔗 Knowledge Graph

{synthesis.knowledge_connections}

---

{update_log}
"""
    
    return note


def merge_into_existing_note(
    existing_content: str,
    new_items: list[dict[str, Any]],
    synthesis: SynthesisResult,
    media_paths: dict[str, str],
    all_items: list[dict[str, Any]],
) -> str:
    """Merge new synthesis into existing note without overwriting."""
    
    now = datetime.now().isoformat()
    updated = existing_content
    
    # Update timestamp if present
    updated = updated.replace(
        "last_updated:",
        f"last_updated: {now}",
    )
    
    # Append to sections instead of replacing
    sections = {
        "## 🧠 Conceptual Deep Dive": synthesis.conceptual_deep_dive,
        "## 🛠️ Actionable Takeaways": synthesis.actionable_knowledge,
        "## ⚖️ Critical Evaluation": synthesis.critical_evaluation,
        "## 📖 Glossary": synthesis.glossary,
        "## 🔗 Knowledge Graph": synthesis.knowledge_connections,
    }
    
    for section_header, new_content in sections.items():
        if section_header in updated and new_content:
            # Find section and append new content with timestamp
            idx = updated.find(section_header)
            next_section_idx = updated.find("\n---\n", idx + len(section_header))
            if next_section_idx > -1:
                enrichment = f"\n\n### Updated: {now.split('T')[0]}\n\n{new_content}"
                updated = (
                    updated[:next_section_idx] + enrichment + updated[next_section_idx:]
                )
    
    # Update sources table
    if "## 📚 Sources Index" in updated:
        old_table_start = updated.find("## 📚 Sources Index") + len("## 📚 Sources Index")
        old_table_end = updated.find("---", old_table_start)
        new_table = "\n\n" + build_sources_table(all_items) + "\n"
        updated = updated[:old_table_start] + new_table + updated[old_table_end:]
    
    # Update media paths if provided
    if media_paths.get("video"):
        updated = updated.replace(
            "notebooklm_video:",
            f"notebooklm_video: {media_paths['video']}",
        )
    if media_paths.get("audio"):
        updated = updated.replace(
            "notebooklm_audio:",
            f"notebooklm_audio: {media_paths['audio']}",
        )
    
    # Append to update log
    log_idx = updated.rfind("|------|")
    if log_idx > -1:
        next_line_idx = updated.find("\n", log_idx) + 1
        new_log_row = f"| {now.split('T')[0]} | {', '.join(item.get('key', 'N/A') for item in new_items)} | Added {len(new_items)} new source(s), enriched all sections |\n"
        updated = updated[:next_line_idx] + new_log_row + updated[next_line_idx:]
    
    return updated
