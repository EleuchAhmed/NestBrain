from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re
from typing import Any

import yaml


WIKILINK_PATTERN = re.compile(r"\[\[([^\]|#]+)(?:#[^\]]+)?(?:\|[^\]]+)?\]\]")
TAG_PATTERN = re.compile(r"(?<!\w)#([\w\-/]+)")
HEADING_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Directories to exclude from vault scan to avoid picking up dependencies and build artifacts
EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".nuxt", "target", "egg-info", ".pytest_cache"}
MAX_NOTES_THRESHOLD = 300  # Alert if vault scan exceeds this count (suggests misconfigured path)


@dataclass(slots=True)
class ObsidianNote:
    path: str
    title: str
    tags: list[str]
    wikilinks: list[str]
    last_modified: str
    metadata: dict[str, Any] = field(default_factory=dict)
    content: str = ""
    summary: str = ""
    semantic_tags: list[str] = field(default_factory=list)


class ObsidianParser:
    """Parse Obsidian markdown vault notes into structured note records."""

    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser().resolve() if vault_path else Path()

    def parse_vault(self) -> list[ObsidianNote]:
        if not self.vault_path or not self.vault_path.exists() or not self.vault_path.is_dir():
            return []

        notes: list[ObsidianNote] = []
        for md_file in self.vault_path.rglob("*.md"):
            # Skip files in excluded directories
            if any(part in EXCLUDED_DIRS for part in md_file.relative_to(self.vault_path).parts):
                continue
            try:
                notes.append(self.parse_file(md_file))
            except Exception:
                continue

        notes.sort(key=lambda note: note.last_modified, reverse=True)
        # Track if note count seems suspiciously high (misconfigured vault path)
        if len(notes) > MAX_NOTES_THRESHOLD:
            # Add warning to first note's metadata for UI display
            if notes:
                notes[0].metadata["_vault_scan_warning"] = f"Parsed {len(notes)} notes—vault path may be too broad. Configure to a specific Obsidian vault folder."
        return notes

    def parse_file(self, file_path: str | Path) -> ObsidianNote:
        file_path = Path(file_path)
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        metadata, body = self._extract_frontmatter(content)
        title = self._extract_title(file_path, metadata, body)
        tags = self._extract_tags(body, metadata)
        wikilinks = self._extract_wikilinks(body)
        last_modified = datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(timespec="seconds")

        return ObsidianNote(
            path=str(file_path),
            title=title,
            tags=tags,
            wikilinks=wikilinks,
            last_modified=last_modified,
            metadata=metadata,
            content=body.strip(),
        )

    def _extract_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        raw_frontmatter = parts[1]
        body = parts[2]
        try:
            metadata = yaml.safe_load(raw_frontmatter) or {}
            if not isinstance(metadata, dict):
                metadata = {}
            return metadata, body
        except Exception:
            return {}, content

    def _extract_title(self, file_path: Path, metadata: dict[str, Any], body: str) -> str:
        frontmatter_title = metadata.get("title")
        if isinstance(frontmatter_title, str) and frontmatter_title.strip():
            return frontmatter_title.strip()

        heading_match = HEADING_PATTERN.search(body)
        if heading_match:
            return heading_match.group(1).strip()

        return file_path.stem.replace("-", " ").replace("_", " ").strip().title()

    def _extract_tags(self, body: str, metadata: dict[str, Any]) -> list[str]:
        tags: set[str] = set()

        fm_tags = metadata.get("tags", [])
        if isinstance(fm_tags, str):
            tags.add(fm_tags.strip().lstrip("#"))
        elif isinstance(fm_tags, list):
            tags.update(str(item).strip().lstrip("#") for item in fm_tags if str(item).strip())

        tags.update(match.group(1).strip() for match in TAG_PATTERN.finditer(body))
        return sorted(tag for tag in tags if tag)

    def _extract_wikilinks(self, body: str) -> list[str]:
        links = [match.group(1).strip() for match in WIKILINK_PATTERN.finditer(body)]
        unique_links = sorted({link for link in links if link})
        return unique_links
