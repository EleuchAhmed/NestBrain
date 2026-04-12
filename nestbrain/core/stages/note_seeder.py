import logging
import re
from pathlib import Path
import json
from datetime import datetime, timezone
from ..nvidia_client import nvidia_client
from ..note_renderer import classify_domain
from ..utils import to_slug
from ..vault_manager import classify_and_file, log_classification_failure

logger = logging.getLogger(__name__)

class NoteSeeder:
    """Layer 2: Entity Growth Seeder
    Contains logic for both generating new stubs (The Seed Maker - devstral-2-123b)
    and patching existing notes (The Surgeon - glm-4.7).
    """

    MODEL_SEEDER = "mistralai/devstral-2-123b-instruct-2512"
    MODEL_SURGEON = "deepseek-ai/deepseek-v3.2"

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.client = nvidia_client
        self.seeder_log_path = self.vault_path / "seeder_log.json"
        self.link_overrides: dict[str, str] = {}

    def _get_note_path(self, term: str, master_note_context: str = "", subject_title: str = "") -> Path:
        """Helper to get a safe Markdown path for an entity term in concept taxonomy."""
        classification_context = f"{term} {subject_title} {master_note_context[:800]}"
        domain = classify_domain(classification_context)

        safe_slug = to_slug(term)
        return self.vault_path / "20_Concepts" / domain / f"{safe_slug}.md"

    def process_extracted_term(self, term: str, master_note_context: str, subject_title: str) -> bool:
        """
        Determines if a note exists. If not, spawns The Seed Maker.
        If yes, spawns The Surgeon to carefully append new context.
        """
        note_path = self._get_note_path(term, master_note_context, subject_title)

        existing_notes = self._scan_existing_notes_index()
        semantic_result = self._semantic_duplicate_check(term, existing_notes)

        if semantic_result.get("match_found"):
            matched_note = str(semantic_result.get("matched_note") or "").strip()
            matched_display = str(semantic_result.get("matched_display") or "").strip()
            if matched_note:
                self._backfill_alias_for_existing(term, existing_notes, matched_note)
                self.link_overrides[term] = matched_display or term
            self._append_seeder_log(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "entity": term,
                    "action": "skipped",
                    "matched_note": matched_note or None,
                    "reason": str(semantic_result.get("reasoning") or "Semantic duplicate found."),
                }
            )
            logger.info("Seeder skipped '%s' because semantic duplicate exists: %s", term, matched_note or "unknown")
            return True

        if not note_path.exists():
            # Brand new concept -> Seed Maker
            logger.info(f"Term '{term}' not found in vault. Spawning The Seed Maker.")
            created = self._seed_new_note(term, master_note_context, subject_title, note_path)
            if created:
                self.link_overrides[term] = term
            self._append_seeder_log(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "entity": term,
                    "action": "created" if created else "failed",
                    "matched_note": None,
                    "reason": "No semantic duplicate found in vault index.",
                }
            )
            return created
        else:
            logger.info(f"Term '{term}' already exists by resolved path. Skipping mutation for backward safety.")
            self._upsert_alias_on_note(note_path, term)
            self.link_overrides[term] = term
            self._append_seeder_log(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "entity": term,
                    "action": "skipped",
                    "matched_note": note_path.stem,
                    "reason": "Resolved canonical note path already exists.",
                }
            )
            return True

    def get_link_overrides(self) -> dict[str, str]:
        return dict(self.link_overrides)

    def reset_link_overrides(self) -> None:
        self.link_overrides.clear()

    def _seed_new_note(self, term: str, master_note_context: str, subject_title: str, write_path: Path) -> bool:
        """The Seed Maker uses devstral to build a baseline concept node."""
        system_prompt = (
            "You are The Seed Maker. Create a concise, factual initial 'stub' note for an Obsidian knowledge vault.\n"
            f"Write a definition and key details for the term based on the provided overarching context.\n"
            f"You MUST include an explicitly linked \"Source Context: [[{subject_title}]]\" section at the end.\n"
            "Format cleanly in Markdown, beginning with `# [Term Name]`."
        )

        user_content = (
            f"Term to define: {term}\n\n"
            f"Overarching Subject context: {master_note_context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            response_text = self.client.generate_chat_completion(
                model=self.MODEL_SEEDER,
                messages=messages,
                temperature=0.3
            )
            rendered = self._upsert_aliases_in_markdown(response_text.strip(), [term])
            write_path.parent.mkdir(parents=True, exist_ok=True)
            write_path.write_text(rendered, encoding="utf-8")
            classify_and_file(str(write_path))
            return True
        except ValueError as e:
            log_classification_failure(
                stage="note_seeder",
                note_title=term,
                reason=str(e),
                source_path=str(write_path),
            )
            logger.error(f"Seed Maker classification failed on term '{term}': {e}")
            return False
        except Exception as e:
            logger.error(f"Seed Maker failed on term '{term}': {e}")
            return False

    def _patch_existing_note(self, term: str, existing_content: str, master_note_context: str, subject_title: str, write_path: Path) -> bool:
        """The Surgeon uses glm to append missing context intelligently without destroying."""
        system_prompt = (
            "You are The Surgeon. Your job is to surgically APPEND a new relevant section to an existing markdown note.\n"
            "DO NOT rewrite or summarize everything. Return ONLY the new sub-section text that should be appended to the bottom.\n"
            f"The new section should capture what the overarching context says about the term.\n"
            f"You must include a bidirectional link `[[{subject_title}]]` inside your generated text so Obsidian registers the connection.\n"
            "Format the new section with a heading corresponding to the new context."
        )

        user_content = (
            f"Term Note: {term}\n"
            f"Existing Content (for reference only, do not repeat it):\n{existing_content[:2000]}...\n\n"
            f"New Overarching Context to integrate:\n{master_note_context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            new_patch = self.client.generate_chat_completion(
                model=self.MODEL_SURGEON,
                messages=messages,
                temperature=0.1
            )
            
            # Append physically
            with write_path.open("a", encoding="utf-8") as f:
                f.write("\n\n" + new_patch.strip() + "\n")
            return True
            
        except Exception as e:
            logger.error(f"Surgeon failed on term '{term}': {e}")
            return False

    def _scan_existing_notes_index(self) -> list[dict[str, str | list[str]]]:
        index: list[dict[str, str | list[str]]] = []
        for note_path in self.vault_path.rglob("*.md"):
            title = note_path.stem.strip()
            aliases = self._extract_aliases_from_frontmatter(note_path)
            index.append(
                {
                    "title": title,
                    "path": str(note_path),
                    "aliases": aliases,
                }
            )
        return index

    def _extract_aliases_from_frontmatter(self, note_path: Path) -> list[str]:
        try:
            head = "\n".join(note_path.read_text(encoding="utf-8").splitlines()[:40])
        except Exception:
            return []

        aliases: list[str] = []
        block_match = re.search(r"(?ms)^---\s*\n(.*?)\n---", head)
        if not block_match:
            return aliases
        frontmatter = block_match.group(1)

        inline = re.search(r"(?im)^aliases\s*:\s*\[(.*?)\]\s*$", frontmatter)
        if inline:
            for token in inline.group(1).split(","):
                value = token.strip().strip("\"'")
                if value:
                    aliases.append(value)

        block = re.search(r"(?ims)^aliases\s*:\s*\n((?:\s*-\s*.*\n?)*)", frontmatter)
        if block:
            for line in block.group(1).splitlines():
                item = re.sub(r"^\s*-\s*", "", line).strip().strip("\"'")
                if item:
                    aliases.append(item)

        deduped: list[str] = []
        seen: set[str] = set()
        for alias in aliases:
            key = alias.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(alias)
        return deduped

    def _semantic_duplicate_check(self, candidate: str, existing_notes: list[dict[str, str | list[str]]]) -> dict[str, object]:
        normalized_candidate = self._normalize_concept(candidate)
        candidate_slug = to_slug(candidate)
        for note in existing_notes:
            title = str(note.get("title") or "")
            aliases = [str(a) for a in (note.get("aliases") or [])]
            if title.lower() == candidate_slug:
                return {
                    "match_found": True,
                    "matched_note": title,
                    "matched_display": self._preferred_display_alias(aliases, candidate),
                    "reasoning": "Exact slug match from note filename.",
                }
            variants = [title] + aliases
            for variant in variants:
                if self._normalize_concept(variant) == normalized_candidate:
                    return {
                        "match_found": True,
                        "matched_note": title,
                        "matched_display": self._preferred_display_alias(aliases, candidate),
                        "reasoning": "Exact normalized match from title/alias index.",
                    }

        if not self.client.is_configured() or not existing_notes:
            return {
                "match_found": False,
                "matched_note": None,
                "matched_display": None,
                "reasoning": "LLM semantic check unavailable or no existing notes.",
            }

        flattened_titles: list[str] = []
        for note in existing_notes:
            title = str(note.get("title") or "")
            aliases = [str(a) for a in (note.get("aliases") or [])]
            if title:
                flattened_titles.append(title)
            flattened_titles.extend(aliases)

        prompt = (
            "Given this list of existing note titles: "
            f"{json.dumps(flattened_titles[:400], ensure_ascii=True)}\n"
            f"Determine whether any of them refers to the same concept as: \"{candidate}\"\n"
            "A match exists if they are:\n"
            "- The same concept under a different name or abbreviation\n"
            "- One is a direct alias or common shorthand of the other\n"
            "- They describe the exact same technical thing, even if worded differently\n"
            "Reply with JSON only: { \"match_found\": true | false, \"matched_note\": \"<filename or null>\", \"reasoning\": \"<one sentence>\" }"
        )

        try:
            response = self.client.generate_chat_completion(
                model=self.MODEL_SURGEON,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict semantic duplicate checker for IT note titles. Return JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
            )
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            data = json.loads(cleaned.strip())
            if not isinstance(data, dict):
                raise ValueError("Duplicate checker response was not a JSON object.")
            match_found = bool(data.get("match_found"))
            matched_note = data.get("matched_note")
            reasoning = str(data.get("reasoning") or "")
            matched_display = None
            if matched_note:
                matched_stem = Path(str(matched_note)).stem.lower()
                for note in existing_notes:
                    title = str(note.get("title") or "")
                    if title.lower() == matched_stem:
                        aliases = [str(a) for a in (note.get("aliases") or [])]
                        matched_display = self._preferred_display_alias(aliases, candidate)
                        matched_note = title
                        break
            return {
                "match_found": match_found,
                "matched_note": str(matched_note).strip() if matched_note else None,
                "matched_display": matched_display,
                "reasoning": reasoning or "Semantic check completed.",
            }
        except Exception as exc:
            logger.warning("Semantic duplicate check failed for '%s': %s", candidate, exc)
            return {
                "match_found": False,
                "matched_note": None,
                "matched_display": None,
                "reasoning": "Semantic check failed; proceeding as unmatched.",
            }

    def _preferred_display_alias(self, aliases: list[str], fallback: str) -> str:
        normalized_fallback = self._normalize_concept(fallback)
        for alias in aliases:
            if self._normalize_concept(alias) == normalized_fallback:
                return alias
        return fallback

    def _backfill_alias_for_existing(self, alias: str, existing_notes: list[dict[str, str | list[str]]], matched_note: str) -> None:
        for note in existing_notes:
            title = str(note.get("title") or "")
            if title != matched_note:
                continue
            path = str(note.get("path") or "").strip()
            if not path:
                return
            self._upsert_alias_on_note(Path(path), alias)
            return

    def _upsert_alias_on_note(self, note_path: Path, alias: str) -> None:
        try:
            content = note_path.read_text(encoding="utf-8")
            updated = self._upsert_aliases_in_markdown(content, [alias])
            if updated != content:
                note_path.write_text(updated, encoding="utf-8")
        except Exception as exc:
            logger.warning("Failed to backfill alias '%s' in %s: %s", alias, note_path, exc)

    def _upsert_aliases_in_markdown(self, content: str, aliases_to_add: list[str]) -> str:
        merged_aliases = self._merge_aliases([], aliases_to_add)
        top_match = re.match(r"(?ms)^---\s*\n(.*?)\n---\s*\n?", content)
        if not top_match:
            alias_block = self._format_aliases_line(merged_aliases)
            body = content.lstrip("\n")
            return f"---\n{alias_block}\n---\n\n{body}" if body else f"---\n{alias_block}\n---\n"

        frontmatter = top_match.group(1)
        rest = content[top_match.end():].lstrip("\n")
        existing_aliases = self._extract_aliases_from_text(frontmatter)
        merged_aliases = self._merge_aliases(existing_aliases, aliases_to_add)

        clean_frontmatter = re.sub(r"(?im)^aliases\s*:\s*\[(.*?)\]\s*$\n?", "", frontmatter)
        clean_frontmatter = re.sub(r"(?ims)^aliases\s*:\s*\n(?:\s*-\s*.*\n?)*", "", clean_frontmatter)
        clean_frontmatter = clean_frontmatter.strip()

        rebuilt_parts: list[str] = []
        if clean_frontmatter:
            rebuilt_parts.append(clean_frontmatter)
        rebuilt_parts.append(self._format_aliases_line(merged_aliases))
        rebuilt_frontmatter = "\n".join(rebuilt_parts)

        if rest:
            return f"---\n{rebuilt_frontmatter}\n---\n\n{rest}"
        return f"---\n{rebuilt_frontmatter}\n---\n"

    def _extract_aliases_from_text(self, frontmatter: str) -> list[str]:
        aliases: list[str] = []

        inline = re.search(r"(?im)^aliases\s*:\s*\[(.*?)\]\s*$", frontmatter)
        if inline:
            for token in inline.group(1).split(","):
                value = token.strip().strip("\"'")
                if value:
                    aliases.append(value)

        block = re.search(r"(?ims)^aliases\s*:\s*\n((?:\s*-\s*.*\n?)*)", frontmatter)
        if block:
            for line in block.group(1).splitlines():
                item = re.sub(r"^\s*-\s*", "", line).strip().strip("\"'")
                if item:
                    aliases.append(item)

        return self._merge_aliases([], aliases)

    def _merge_aliases(self, left: list[str], right: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for raw in left + right:
            value = str(raw).strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(value)
        return merged

    def _format_aliases_line(self, aliases: list[str]) -> str:
        rendered = [f'"{alias.replace("\\", "\\\\").replace("\"", "\\\"")}"' for alias in aliases]
        return f"aliases: [{', '.join(rendered)}]"

    def _normalize_concept(self, text: str) -> str:
        normalized = text.lower().strip()
        normalized = re.sub(r"\.(md|markdown)$", "", normalized)
        normalized = normalized.replace("&", " and ")
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _append_seeder_log(self, entry: dict[str, object]) -> None:
        logs: list[dict[str, object]] = []
        if self.seeder_log_path.exists():
            try:
                existing = json.loads(self.seeder_log_path.read_text(encoding="utf-8"))
                if isinstance(existing, list):
                    logs = [row for row in existing if isinstance(row, dict)]
            except Exception:
                logs = []

        logs.append(entry)
        self.seeder_log_path.write_text(json.dumps(logs, indent=2), encoding="utf-8")
