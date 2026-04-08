from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import sys
from typing import Any

from playwright.async_api import async_playwright

from .notebooklm_auth import save_auth_payload

logger = logging.getLogger("notebooklm_browser_auth")

NOTEBOOKLM_URL = "https://notebooklm.google.com/"


async def authenticate_with_browser(timeout_ms: int = 300000) -> str:
    """Run an interactive browser login flow and persist NotebookLM auth tokens."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1280,800",
            ],
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        try:
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
        finally:
            await context.close()
            await browser.close()


def run_browser_auth_cli() -> int:
    """CLI entrypoint for NotebookLM browser authentication."""
    print("NotebookLM authentication started.")
    print("A browser window will open. Complete login, then return to the app and click Refresh Status.")
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
