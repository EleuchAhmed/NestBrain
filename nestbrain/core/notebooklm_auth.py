import sys
import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from notebooklm.auth import AuthTokens
from notebooklm.client import NotebookLMClient
from notebooklm.exceptions import AuthError as NotebookLMClientAuthError, NotebookLMError
from .paths import get_logs_dir, get_user_data_dir

log_dir = get_logs_dir()

logger = logging.getLogger("notebooklm_auth")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_dir / "notebooklm_auth.log")
console_handler = logging.StreamHandler(sys.stderr)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


class NotebookLMAuthRequiredError(RuntimeError):
    """Raised when NotebookLM credentials are missing or no longer valid."""


def normalize_auth_payload(payload: dict) -> dict:
    """Normalize and validate NotebookLM auth payload shape before persistence."""
    if not isinstance(payload, dict):
        raise ValueError("Auth payload must be a JSON object.")

    raw_cookies = payload.get("cookies", {})
    if not isinstance(raw_cookies, dict):
        raise ValueError("Auth payload must include a 'cookies' object.")

    cookies = {
        str(key).strip(): str(value).strip()
        for key, value in raw_cookies.items()
        if str(key).strip() and str(value).strip()
    }
    if not cookies:
        raise ValueError("Auth payload must include at least one non-empty cookie.")

    csrf_token = str(payload.get("csrf_token", "")).strip()
    session_id = str(payload.get("session_id", "")).strip()
    normalized = {
        "cookies": cookies,
        "csrf_token": csrf_token,
        "session_id": session_id,
    }

    if "updated_at" in payload:
        normalized["updated_at"] = str(payload.get("updated_at", "")).strip()

    return normalized


def _get_auth_file_path() -> Path:
    """Return the preferred auth.json path with legacy fallback migration."""
    override = os.getenv("NOTEBOOKLM_AUTH_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    primary = _get_primary_auth_file_path()
    legacy = _get_legacy_auth_file_path()

    if primary.exists():
        return primary

    if legacy.exists():
        migrated = _try_migrate_legacy_auth(legacy, primary)
        if migrated:
            return primary
        return legacy

    return primary


def _get_primary_auth_file_path() -> Path:
    return get_user_data_dir() / "auth" / "notebooklm_auth.json"


def _get_legacy_auth_file_path() -> Path:
    return Path(os.path.expanduser("~/.notebooklm-mcp/auth.json"))


def _try_migrate_legacy_auth(legacy_path: Path, primary_path: Path) -> bool:
    try:
        primary_path.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(legacy_path.read_text(encoding="utf-8"))
        primary_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Migrated NotebookLM auth cache from %s to %s", legacy_path, primary_path)
        return True
    except Exception as exc:
        logger.warning("Auth migration skipped (%s)", exc)
        return False


def save_auth_payload(payload: dict) -> Path:
    """Persist NotebookLM auth payload to the preferred writable location."""
    normalized_payload = normalize_auth_payload(payload)
    auth_file = _get_auth_file_path()
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    auth_file.write_text(json.dumps(normalized_payload, indent=2), encoding="utf-8")
    return auth_file

def _load_auth_tokens() -> Optional[AuthTokens]:
    """Load cached auth tokens from the local filesystem."""
    auth_file = _get_auth_file_path()
    if not auth_file.exists():
        logger.warning(f"Auth file not found at {auth_file}")
        return None
        
    try:
        data = json.loads(auth_file.read_text(encoding="utf-8"))
        cookies = data.get('cookies', {})
        if not isinstance(cookies, dict):
            cookies = {}
        cookies = {str(k): str(v) for k, v in cookies.items() if str(k).strip() and str(v).strip()}
        csrf_token = str(data.get('csrf_token', '')).strip()
        session_id = str(data.get('session_id', '')).strip()
        if not cookies:
            logger.warning("Auth file is missing required NotebookLM cookies.")
            return None
        return AuthTokens(
            cookies=cookies,
            csrf_token=csrf_token,
            session_id=session_id,
        )
    except Exception as e:
        logger.error(f"Failed to parse auth.json: {e}")
        return None


def has_cached_auth_tokens() -> bool:
    """Return True if locally cached auth tokens are present and parseable."""
    return _load_auth_tokens() is not None


async def get_auth_tokens() -> AuthTokens:
    """
    Primary interface for pipeline integration.
    Returns authenticated AuthTokens ready for use with NotebookLMClient.
    """
    tokens = _load_auth_tokens()

    if tokens:
        logger.info("Cached auth tokens found. Validating session health...")
        try:
            async with NotebookLMClient(tokens) as client:
                # Add a timeout to prevent hanging on startup or during pipeline steps.
                refreshed = await asyncio.wait_for(client.refresh_auth(), timeout=30.0)

                if refreshed:
                    # IMPORTANT: Persist the refreshed tokens to prevent them from expiring
                    # while the application is closed.
                    payload = {
                        "cookies": refreshed.cookies,
                        "csrf_token": refreshed.csrf_token,
                        "session_id": refreshed.session_id,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    save_auth_payload(payload)
                    logger.info("Session health check passed and tokens updated.")
                    return refreshed

            logger.info("Session health check passed (no refresh needed).")
            return tokens
        except asyncio.TimeoutError as e:
            logger.error("Session health check timed out after 30 seconds.")
            raise NotebookLMAuthRequiredError("NotebookLM health check timed out. Please check your connection.") from e
        except (NotebookLMClientAuthError, NotebookLMError, ValueError, Exception) as e:
            logger.warning(f"Session health check failed: {e}. Cookies may have expired.")
            raise NotebookLMAuthRequiredError("NotebookLM authentication expired. Please re-authenticate.") from e
    else:
        logger.warning("No cached tokens available for initialization.")
        raise NotebookLMAuthRequiredError("No NotebookLM authentication tokens found. Please authenticate.")
