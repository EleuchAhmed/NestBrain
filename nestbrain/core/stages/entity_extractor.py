import json
import logging
import re
from typing import Any, List
from ..nvidia_client import nvidia_client

logger = logging.getLogger(__name__)

class EntityExtractor:
    """Layer 2: The Scout (deepseek-v3.1)
    Scans the Master Note to extract technical terms and knowledge entities as a JSON list.
    """
    
    MODEL = "deepseek-ai/deepseek-v3.2"

    def __init__(self):
        self.client = nvidia_client
        self.used_fallback = False
        self.last_error = ""
        self.last_scored_entities: list[dict[str, Any]] = []

    def extract_entities(self, master_note: str) -> List[str]:
        """
        Parses the fully synthesized master note and isolates all standalone 
        concepts, technical details, people, frameworks, etc.
        Returns a list of clean string entity names.
        """
        logger.info("Extracting knowledge entities from Master Note...")

        system_prompt = (
            "You are an expert IT Knowledge Entity Extractor.\n"
            "Extract only concrete, specific IT technical entities from the provided master note.\n"
            "Every extracted entity MUST satisfy ALL rules:\n"
            "1) Specificity: named concept/protocol/technology/pattern/algorithm/tool/standard, not a generic noun.\n"
            "2) Noteworthiness: an IT professional could write >=200 words about it in isolation.\n"
            "3) Distinctness: one precise concept, not a broad category.\n"
            "4) IT Domain: networking, operating systems, databases, software architecture, security, DevOps, programming languages/paradigms, distributed systems, hardware/low-level, or cloud infrastructure.\n"
            "Output STRICT JSON array only. Each item must contain:\n"
            "- entity (string)\n"
            "- confidence (number 0.0 to 1.0)\n"
            "- justification (single line string)\n"
            "Do not include markdown or extra keys."
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
                
            payload = json.loads(cleaned_text.strip())
            if not isinstance(payload, list):
                raise ValueError("Response was not a JSON list.")

            scored_entities: list[dict[str, Any]] = []
            for item in payload:
                if isinstance(item, str):
                    # Backward-compatible parsing if a model returns legacy string arrays.
                    entity = item.strip()
                    if entity:
                        scored_entities.append(
                            {
                                "entity": entity,
                                "confidence": 0.80,
                                "justification": "Legacy string output treated as likely technical entity.",
                            }
                        )
                    continue

                if not isinstance(item, dict):
                    continue
                entity = str(item.get("entity", "")).strip()
                justification = str(item.get("justification", "")).strip()
                try:
                    confidence = float(item.get("confidence", 0.0))
                except (TypeError, ValueError):
                    confidence = 0.0
                confidence = max(0.0, min(1.0, confidence))
                if not entity or not justification:
                    continue
                scored_entities.append(
                    {
                        "entity": entity,
                        "confidence": confidence,
                        "justification": justification,
                    }
                )

            self.last_scored_entities = scored_entities
            entities = [
                row["entity"]
                for row in scored_entities
                if row["confidence"] >= 0.75
            ]

            logger.info(
                "Extracted %d entities, %d passed confidence gate >= 0.75.",
                len(scored_entities),
                len(entities),
            )
            self.used_fallback = False
            self.last_error = ""
            return [str(e).strip() for e in entities if e]

        except Exception as e:
            logger.error(f"Failed to extract entities: {e}")
            self.used_fallback = True
            self.last_error = str(e)
            fallback = self._extract_entities_heuristic(master_note)
            self.last_scored_entities = [
                {
                    "entity": e,
                    "confidence": 0.76,
                    "justification": "Heuristic extraction from explicit technical cues.",
                }
                for e in fallback
            ]
            return fallback

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

        generic_terms = {
            "strategy", "role", "other", "advanced", "evolution", "system", "technology",
            "framework", "component", "process", "method", "approach", "model", "pattern",
            "architecture", "infrastructure", "development", "software", "hardware",
        }

        filtered: list[str] = []
        seen: set[str] = set()
        for entity in candidates:
            entity = re.sub(r"\s+", " ", entity).strip(" -")
            if len(entity) < 3:
                continue
            lower = entity.lower()
            if lower in {"the", "and", "for", "with", "from", "core findings"}:
                continue
            if lower in generic_terms:
                continue
            if re.fullmatch(r"[a-z]+", lower) and len(lower.split()) == 1:
                continue
            key = lower
            if key in seen:
                continue
            seen.add(key)
            filtered.append(entity)
            if len(filtered) >= 30:
                break

        logger.info(f"Heuristic extractor returned {len(filtered)} entities.")
        return filtered
