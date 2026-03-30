"""NotebookLM bridge for Python GUI pipeline. Wraps notebooklm_operations.py."""

from __future__ import annotations

import json
import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any


class NotebookLMBridge:
    """Async wrapper around NotebookLM operations via Python subprocess."""

    def __init__(self, app_root: str | Path):
        self.app_root = Path(app_root).resolve()
        self.script_path = self.app_root / "scripts" / "notebooklm_operations.py"
        if not self.script_path.exists():
            raise FileNotFoundError(f"notebooklm_operations.py not found at {self.script_path}")

    async def call_notebooklm(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        """Call NotebookLM operations via stdin/stdout subprocess bridge."""
        payload = json.dumps({"action": action, "args": args})
        
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(self.script_path),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate(payload.encode())
            stdout_text = stdout.decode("utf-8", errors="ignore")
            stderr_text = stderr.decode("utf-8", errors="ignore")
            
            if process.returncode != 0:
                if "No module named 'notebooklm'" in stderr_text:
                    raise RuntimeError(
                        "NotebookLM Python dependency is missing. Install it in the project venv before running the full pipeline."
                    )
                raise RuntimeError(f"Process exited with code {process.returncode}: {stderr_text}")
            
            # Extract JSON from output (may have extra logging)
            first_brace = stdout_text.find("{")
            last_brace = stdout_text.rfind("}")
            if first_brace == -1 or last_brace == -1:
                raise RuntimeError(f"No JSON found in NotebookLM response: {stdout_text[:500]}")
            
            json_str = stdout_text[first_brace : last_brace + 1]
            result = json.loads(json_str)
            
            if result.get("error"):
                raise RuntimeError(f"NotebookLM error: {result['error']}")
            
            return result
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON from NotebookLM: {e}")
        except Exception as e:
            raise RuntimeError(f"NotebookLM bridge error: {e}")

    async def create_notebook(self, title: str) -> str:
        """Create a new NotebookLM notebook. Returns notebook ID."""
        result = await self.call_notebooklm("createNotebook", {"title": title})
        return result.get("notebookId", "")

    async def ingest_file(self, notebook_id: str, path: str) -> bool:
        """Ingest a PDF file into notebook. Returns success."""
        try:
            await self.call_notebooklm("ingestFile", {"notebookId": notebook_id, "path": path})
            return True
        except Exception:
            return False

    async def ingest_url(self, notebook_id: str, url: str) -> bool:
        """Ingest a URL source into notebook. Returns success."""
        try:
            await self.call_notebooklm("ingestUrl", {"notebookId": notebook_id, "url": url})
            return True
        except Exception:
            return False

    async def ingest_text(self, notebook_id: str, title: str, content: str) -> bool:
        """Ingest text content into notebook. Returns success."""
        try:
            await self.call_notebooklm(
                "ingestText",
                {"notebookId": notebook_id, "title": title, "content": content},
            )
            return True
        except Exception:
            return False

    async def interrogate(self, notebook_id: str, queries: list[str]) -> list[str]:
        """Run interrogation queries. Returns list of responses."""
        try:
            result = await self.call_notebooklm(
                "interrogate",
                {"notebookId": notebook_id, "queries": queries},
            )
            return result.get("responses", [])
        except Exception:
            return []

    async def synthesize(self, notebook_id: str, query: str) -> str:
        """Synthesize grounded response from notebook. Returns text."""
        try:
            result = await self.call_notebooklm(
                "synthesize",
                {"notebookId": notebook_id, "query": query},
            )
            return result.get("answer", "")
        except Exception:
            return ""

    async def generate_media(self, notebook_id: str, media_type: str) -> dict[str, Any]:
        """Generate media artifact (audio/video). Returns artifact metadata."""
        try:
            result = await self.call_notebooklm(
                "generateMedia",
                {"notebookId": notebook_id, "type": media_type},
            )
            return result
        except Exception:
            return {"status": "error"}

    async def download_media(self, notebook_id: str, media_type: str, artifact_id: str, output_path: str) -> str:
        """Download media artifact to local file. Returns file path."""
        try:
            result = await self.call_notebooklm(
                "downloadMedia",
                {
                    "notebookId": notebook_id,
                    "type": media_type,
                    "artifactId": artifact_id,
                    "outputPath": output_path,
                },
            )
            return result.get("path", "")
        except Exception:
            return ""
