import logging
from typing import List
from pathlib import Path
from ..nvidia_client import nvidia_client

logger = logging.getLogger(__name__)

class ConnectionAnnotator:
    """Layer 3: The Matchmaker (deepseek-v3.1)
    Given the final, vetted semantic connection between Note A and Note B, 
    writes a single "See Also" contextual reason binding the two, 
    appending it to the notes.
    """
    
    MODEL = "deepseek-ai/deepseek-v3.1"

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.client = nvidia_client

    def annotate_connections(self, new_note_title: str, new_note_content: str, target_notes: List[str]):
        """
        Takes the title and content of the source note, and the list of 
        semantically audited target note titles.
        Invokes The Matchmaker to explain *why* they are connected, 
        then appends that explanation to the target note in the vault.
        """
        if not target_notes:
            return

        logger.info(f"Matchmaker annotating {len(target_notes)} semantic connections for '{new_note_title}'.")

        for title in target_notes:
            try:
                target_file = self.vault_path / f"{title}.md"
                if not target_file.exists():
                    continue

                target_content = target_file.read_text(encoding="utf-8")
                
                # Ask the Matchmaker to write a 1-sentence connection
                annotation = self._generate_annotation(new_note_title, new_note_content, title, target_content)
                
                # Append to the target note safely
                if annotation:
                    with target_file.open("a", encoding="utf-8") as f:
                        # Ensures there's a blank line
                        f.write(f"\n\n---\n**See Also:** [[{new_note_title}]] - {annotation}\n")
                        
            except Exception as e:
                logger.error(f"Matchmaker failed while processing target '{title}': {e}")

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
