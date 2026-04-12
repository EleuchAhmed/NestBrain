import asyncio
import json

import nestbrain.core.notebooklm_auth as auth_module
from nestbrain.core.notebooklm_auth import NotebookLMAuthRequiredError


class _FakeClientSuccess:
    def __init__(self, tokens):
        self.tokens = tokens

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def refresh_auth(self):
        return None


class _FakeClientExpired:
    def __init__(self, tokens):
        self.tokens = tokens

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def refresh_auth(self):
        raise ValueError("expired")


def test_has_cached_auth_tokens_requires_cookies_and_csrf(tmp_path, monkeypatch):
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(json.dumps({"cookies": {"SID": "abc"}, "csrf_token": ""}), encoding="utf-8")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_FILE", str(auth_file))

    assert auth_module.has_cached_auth_tokens() is False


def test_get_auth_tokens_raises_when_missing(tmp_path, monkeypatch):
    auth_file = tmp_path / "missing-auth.json"
    monkeypatch.setenv("NOTEBOOKLM_AUTH_FILE", str(auth_file))

    try:
        asyncio.run(auth_module.get_auth_tokens())
    except NotebookLMAuthRequiredError as exc:
        assert "No NotebookLM authentication tokens found" in str(exc)
    else:
        raise AssertionError("NotebookLMAuthRequiredError was not raised")


def test_get_auth_tokens_raises_when_refresh_fails(tmp_path, monkeypatch):
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "cookies": {"SID": "abc"},
                "csrf_token": "csrf-token",
                "session_id": "session-id",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NOTEBOOKLM_AUTH_FILE", str(auth_file))
    monkeypatch.setattr(auth_module, "NotebookLMClient", _FakeClientExpired)

    try:
        asyncio.run(auth_module.get_auth_tokens())
    except NotebookLMAuthRequiredError as exc:
        assert "expired" in str(exc).lower() or "re-authenticate" in str(exc).lower()
    else:
        raise AssertionError("NotebookLMAuthRequiredError was not raised")


def test_get_auth_tokens_returns_tokens_when_valid(tmp_path, monkeypatch):
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "cookies": {"SID": "abc"},
                "csrf_token": "csrf-token",
                "session_id": "session-id",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("NOTEBOOKLM_AUTH_FILE", str(auth_file))
    monkeypatch.setattr(auth_module, "NotebookLMClient", _FakeClientSuccess)

    tokens = asyncio.run(auth_module.get_auth_tokens())

    assert tokens.csrf_token == "csrf-token"
    assert tokens.cookies.get("SID") == "abc"
