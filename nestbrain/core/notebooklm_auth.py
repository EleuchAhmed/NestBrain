import sys
import os
import json
import logging
import asyncio
from pathlib import Path
from typing import Optional
from notebooklm.auth import AuthTokens
from notebooklm.client import NotebookLMClient
from notebooklm.exceptions import AuthError, NotebookLMError
from .paths import get_logs_dir

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


def _get_auth_file_path() -> Path:
    """Return the path to the cached auth.json file."""
    override = os.getenv("NOTEBOOKLM_AUTH_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(os.path.expanduser("~/.notebooklm-mcp/auth.json"))

def _load_auth_tokens() -> Optional[AuthTokens]:
    """Load cached auth tokens from the local filesystem."""
    auth_file = _get_auth_file_path()
    if not auth_file.exists():
        logger.warning(f"Auth file not found at {auth_file}")
        return None
        
    try:
        data = json.loads(auth_file.read_text())
        return AuthTokens(
            cookies=data.get('cookies', {}),
            csrf_token=data.get('csrf_token', ''),
            session_id=data.get('session_id', '')
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
                await client.refresh_auth()
            logger.info("Session health check passed.")
            return tokens
        except (AuthError, NotebookLMError, ValueError) as e:
            logger.warning(f"Session health check failed: {e}. Cookies may have expired.")
            raise RuntimeError("NotebookLM Cookies expired. Please re-authenticate.") from e
    else:
        logger.warning("No cached tokens available for initialization.")
        raise RuntimeError("No NotebookLM authentication tokens found. Please authenticate.")
