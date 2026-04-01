from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


class OllamaClientError(Exception):
    pass


class OllamaClient:
    """HTTP client wrapper for NVIDIA NIM API (DeepSeek V3.1)."""

    def __init__(self, host: str = "https://integrate.api.nvidia.com/v1", model: str = "deepseek-ai/deepseek-v3.1", timeout: int = 90) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        
        # Ensure the client uses OpenAI-compatible SDK format with Bearer token
        self.client = OpenAI(
            base_url=self.host,
            api_key=os.environ["NVIDIA_API_KEY"]
        )

    def generate(self, prompt: str, model: str | None = None) -> str:
        try:
            response = self.client.chat.completions.create(
                model=model or self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4096,
                stream=False
            )
            content = response.choices[0].message.content
            if content is None:
                return ""
            return content.strip()
        except KeyError as exc:
            raise OllamaClientError("Missing NVIDIA_API_KEY environment variable") from exc
        except Exception as exc:
            raise OllamaClientError(f"API request failed: {exc}") from exc

    def summarize_text(self, text: str, max_chars: int = 7000) -> str:
        clipped_text = text[:max_chars]
        prompt = (
            "Summarize the following knowledge note in 4 concise bullet points, "
            "including core concept, key methods, and practical insight.\n\n"
            f"{clipped_text}"
        )
        return self.generate(prompt)

    def generate_semantic_tags(self, text: str, max_tags: int = 8) -> list[str]:
        prompt = (
            "Return ONLY a JSON array of short semantic tags (no hashtags) for this note. "
            f"Maximum {max_tags} tags.\n\n{text[:5000]}"
        )
        output = self.generate(prompt)
        parsed = self._extract_json(output)

        if isinstance(parsed, list):
            return [str(tag).strip() for tag in parsed if str(tag).strip()][:max_tags]

        return []

    def suggest_links(self, note_titles: list[str], context: str) -> list[dict[str, str]]:
        if len(note_titles) < 2:
            return []

        prompt = (
            "Given these note/reference titles, suggest up to 12 conceptual links. "
            "Return ONLY JSON with format: [{\"source\":\"A\",\"target\":\"B\",\"reason\":\"...\"}].\n\n"
            f"Titles:\n{json.dumps(note_titles, ensure_ascii=False)}\n\n"
            f"Context:\n{context[:5000]}"
        )
        output = self.generate(prompt)
        parsed = self._extract_json(output)
        if isinstance(parsed, list):
            links: list[dict[str, str]] = []
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                source = str(item.get("source", "")).strip()
                target = str(item.get("target", "")).strip()
                reason = str(item.get("reason", "")).strip()
                if source and target and source != target:
                    links.append({"source": source, "target": target, "reason": reason})
            return links
        return []

    def _extract_json(self, text: str) -> Any:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        start_index = min((idx for idx in [text.find("["), text.find("{")] if idx != -1), default=-1)
        if start_index == -1:
            return None

        for end_index in range(len(text), start_index, -1):
            segment = text[start_index:end_index]
            try:
                return json.loads(segment)
            except json.JSONDecodeError:
                continue

        return None
