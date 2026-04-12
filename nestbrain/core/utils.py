from __future__ import annotations

import re


def to_slug(title: str) -> str:
    """Convert a display title to the canonical vault slug."""
    normalized = (title or "").lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return normalized or "node"