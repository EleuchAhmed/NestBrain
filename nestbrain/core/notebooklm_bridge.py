"""NotebookLM bridge for Python GUI pipeline. Native implementation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .notebooklm_auth import get_auth_tokens
from notebooklm.client import NotebookLMClient
from notebooklm.rpc import AudioFormat, AudioLength, VideoFormat, VideoStyle


class NotebookLMBridge:
    """Async client interacting with NotebookLM natively."""

    def __init__(self, app_root: str | Path):
        self.app_root = Path(app_root).resolve()

    async def create_notebook(self, title: str) -> str:
        tokens = await get_auth_tokens()
        async with NotebookLMClient(tokens) as client:
            notebook = await client.notebooks.create(title=title)
            return notebook.id

    async def ingest_file(self, notebook_id: str, path: str) -> bool:
        try:
            tokens = await get_auth_tokens()
            async with NotebookLMClient(tokens) as client:
                await client.sources.add_file(notebook_id=notebook_id, file_path=path, wait=True)
                return True
        except Exception:
            return False

    async def ingest_url(self, notebook_id: str, url: str) -> bool:
        try:
            tokens = await get_auth_tokens()
            async with NotebookLMClient(tokens) as client:
                await client.sources.add_url(notebook_id=notebook_id, url=url, wait=True)
                return True
        except Exception:
            return False

    async def ingest_text(self, notebook_id: str, title: str, content: str) -> bool:
        try:
            tokens = await get_auth_tokens()
            async with NotebookLMClient(tokens) as client:
                await client.sources.add_text(notebook_id=notebook_id, title=title, content=content, wait=True)
                return True
        except Exception:
            return False

    async def interrogate(self, notebook_id: str, queries: list[str]) -> list[str]:
        try:
            tokens = await get_auth_tokens()
            responses = []
            async with NotebookLMClient(tokens) as client:
                for query in queries:
                    try:
                        res = await client.chat.ask(notebook_id=notebook_id, question=query)
                        responses.append(f"### Query: {query}\n\n{res.answer}")
                    except Exception as e:
                        responses.append(f"### Query: {query}\n\nWarning: {str(e)}")
                    await asyncio.sleep(1)
            return responses
        except Exception:
            return []

    async def synthesize(self, notebook_id: str, query: str) -> str:
        try:
            tokens = await get_auth_tokens()
            async with NotebookLMClient(tokens) as client:
                res = await client.chat.ask(notebook_id=notebook_id, question=query)
                return res.answer
        except Exception:
            return ""

    async def generate_media(self, notebook_id: str, media_type: str) -> dict[str, Any]:
        try:
            tokens = await get_auth_tokens()
            async with NotebookLMClient(tokens) as client:
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        if media_type == "audio":
                            status = await client.artifacts.generate_audio(
                                notebook_id,
                                audio_format=AudioFormat.DEEP_DIVE,
                                audio_length=AudioLength.DEFAULT,
                            )
                        else:
                            status = await client.artifacts.generate_video(
                                notebook_id,
                                video_format=VideoFormat.EXPLAINER,
                                video_style=VideoStyle.AUTO_SELECT,
                            )
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        await asyncio.sleep(5)

                timeout = 600.0 if media_type == "video" else 300.0
                result = await client.artifacts.wait_for_completion(
                    notebook_id,
                    status.task_id,
                    timeout=timeout,
                )

                if result.is_complete:
                    artifact = await client.artifacts.get(notebook_id, status.task_id)
                    return {
                        "status": "success",
                        "artifactId": status.task_id,
                        "url": getattr(artifact, "url", None),
                    }
                return {"status": "failed", "error": result.error or "Generation timed out"}
        except Exception:
            return {"status": "error"}

    async def download_media(self, notebook_id: str, media_type: str, artifact_id: str, output_path: str) -> str:
        try:
            tokens = await get_auth_tokens()
            async with NotebookLMClient(tokens) as client:
                if media_type == "audio":
                    saved_path = await client.artifacts.download_audio(notebook_id, output_path, artifact_id=artifact_id)
                else:
                    saved_path = await client.artifacts.download_video(notebook_id, output_path, artifact_id=artifact_id)
                return saved_path
        except Exception:
            return ""
