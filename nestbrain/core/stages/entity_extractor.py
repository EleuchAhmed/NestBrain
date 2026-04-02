import json
import logging
import re
from typing import List
from ..nvidia_client import nvidia_client

logger = logging.getLogger(__name__)

class EntityExtractor:
    """Layer 2: The Scout (deepseek-v3.1)
    Scans the Master Note to extract technical terms and knowledge entities as a JSON list.
    """
    
    MODEL = "deepseek-ai/deepseek-r1"

    def __init__(self):
        self.client = nvidia_client
        self.used_fallback = False
        self.last_error = ""

    def extract_entities(self, master_note: str) -> List[str]:
        """
        Parses the fully synthesized master note and isolates all standalone 
        concepts, technical details, people, frameworks, etc.
        Returns a list of clean string entity names.
        """
        logger.info("Extracting knowledge entities from Master Note...")

        system_prompt = (
            "You are an expert Data Scout. Your job is to extract fundamental knowledge entities "
            "(technical terms, frameworks, prominent figures, specific algorithms, protocols) from the provided text.\n"
            "Return ONLY a cleanly formatted JSON array of strings containing the exact entity names.\n"
            "Ignore generic words, focus on noun phrases that deserve their own independent Wiki-style page.\n"
            "Do NOT include markdown formatting or explanations."
        )

        user_content = f"MASTER NOTE CONTENT:\n{master_note}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            response_text = self.client.generate_chat_completion(
                model=self.MODEL,
                messages=messages,
                temperature=0.1
            )
            
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
                
            entities = json.loads(cleaned_text.strip())
            
            if not isinstance(entities, list):
                raise ValueError("Response was not a JSON list of strings.")
                
            logger.info(f"Extracted {len(entities)} distinct entities.")
            self.used_fallback = False
            self.last_error = ""
            return [str(e).strip() for e in entities if e]

        except Exception as e:
            logger.error(f"Failed to extract entities: {e}")
            self.used_fallback = True
            self.last_error = str(e)
            return self._extract_entities_heuristic(master_note)

    def _extract_entities_heuristic(self, master_note: str) -> List[str]:
        """Fallback extraction from wikilinks, acronyms, and title-cased phrases."""
        candidates: list[str] = []

        for link in re.findall(r"\[\[([^\]|#]+)", master_note):
            value = link.strip()
            if value:
                candidates.append(value)

        for acronym in re.findall(r"\b[A-Z]{2,8}\b", master_note):
            candidates.append(acronym.strip())

        for phrase in re.findall(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", master_note):
            cleaned = phrase.strip()
            if len(cleaned) > 3:
                candidates.append(cleaned)

        filtered: list[str] = []
        seen: set[str] = set()
        for entity in candidates:
            entity = re.sub(r"\s+", " ", entity).strip(" -")
            if len(entity) < 3:
                continue
            if entity.lower() in {"the", "and", "for", "with", "from", "core findings"}:
                continue
            key = entity.lower()
            if key in seen:
                continue
            seen.add(key)
            filtered.append(entity)
            if len(filtered) >= 30:
                break

        logger.info(f"Heuristic extractor returned {len(filtered)} entities.")
        return filtered
