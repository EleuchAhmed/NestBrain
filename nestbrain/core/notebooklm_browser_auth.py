from __future__ import annotations

import asyncio
import base64
import ctypes
import json
from datetime import datetime, timezone
import logging
import os
import re
import sqlite3
from pathlib import Path
import shutil
import tempfile
import sys
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from notebooklm.auth import AuthTokens
from notebooklm.client import NotebookLMClient
from notebooklm.exceptions import AuthError as NotebookLMClientAuthError, NotebookLMError

from playwright.async_api import async_playwright

from .notebooklm_auth import save_auth_payload

logger = logging.getLogger("notebooklm_browser_auth")

NOTEBOOKLM_URL = "https://notebooklm.google.com/"
AUTH_MODE_ENV = "NOTEBOOKLM_AUTH_MODE"
AUTH_CHROMIUM_EXECUTABLE_ENV = "NOTEBOOKLM_CHROMIUM_EXECUTABLE"
DEFAULT_AUTH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=1280,800",
]

CHROMIUM_PROFILE_NAMES = ["Default", "Profile 1", "Profile 2", "Profile 3", "Guest Profile"]


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _resolve_auth_mode() -> str:
    mode = os.getenv(AUTH_MODE_ENV, "auto").strip().lower()
    if mode in {"auto", "trusted", "playwright"}:
        return mode
    return "auto"


def _windows_browser_candidates() -> list[Path]:
    localappdata = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "")

    candidates: list[Path] = []
    for root in [program_files, program_files_x86]:
        if root:
            candidates.append(Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe")
            candidates.append(Path(root) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    if localappdata:
        candidates.append(Path(localappdata) / "Google" / "Chrome" / "Application" / "chrome.exe")
        candidates.append(Path(localappdata) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    return candidates


def _detect_system_browser_executable() -> Path | None:
    override = os.getenv(AUTH_CHROMIUM_EXECUTABLE_ENV, "").strip()
    if override:
        override_path = Path(override).expanduser()
        if override_path.exists():
            return override_path

    if os.name == "nt":
        for candidate in _windows_browser_candidates():
            if candidate.exists():
                return candidate

    for command in ["chrome", "msedge", "chromium", "chromium-browser"]:
        resolved = shutil.which(command)
        if resolved:
            return Path(resolved)

    return None


def _system_browser_user_data_dir(executable_path: Path) -> Path | None:
    if os.name != "nt":
        return None

    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        return None

    executable_name = executable_path.name.lower()
    if "msedge" in executable_name:
        return Path(localappdata) / "Microsoft" / "Edge" / "User Data"

    return Path(localappdata) / "Google" / "Chrome" / "User Data"


def _candidate_chromium_roots() -> list[Path]:
    roots: list[Path] = []
    localappdata = os.environ.get("LOCALAPPDATA", "")
    if not localappdata:
        return roots

    roots.append(Path(localappdata) / "Google" / "Chrome" / "User Data")
    roots.append(Path(localappdata) / "Microsoft" / "Edge" / "User Data")
    return roots


def _copy_sqlite_database(source: Path) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="nestbrain_cookies_"))
    copy_path = temp_dir / source.name
    shutil.copy2(source, copy_path)
    return copy_path


def _dpapi_decrypt(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    buffer = ctypes.create_string_buffer(data, len(data))
    in_blob = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()

    if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise RuntimeError("Failed to decrypt Chromium browser key with Windows DPAPI.")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _get_chromium_aes_key(local_state_path: Path) -> bytes:
    local_state = json.loads(local_state_path.read_text(encoding="utf-8"))
    encrypted_key_b64 = local_state.get("os_crypt", {}).get("encrypted_key", "")
    if not encrypted_key_b64:
        raise RuntimeError(f"Encrypted browser key not found in {local_state_path}.")

    encrypted_key = base64.b64decode(encrypted_key_b64)
    if encrypted_key.startswith(b"DPAPI"):
        encrypted_key = encrypted_key[5:]

    return _dpapi_decrypt(encrypted_key)


def _decrypt_chromium_cookie(encrypted_value: bytes, aes_key: bytes) -> str:
    if encrypted_value.startswith(b"v10") or encrypted_value.startswith(b"v11"):
        nonce = encrypted_value[3:15]
        ciphertext = encrypted_value[15:]
        return AESGCM(aes_key).decrypt(nonce, ciphertext, None).decode("utf-8", errors="replace")

    if encrypted_value:
        return encrypted_value.decode("utf-8", errors="replace")

    return ""


def _read_chromium_cookies_from_profile(profile_dir: Path, domain_patterns: list[str]) -> dict[str, str]:
    cookie_db = profile_dir / "Network" / "Cookies"
    if not cookie_db.exists():
        cookie_db = profile_dir / "Cookies"
    if not cookie_db.exists():
        return {}

    local_state = profile_dir.parent / "Local State"
    if not local_state.exists():
        return {}

    aes_key = _get_chromium_aes_key(local_state)
    copied_db = _copy_sqlite_database(cookie_db)
    cookies: dict[str, str] = {}

    try:
        connection = sqlite3.connect(copied_db)
        try:
            cursor = connection.execute(
                "SELECT host_key, name, encrypted_value, value FROM cookies"
            )
            for host_key, name, encrypted_value, plain_value in cursor.fetchall():
                host = str(host_key or "")
                if not any(pattern in host for pattern in domain_patterns):
                    continue

                cookie_name = str(name or "").strip()
                if not cookie_name:
                    continue

                value = ""
                if isinstance(plain_value, str) and plain_value:
                    value = plain_value
                elif encrypted_value:
                    value = _decrypt_chromium_cookie(bytes(encrypted_value), aes_key)

                value = value.strip()
                if value:
                    cookies[cookie_name] = value
        finally:
            connection.close()
    finally:
        try:
            copied_db.unlink(missing_ok=True)
            copied_db.parent.rmdir()
        except Exception:
            pass

    return cookies


def _read_google_profile_cookies() -> dict[str, str]:
    cookies: dict[str, str] = {}
    domain_patterns = ["google.com", "notebooklm.google.com", "accounts.google.com"]
    for root in _candidate_chromium_roots():
        for profile_name in CHROMIUM_PROFILE_NAMES:
            profile_dir = root / profile_name
            if not profile_dir.exists():
                continue
            profile_cookies = _read_chromium_cookies_from_profile(profile_dir, domain_patterns)
            for key, value in profile_cookies.items():
                cookies.setdefault(key, value)

    return cookies


async def _refresh_tokens_from_cookies(cookies: dict[str, str], timeout_ms: int) -> str:
    tokens = AuthTokens(cookies=cookies, csrf_token="", session_id="")
    try:
        async with NotebookLMClient(tokens) as client:
            refreshed = await asyncio.wait_for(client.refresh_auth(), timeout_ms / 1000)
    except asyncio.TimeoutError as exc:
        raise RuntimeError("Timed out refreshing NotebookLM session from browser cookies.") from exc
    except (NotebookLMClientAuthError, NotebookLMError, ValueError) as exc:
        raise RuntimeError(f"NotebookLM rejected cookies from the local browser profile: {exc}") from exc

    payload: dict[str, Any] = {
        "cookies": refreshed.cookies,
        "csrf_token": refreshed.csrf_token,
        "session_id": refreshed.session_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    auth_path = save_auth_payload(payload)
    return str(auth_path)


async def _extract_and_persist_auth(context: Any, timeout_ms: int) -> str:
    page = await context.new_page()
    await page.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        """
    )

    await page.goto(NOTEBOOKLM_URL, wait_until="domcontentloaded")
    await page.wait_for_function(
        """
        () => window.location.hostname === 'notebooklm.google.com'
            && !window.location.href.includes('accounts.google.com')
            && !window.location.href.includes('signin')
        """,
        timeout=timeout_ms,
    )
    # Give the page a moment to populate in-memory auth globals.
    await page.wait_for_timeout(8000)

    cookie_list = await context.cookies()
    cookies: dict[str, str] = {}
    for cookie in cookie_list:
        domain = str(cookie.get("domain", ""))
        if "google.com" in domain or "notebooklm" in domain:
            name = str(cookie.get("name", "")).strip()
            value = str(cookie.get("value", "")).strip()
            if name and value:
                cookies[name] = value

    wiz_data = await page.evaluate(
        """
        () => {
            const read = (path) => {
                try {
                    return path.split('.').reduce((obj, prop) => obj?.[prop], window);
                } catch {
                    return "";
                }
            };

            let at = read('_WIZ_global_data.SNlM0e') || read('WIZ_global_data.SNlM0e') || "";
            let sid = read('_WIZ_global_data.FdrF9e') || read('WIZ_global_data.FdrF9e') || "";

            if (!at || !sid) {
                const pools = [window._WIZ_global_data, window.WIZ_global_data];
                for (const pool of pools) {
                    if (!pool || typeof pool !== 'object') {
                        continue;
                    }
                    if (!at && pool.SNlM0e) {
                        at = pool.SNlM0e;
                    }
                    if (!sid && pool.FdrF9e) {
                        sid = pool.FdrF9e;
                    }
                }
            }

            return { at, sid };
        }
        """
    )

    csrf_token = str((wiz_data or {}).get("at", "")).strip()
    session_id = str((wiz_data or {}).get("sid", "")).strip()

    if not cookies:
        raise RuntimeError("No NotebookLM/Google cookies were captured from the browser session.")

    if not csrf_token:
        raise RuntimeError("Could not extract CSRF token from the NotebookLM page state.")

    payload: dict[str, Any] = {
        "cookies": cookies,
        "csrf_token": csrf_token,
        "session_id": session_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    auth_path = save_auth_payload(payload)
    return str(auth_path)


async def _authenticate_with_trusted_browser(playwright: Any, timeout_ms: int) -> str:
    if os.name != "nt":
        raise RuntimeError("Trusted browser auth currently supports Windows desktop installs only.")

    cookies = _read_google_profile_cookies()
    if not cookies:
        raise RuntimeError(
            "No Google/NotebookLM cookies were found in the local Chrome or Edge profiles. "
            "Sign into Google in Chrome or Edge, then retry NotebookLM authentication."
        )

    logger.info("Attempting trusted NotebookLM auth from local browser profile cookies (%s cookies).", len(cookies))
    return await _refresh_tokens_from_cookies(cookies, timeout_ms)


async def _authenticate_with_playwright_browser(playwright: Any, timeout_ms: int) -> str:
    browser = await playwright.chromium.launch(
        headless=False,
        args=DEFAULT_BROWSER_ARGS,
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=DEFAULT_AUTH_USER_AGENT,
    )

    try:
        return await _extract_and_persist_auth(context, timeout_ms)
    finally:
        await context.close()
        await browser.close()


def _browser_runtime_context() -> dict[str, str]:
    base = {
        "frozen": str(bool(getattr(sys, "frozen", False))),
        "executable": sys.executable,
        "cwd": str(Path.cwd()),
        "playwright_browsers_path": os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""),
    }
    if os.name == "nt":
        base["localappdata"] = os.environ.get("LOCALAPPDATA", "")
        base["temp"] = os.environ.get("TEMP", "")
    return base


async def authenticate_with_browser(timeout_ms: int = 300000) -> str:
    """Run an interactive browser login flow and persist NotebookLM auth tokens."""
    runtime = _browser_runtime_context()
    auth_mode = _resolve_auth_mode()
    if getattr(sys, "frozen", False):
        # For packaged builds, Playwright must resolve bundled browsers under package data.
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
        runtime = _browser_runtime_context()
    logger.info("NotebookLM auth runtime context: %s", runtime)
    logger.info("NotebookLM auth mode: %s", auth_mode)

    async with async_playwright() as playwright:
        trusted_error: Exception | None = None
        if auth_mode in {"auto", "trusted"}:
            try:
                return await _authenticate_with_trusted_browser(playwright, timeout_ms)
            except Exception as exc:
                trusted_error = exc
                logger.warning("Trusted browser auth attempt failed: %s", exc)
                if auth_mode == "trusted":
                    raise RuntimeError(f"Trusted browser authentication failed: {exc}") from exc

        try:
            return await _authenticate_with_playwright_browser(playwright, timeout_ms)
        except Exception as exc:
            logger.exception("Playwright browser auth attempt failed: %s", exc)
            if trusted_error is not None and auth_mode == "auto":
                raise RuntimeError(
                    "NotebookLM authentication failed in both trusted and fallback modes. "
                    f"Trusted mode error: {trusted_error}; Playwright mode error: {exc}"
                ) from exc
            raise RuntimeError(
                "Could not launch the NotebookLM browser runtime. "
                "Reinstall the app with bundled browser support or contact support."
            ) from exc


def run_browser_auth_cli() -> int:
    """CLI entrypoint for NotebookLM browser authentication."""
    print("NotebookLM authentication started.")
    print("A browser window will open. Complete login, then return to the app and click Refresh Status.")
    logger.info("Starting NotebookLM browser auth CLI")
    try:
        auth_path = asyncio.run(authenticate_with_browser())
        print(f"Authentication successful. Tokens saved at: {auth_path}")
        return 0
    except Exception as exc:
        logger.exception("NotebookLM browser authentication failed: %s", exc)
        print(f"Authentication failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run_browser_auth_cli())
