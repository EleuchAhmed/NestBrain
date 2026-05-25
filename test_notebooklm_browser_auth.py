import nestbrain.core.notebooklm_browser_auth as browser_auth


def test_decrypt_chromium_cookie_plaintext():
    assert browser_auth._decrypt_chromium_cookie(b"plain-value", b"0" * 32) == "plain-value"


def test_resolve_auth_mode_defaults_to_auto(monkeypatch):
    monkeypatch.delenv(browser_auth.AUTH_MODE_ENV, raising=False)
    assert browser_auth._resolve_auth_mode() == "auto"


def test_resolve_auth_mode_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv(browser_auth.AUTH_MODE_ENV, "unsupported")
    assert browser_auth._resolve_auth_mode() == "auto"


def test_detect_system_browser_uses_override(monkeypatch, tmp_path):
    fake_browser = tmp_path / "chrome.exe"
    fake_browser.write_text("", encoding="utf-8")

    monkeypatch.setenv(browser_auth.AUTH_CHROMIUM_EXECUTABLE_ENV, str(fake_browser))
    detected = browser_auth._detect_system_browser_executable()

    assert detected == fake_browser


def test_system_browser_user_data_dir_for_chrome(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/test/AppData/Local")
    path = browser_auth._system_browser_user_data_dir(browser_auth.Path("C:/Program Files/Google/Chrome/Application/chrome.exe"))
    assert path is not None
    assert str(path).replace("\\", "/").endswith("Google/Chrome/User Data")


def test_system_browser_user_data_dir_for_edge(monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", "C:/Users/test/AppData/Local")
    path = browser_auth._system_browser_user_data_dir(browser_auth.Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"))
    assert path is not None
    assert str(path).replace("\\", "/").endswith("Microsoft/Edge/User Data")


def test_resolve_auth_mode_ignores_unknown_value(monkeypatch):
    monkeypatch.setenv(browser_auth.AUTH_MODE_ENV, "trusted-but-not-really")
    assert browser_auth._resolve_auth_mode() == "auto"
