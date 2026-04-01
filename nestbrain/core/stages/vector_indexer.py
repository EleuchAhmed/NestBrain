import os
import json
import logging
import math
from pathlib import Path
from typing import Dict, List, Tuple
from ..nvidia_client import nvidia_client

logger = logging.getLogger(__name__)

class VectorIndexer:
    """Layer 3: The Librarian (nv-embedqa-e5-v5)
    Converts vault notes into mathematical vectors for semantic similarity indexing.
    Currently uses flat JSON storage for lightweight viability.
    """
    
    MODEL = "nvidia/nv-embedqa-e5-v5"

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.index_file = self.vault_path / ".nestbrain_index.json"
        self.client = nvidia_client
        self.index_data = self._load_index()

    def _load_index(self) -> Dict[str, List[float]]:
        if self.index_file.exists():
            try:
                return json.loads(self.index_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                logger.warning("Failed to decode index map. Starting fresh.")
                return {}
        return {}

    def _save_index(self):
        self.index_file.write_text(json.dumps(self.index_data), encoding="utf-8")

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm_a = math.sqrt(sum(a * a for a in vec1))
        norm_b = math.sqrt(sum(b * b for b in vec2))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def embed_new_note(self, note_title: str, content: str) -> List[float]:
        """Generate embedding for a note, truncating to avoid token limits."""
        logger.info(f"Generating embedding for '{note_title}'...")
        
        try:
            # nv-embedqa-e5-v5 may have a context limit; we pass a chunk.
            # Alternatively, the embedding API requires explicit input_type="query" or "passage"
            embeddings = self.client.generate_embeddings(
                model=self.MODEL,
                input_texts=[content[:4000]], # naive split
                input_type="passage"
            )
            
            vec = embeddings[0]
            self.index_data[note_title] = vec
            self._save_index()
            return vec
            
        except Exception as e:
            logger.error(f"Failed to embed note '{note_title}': {e}")
            return []

    def find_similar_notes(self, new_note_vec: List[float], top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Scans the vault index for the top-K highest similarity notes.
        Returns tuples of (note_title, similarity_score).
        """
        if not new_note_vec:
            return []

        results = []
        for title, vec in self.index_data.items():
            # Skip exact matches
            if vec == new_note_vec:
                continue
            
            score = self._cosine_similarity(new_note_vec, vec)
            results.append((title, score))
            
        # Sort descending by score
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
