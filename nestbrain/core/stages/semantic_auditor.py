import logging
import re
from typing import List, Tuple, Dict, Any
from pathlib import Path
from ..nvidia_client import nvidia_client
from ..vault_manager import find_note_path

logger = logging.getLogger(__name__)

class SemanticAuditor:
    """Layer 3: The Auditor (rerank-qa-mistral-4b)
    Evaluates the top-K semantic matches from the indexer to 
    filter out low-relevance "false positive" connections.
    """
    
    MODEL = "nvidia/nv-rerankqa-mistral-4b-v3"

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

    def audit_connections(self, new_note_content: str, semantic_matches: List[Tuple[str, float]], threshold_logit: float = 0.0) -> List[Tuple[str, float]]:
        """
        Takes the raw text of the newly minted note, compares it against the text 
        of the conceptually matched notes, and runs them through the reranking model.
        Returns the finalized list of note titles that survived the audit.
        """
        if not semantic_matches:
            return []

        logger.info(f"Auditing {len(semantic_matches)} potential graph connections.")

        passages = []
        mapping: dict[int, Tuple[str, float]] = {}

        for idx, (title, score) in enumerate(semantic_matches):
            try:
                # Read passage from the vault (limit length to prevent overflowing reranker)
                note_file = find_note_path(title, self.vault_path)
                if note_file is None or not note_file.exists():
                    continue

                content = note_file.read_text(encoding="utf-8")
                truncated = content[:3000] # Rerankers typically handle shorter contexts 
                passages.append({"text": truncated})
                mapping[idx] = (title, score)
            except Exception as e:
                logger.warning(f"Could not read matched note {title}: {e}")

        if not passages:
            return []

        # We constrain the query part slightly to keep context tight
        query_text = new_note_content[:2000]

        try:
            rankings = self.client.rerank(
                model=self.MODEL,
                query=query_text,
                passages=passages
            )
            
            # The NVIDIA rerank API usually returns items with an 'index' and a 'logit' score
            # A higher logit indicates a stronger semantic relevance.
            survivors = []
            for item in rankings:
                original_idx = item.get("index")
                logit = item.get("logit", -100)
                
                if logit >= threshold_logit:
                    original_match = mapping.get(original_idx)
                    if original_match:
                        survivors.append(original_match)
                else:
                    logger.debug(f"Connection {mapping.get(original_idx)} rejected by Auditor (logit {logit}).")

            logger.info(f"{len(survivors)} connections survived the audit.")
            return survivors

        except Exception as e:
            logger.error(f"Failed to audit semantic connections: {e}")
            # Fallback: Just return the top 2 if API fails
            fallback = semantic_matches[:2]
            return fallback
