"""Note rendering and synthesis for note-vault integration."""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Any
from .utils import to_slug


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
    return to_slug(text)


def classify_domain(collection_name: str) -> str:
    """Classify text into concept taxonomy folders used in the vault."""
    lower = collection_name.lower()

    if any(x in lower for x in ["agent", "autonomy", "multi-agent", "tool use", "planner", "reasoning"]):
        return "Agents & Autonomy"
    if any(x in lower for x in ["data", "etl", "pipeline", "warehouse", "lakehouse", "mlops", "feature store", "dbt", "airflow"]):
        return "Data Engineering & MLOps"
    if any(x in lower for x in ["frontend", "ui", "ux", "react", "vue", "angular", "css", "html", "javascript"]):
        return "Frontend & UI"
    if any(x in lower for x in ["backend", "api", "microservice", "rest", "graphql", "fastapi", "django", "flask", "node", "express"]):
        return "Backend & API"
    if any(x in lower for x in ["network security", "firewall", "ids", "ips", "vpn", "network protocol", "zero trust"]):
        return "Network Security"
    if any(x in lower for x in ["appsec", "owasp", "sast", "dast", "xss", "sql injection", "csrf", "secure coding"]):
        return "AppSec"
    if any(x in lower for x in ["cryptography", "encryption", "cipher", "hash", "signature", "pki", "rsa", "ecc", "aes"]):
        return "Cryptography"
    if any(x in lower for x in ["web security", "browser security", "cookie", "cors", "csp", "session hijack"]):
        return "web security"
    if any(x in lower for x in ["aws", "azure", "gcp", "cloud provider", "cloudformation", "iam", "cloud run"]):
        return "Cloud Providers"
    if any(x in lower for x in ["devops", "ci", "cd", "docker", "kubernetes", "helm", "terraform", "ansible", "github actions", "gitlab"]):
        return "DevOps & CI-CD"

    return "Systems Design"


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
    """Render a complete markdown note with frontmatter, media, synthesis, and sources."""
    
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
    
    frontmatter = f"""---
aliases: [\"{collection_name}\"]
---
"""

    # Full note
    note = f"""{frontmatter}
{synthesis.academic_synthesis}

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
    """Merge new synthesis into existing note without overwriting.
    Safely finds section bounds to append updates without breaking customized notes.
    """
    
    now = datetime.now().isoformat()
    updated = existing_content

    def _replace_frontmatter_field(content: str, field_name: str, value: str) -> str:
        pattern = rf"(?m)^{re.escape(field_name)}:\s*.*$"
        if re.search(pattern, content):
            return re.sub(pattern, f"{field_name}: {value}", content)
        # Add to existing frontmatter if field is missing
        if content.startswith("---\n"):
            return content.replace("---\n", f"---\n{field_name}: {value}\n", 1)
        return content
    
    # Update timestamp if present or inject it
    updated = _replace_frontmatter_field(updated, "last_updated", now)
    
    # Append to sections instead of replacing
    sections = {
        "## 🧠 Conceptual Deep Dive": synthesis.conceptual_deep_dive,
        "## 🛠️ Actionable Takeaways": synthesis.actionable_knowledge,
        "## ⚖️ Critical Evaluation": synthesis.critical_evaluation,
        "## 📖 Glossary": synthesis.glossary,
        "## 🔗 Knowledge Graph": synthesis.knowledge_connections,
    }
    
    for section_header, new_content in sections.items():
        if not new_content:
            continue
        enrichment = f"\n\n### Updated: {now.split('T')[0]}\n\n{new_content}"
        
        header_idx = updated.find(section_header)
        if header_idx != -1:
            search_start = header_idx + len(section_header)
            # Find the next H1, H2, or horizontal rule to mark the end of this section
            match = re.search(r'\n(?:---|##? )', updated[search_start:])
            next_idx = search_start + match.start() if match else len(updated)
            
            # Insert enrichment right before the next section
            updated = updated[:next_idx].rstrip() + enrichment + "\n\n" + updated[next_idx:].lstrip("\n")
        else:
            updated = updated.rstrip() + f"\n\n{section_header}\n{enrichment}\n"
    
    # Update sources table
    if "## 📚 Sources Index" in updated:
        old_table_start = updated.find("## 📚 Sources Index") + len("## 📚 Sources Index")
        match = re.search(r'\n(?:---|##? )', updated[old_table_start:])
        old_table_end = old_table_start + match.start() if match else len(updated)
        
        new_table = "\n\n" + build_sources_table(all_items) + "\n\n"
        updated = updated[:old_table_start] + new_table + updated[old_table_end:].lstrip("\n")
    
    # Update media paths if provided
    if media_paths.get("video"):
        updated = _replace_frontmatter_field(updated, "notebooklm_video", str(media_paths["video"]))
    if media_paths.get("audio"):
        updated = _replace_frontmatter_field(updated, "notebooklm_audio", str(media_paths["audio"]))
    
    # Append to update log
    log_idx = updated.rfind("|------|")
    if log_idx > -1:
        next_line_idx = updated.find("\n", log_idx)
        next_line_idx = next_line_idx + 1 if next_line_idx != -1 else len(updated)
        
        new_log_row = f"| {now.split('T')[0]} | {', '.join(item.get('key', 'N/A') for item in new_items)} | Added {len(new_items)} new source(s), enriched all sections |\n"
        updated = updated[:next_line_idx] + new_log_row + updated[next_line_idx:]
    else:
        # Create log if it somehow got removed
        log_header = f"\n\n## 🕐 Update Log\n\n| Date | Sources Added | Summary of Changes |\n|------|--------------|-------------------|\n"
        new_log_row = f"| {now.split('T')[0]} | {', '.join(item.get('key', 'N/A') for item in new_items)} | Added {len(new_items)} new source(s), enriched all sections |\n"
        updated = updated.rstrip() + log_header + new_log_row
    
    return updated


def merge_note(existing_path: str, new_context: str, source_title: str) -> None:
    """Append a dated context section to an existing note without rewriting prior content."""

    note_path = Path(existing_path)
    if not note_path.exists() or not note_path.is_file():
        raise FileNotFoundError(f"Note file not found: {existing_path}")

    timestamp = datetime.now().date().isoformat()
    section = (
        f"\n\n## New context from [[{source_title}]] — {timestamp}\n"
        f"{new_context.strip()}\n"
    )

    current = note_path.read_text(encoding="utf-8")
    updated = current + section if current.endswith("\n") else current + "\n" + section.lstrip("\n")
    note_path.write_text(updated, encoding="utf-8")
