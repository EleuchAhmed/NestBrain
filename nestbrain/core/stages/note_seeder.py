import logging
from pathlib import Path
from ..nvidia_client import nvidia_client

logger = logging.getLogger(__name__)

class NoteSeeder:
    """Layer 2: Entity Growth Seeder
    Contains logic for both generating new stubs (The Seed Maker - devstral-2-123b)
    and patching existing notes (The Surgeon - glm-4.7).
    """

    MODEL_SEEDER = "devstral-2-123b-instruct-2512"
    MODEL_SURGEON = "THUDM/glm-4.7"

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.client = nvidia_client

    def _get_note_path(self, term: str) -> Path:
        """Helper to get a safe Markdown path for an entity term."""
        # Minimal sanitization for Windows/Unix
        safe_term = term.replace(":", " -").replace("/", "-").replace("\\", "-")
        return self.vault_path / f"{safe_term}.md"

    def process_extracted_term(self, term: str, master_note_context: str, subject_title: str) -> bool:
        """
        Determines if a note exists. If not, spawns The Seed Maker.
        If yes, spawns The Surgeon to carefully append new context.
        """
        note_path = self._get_note_path(term)

        if not note_path.exists():
            # Brand new concept -> Seed Maker
            logger.info(f"Term '{term}' not found in vault. Spawning The Seed Maker.")
            return self._seed_new_note(term, master_note_context, subject_title, note_path)
        else:
            # Exists -> Surgeon
            logger.info(f"Term '{term}' already exists. Spawning The Surgeon to append context.")
            existing_content = note_path.read_text(encoding="utf-8")
            return self._patch_existing_note(term, existing_content, master_note_context, subject_title, note_path)

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
            write_path.write_text(response_text.strip(), encoding="utf-8")
            return True
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
