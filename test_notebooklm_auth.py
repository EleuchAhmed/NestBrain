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


def test_has_cached_auth_tokens_accepts_cookie_only_payload(tmp_path, monkeypatch):
    auth_file = tmp_path / "auth.json"
    auth_file.write_text(json.dumps({"cookies": {"SID": "abc"}, "csrf_token": ""}), encoding="utf-8")
    monkeypatch.setenv("NOTEBOOKLM_AUTH_FILE", str(auth_file))

    assert auth_module.has_cached_auth_tokens() is True


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


def test_normalize_auth_payload_rejects_invalid_shape():
    try:
        auth_module.normalize_auth_payload({"cookies": [], "csrf_token": "csrf"})
    except ValueError as exc:
        assert "cookies" in str(exc).lower()
    else:
        raise AssertionError("normalize_auth_payload should reject non-dict cookies")


def test_normalize_auth_payload_filters_empty_cookie_values():
    payload = auth_module.normalize_auth_payload(
        {
            "cookies": {
                "SID": "abc",
                "": "ignored",
                "HSID": "",
            },
            "csrf_token": "",
            "session_id": "",
        }
    )

    assert payload["cookies"] == {"SID": "abc"}
    assert payload["csrf_token"] == ""
    assert payload["session_id"] == ""


def test_save_auth_payload_accepts_cookie_only_payload(tmp_path, monkeypatch):
    auth_file = tmp_path / "auth.json"
    monkeypatch.setenv("NOTEBOOKLM_AUTH_FILE", str(auth_file))

    saved_path = auth_module.save_auth_payload({"cookies": {"SID": "abc"}})

    assert saved_path == auth_file
    data = json.loads(auth_file.read_text(encoding="utf-8"))
    assert data["cookies"] == {"SID": "abc"}
    assert data["csrf_token"] == ""
    assert data["session_id"] == ""
