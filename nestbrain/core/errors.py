from __future__ import annotations

import traceback
from typing import Any


def build_error_payload(exc: Exception, source: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a structured error payload that UI and logs can consume consistently."""
    payload: dict[str, Any] = {
        "source": source,
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }
    if context:
        payload["context"] = context
    return payload
