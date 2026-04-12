import asyncio

import nestbrain.core.notebooklm_bridge as bridge_module
from nestbrain.core.notebooklm_bridge import NotebookLMBridge
from nestbrain.core.notebooklm_auth import NotebookLMAuthRequiredError


class _FakeSources:
    def __init__(self, calls):
        self.calls = calls

    async def add_text(self, **kwargs):
        self.calls.append(("text", kwargs))

    async def add_file(self, **kwargs):
        self.calls.append(("file", kwargs))

    async def add_url(self, **kwargs):
        self.calls.append(("url", kwargs))


class _FakeClient:
    def __init__(self, tokens, calls):
        self.tokens = tokens
        self.calls = calls
        self.sources = _FakeSources(calls)

    async def __aenter__(self):
        self.calls.append(("enter", self.tokens))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.calls.append(("exit", exc_type))
        return False


class _FakeNotebookResult:
    def __init__(self, notebook_id: str):
        self.id = notebook_id


class _FakeNotebooks:
    def __init__(self, calls):
        self.calls = calls

    async def create(self, *, title: str):
        self.calls.append(("create_notebook", title))
        return _FakeNotebookResult("nb-created")


class _FakeClientWithNotebooks(_FakeClient):
    def __init__(self, tokens, calls):
        super().__init__(tokens, calls)
        self.notebooks = _FakeNotebooks(calls)


def test_ingest_methods_use_bounded_wait(monkeypatch):
    calls = []

    async def fake_get_auth_tokens():
        return "fake-tokens"

    async def fake_wait_for(awaitable, timeout):
        calls.append(("wait_for", timeout))
        return await awaitable

    def fake_client_factory(tokens):
        return _FakeClient(tokens, calls)

    monkeypatch.setattr(bridge_module, "get_auth_tokens", fake_get_auth_tokens)
    monkeypatch.setattr(bridge_module, "NotebookLMClient", fake_client_factory)
    monkeypatch.setattr(bridge_module.asyncio, "wait_for", fake_wait_for)

    bridge = NotebookLMBridge("c:/tmp")

    assert asyncio.run(bridge.ingest_text("nb-1", "Sample Title", "Sample body")) is True
    assert asyncio.run(bridge.ingest_file("nb-2", "sample.pdf")) is True
    assert asyncio.run(bridge.ingest_url("nb-3", "https://example.com")) is True

    wait_for_calls = [entry for entry in calls if entry[0] == "wait_for"]
    assert wait_for_calls == [
        ("wait_for", bridge.INGEST_TIMEOUT_SECONDS),
        ("wait_for", bridge.INGEST_TIMEOUT_SECONDS),
        ("wait_for", bridge.INGEST_TIMEOUT_SECONDS),
    ]

    text_call = next(entry for entry in calls if entry[0] == "text")
    assert text_call[1]["wait"] is True
    file_call = next(entry for entry in calls if entry[0] == "file")
    assert file_call[1]["wait"] is True
    url_call = next(entry for entry in calls if entry[0] == "url")
    assert url_call[1]["wait"] is True


def test_ingest_text_returns_false_on_timeout(monkeypatch):
    calls = []

    async def fake_get_auth_tokens():
        return "fake-tokens"

    async def timeout_wait_for(awaitable, timeout):
        calls.append(("wait_for", timeout))
        awaitable.close()
        raise asyncio.TimeoutError

    def fake_client_factory(tokens):
        return _FakeClient(tokens, calls)

    monkeypatch.setattr(bridge_module, "get_auth_tokens", fake_get_auth_tokens)
    monkeypatch.setattr(bridge_module, "NotebookLMClient", fake_client_factory)
    monkeypatch.setattr(bridge_module.asyncio, "wait_for", timeout_wait_for)

    bridge = NotebookLMBridge("c:/tmp")

    assert asyncio.run(bridge.ingest_text("nb-1", "Sample Title", "Sample body")) is False
    assert calls[0] == ("enter", "fake-tokens")
    assert calls[1] == ("wait_for", bridge.INGEST_TIMEOUT_SECONDS)


def test_create_notebook_returns_id(monkeypatch):
    calls = []

    async def fake_get_auth_tokens():
        return "fake-tokens"

    def fake_client_factory(tokens):
        return _FakeClientWithNotebooks(tokens, calls)

    monkeypatch.setattr(bridge_module, "get_auth_tokens", fake_get_auth_tokens)
    monkeypatch.setattr(bridge_module, "NotebookLMClient", fake_client_factory)

    bridge = NotebookLMBridge("c:/tmp")

    notebook_id = asyncio.run(bridge.create_notebook("My Collection"))

    assert notebook_id == "nb-created"
    assert ("create_notebook", "My Collection") in calls


def test_ingest_text_reraises_auth_required(monkeypatch):
    async def fake_get_auth_tokens():
        raise NotebookLMAuthRequiredError("auth required")

    monkeypatch.setattr(bridge_module, "get_auth_tokens", fake_get_auth_tokens)

    bridge = NotebookLMBridge("c:/tmp")

    try:
        asyncio.run(bridge.ingest_text("nb-1", "Sample Title", "Sample body"))
    except NotebookLMAuthRequiredError as exc:
        assert "auth required" in str(exc)
    else:
        raise AssertionError("NotebookLMAuthRequiredError was not raised")


def test_create_notebook_reraises_auth_required(monkeypatch):
    async def fake_get_auth_tokens():
        raise NotebookLMAuthRequiredError("token expired")

    monkeypatch.setattr(bridge_module, "get_auth_tokens", fake_get_auth_tokens)

    bridge = NotebookLMBridge("c:/tmp")

    try:
        asyncio.run(bridge.create_notebook("My Collection"))
    except NotebookLMAuthRequiredError as exc:
        assert "token expired" in str(exc)
    else:
        raise AssertionError("NotebookLMAuthRequiredError was not raised")