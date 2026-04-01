"""
Legacy compatibility wrapper for the canonical NotebookLM bridge entrypoint.

Canonical file:
- automation/notebooklm-bridge/notebooklm-operations.py
"""

import asyncio
import importlib.util
from pathlib import Path


def _load_canonical_module():
    canonical = Path(__file__).resolve().parents[1] / "automation" / "notebooklm-bridge" / "notebooklm-operations.py"
    spec = importlib.util.spec_from_file_location("automation_notebooklm_bridge", canonical)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load canonical NotebookLM bridge module: {canonical}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def main():
    module = _load_canonical_module()
    await module.main()


if __name__ == "__main__":
    asyncio.run(main())
