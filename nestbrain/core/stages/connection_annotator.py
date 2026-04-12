import logging
import re
import json
from datetime import datetime, timezone
from typing import List, Tuple
from pathlib import Path
from ..nvidia_client import nvidia_client
from ..vault_manager import find_note_path
from ..vault_manager import append_vault_log_entry
from ..utils import to_slug

logger = logging.getLogger(__name__)

class ConnectionAnnotator:
    """Layer 3: The Matchmaker (deepseek-v3.1)
    Given the final, vetted semantic connection between Note A and Note B, 
    writes a single "See Also" contextual reason binding the two, 
    appending it to the notes.
    """
    
    MODEL = "deepseek-ai/deepseek-r1"
    TOP_K = 5
    MIN_SCORE = 0.75

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.client = nvidia_client

    def _sanitize_filename(self, title: str) -> str:
        """Sanitize title to safe filename (prevent path traversal)."""
        # Remove path separators and unsafe characters
        safe = re.sub(r"[/\\:*?\"<>|]", "-", title)
        # Replace multiple dashes with single dash
        safe = re.sub(r"-+", "-", safe)
        return safe.strip("-")

    def annotate_connections(self, new_note_title: str, new_note_summary: str, target_notes: List[Tuple[str, float]]):
        """
        Takes the title and summary of the source note, and the list of
        semantically audited target note paths/titles with scores.
        Invokes The Matchmaker to explain *why* they are connected, 
        then appends that explanation to the target note in the vault.
        """
        if not target_notes:
            return

        ordered_targets = sorted(target_notes, key=lambda item: item[1], reverse=True)[: self.TOP_K]
        logger.info(f"Matchmaker annotating {len(ordered_targets)} semantic connections for '{new_note_title}'.")

        for target_ref, score in ordered_targets:
            if score < self.MIN_SCORE:
                continue
            try:
                target_file = self._resolve_target_path(target_ref)
                if target_file is None or not target_file.exists():
                    continue

                target_content = target_file.read_text(encoding="utf-8")
                target_title = target_file.stem
                if self._has_propagation_record(new_note_title, target_title):
                    continue
                if f"[[{new_note_title}]]" in target_content:
                    continue
                
                # Ask the Matchmaker to write a 1-sentence connection
                annotation = self._generate_annotation(new_note_title, new_note_summary, target_title, target_content)
                
                # Append to the target note safely
                if annotation:
                    with target_file.open("a", encoding="utf-8") as f:
                        f.write(f"\n\n## Related — [[{new_note_title}]]\n> {annotation.strip()}\n")
                    append_vault_log_entry(
                        self.vault_path,
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "action": "propagation",
                            "updated": target_title,
                            "linked_to": new_note_title,
                            "score": float(score),
                        },
                    )
                        
            except Exception as e:
                logger.error(f"Matchmaker failed while processing target '{target_ref}': {e}")

    def _resolve_target_path(self, target_ref: str) -> Path | None:
        candidate = Path(target_ref)
        if candidate.exists():
            return candidate
        resolved = find_note_path(target_ref, self.vault_path)
        if resolved is not None:
            return resolved
        if to_slug(target_ref) != target_ref:
            return find_note_path(candidate.stem, self.vault_path)
        return None

    def _has_propagation_record(self, source_title: str, target_title: str) -> bool:
        log_path = self.vault_path / "vault_log.jsonl"
        if not log_path.exists():
            return False

        source_slug = to_slug(source_title)
        target_slug = to_slug(target_title)
        try:
            for line in log_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    continue
                if str(record.get("action")) != "propagation":
                    continue
                if to_slug(str(record.get("linked_to") or "")) != source_slug:
                    continue
                if to_slug(str(record.get("updated") or "")) != target_slug:
                    continue
                return True
        except Exception:
            return False
        return False

    def _generate_annotation(self, new_title: str, new_content: str, old_title: str, old_content: str) -> str:
        """Uses deepseek-v3.1 to synthesize the bridging context."""

        system_prompt = (
            "You are an expert Graph Matchmaker. You will be provided with two conceptually related notes from a knowledge vault.\n"
            "Write exactly ONE concise sentence explaining WHY the new note is conceptually similar or highly relevant to the old note.\n"
            "Do NOT reference the notes directly as 'Note A' or 'The new note'. Speak directly to the semantic relationship.\n"
            "Example: 'Both frameworks solve asynchronous state management but target different UI rendering paradigms.'"
        )

        user_content = (
            f"Note 1 (New): {new_title}\n{new_content[:1500]}\n\n"
            f"Note 2 (Existing): {old_title}\n{old_content[:1500]}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            response_text = self.client.generate_chat_completion(
                model=self.MODEL,
                messages=messages,
                temperature=0.3
            )
            
            # Clean up the output string
            sentence = response_text.strip()
            # If the model hallucinates formatting
            sentence = sentence.replace("---\n", "").replace("**See Also:**", "").strip()
            return sentence

        except Exception as e:
            logger.error(f"Failed to generate Matchmaker annotation: {e}")
            return "Shares deep semantic connections based on vault indexation."
