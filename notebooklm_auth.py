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

# Configure structured logging for the auth layer
log_dir = Path("pipeline_logs")
log_dir.mkdir(exist_ok=True)

logger = logging.getLogger("notebooklm_auth")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_dir / "notebooklm_auth.log")
# Ensure console logs are also shown
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
logger.addHandler(console_handler)


def _get_auth_file_path() -> Path:
    """Return the path to the cached auth.json file."""
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

async def _trigger_browser_fallback() -> bool:
    """
    Execute the Puppeteer script to refresh Google cookies via a real browser session.
    Circuit breaker: If this fails 3 times, we permanently fail to avoid locking the account.
    """
    logger.info("Triggering browser-auth.ts fallback to refresh Google session cookies.")
    script_path = Path(__file__).parent / "antigravity-notebooklm-mcp"
    
    # We allow up to 3 fallback attempts locally
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fallback attempt {attempt}/{max_retries}...")
            process = await asyncio.create_subprocess_exec(
                "npx", "ts-node", "src/browser-auth.ts",
                cwd=str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
                
                if process.returncode == 0:
                    logger.info("Browser fallback completed successfully. New cookies cached.")
                    return True
                else:
                    logger.error(f"Browser fallback failed (exit code {process.returncode}):\n{stderr.decode()}")
            except asyncio.TimeoutError:
                process.kill()
                logger.error("Browser fallback timed out after 120 seconds. Is user input required?")
                
        except Exception as e:
            logger.error(f"Unexpected error executing fallback: {e}")
            
        if attempt < max_retries:
            logger.info("Waiting 10 seconds before retrying fallback...")
            await asyncio.sleep(10)
            
    logger.critical("Browser fallback failed 3 consecutive times. Circuit breaker tripped.")
    return False

async def get_auth_tokens() -> AuthTokens:
    """
    Primary interface for pipeline integration.
    Returns authenticated AuthTokens ready for use with NotebookLMClient.
    """
    tokens = _load_auth_tokens()
    
    # Pre-flight ping: check if CSRF token is still valid
    if tokens:
        logger.info("Cached auth tokens found. Validating session health...")
        try:
            async with NotebookLMClient(tokens) as client:
                await client.refresh_auth()
            logger.info("Session health check passed.")
            return tokens
        except (AuthError, NotebookLMError, ValueError) as e:
            logger.warning(f"Session health check failed: {e}. Cookies may have expired.")
    else:
        logger.warning("No cached tokens available for initialization.")
        
    # If we reach here, we either had no tokens or the session was stale
    logger.info("Initiating hybrid fallback strategy...")
    success = await _trigger_browser_fallback()
    
    if not success:
        logger.critical("Authentication failure could not be resolved by fallback.")
        raise RuntimeError("NotebookLM Authentication permanently failed. Check logs.")
        
    # Reload the freshly generated tokens
    new_tokens = _load_auth_tokens()
    if not new_tokens:
        logger.critical("Fallback reported success but auth.json is still missing/invalid.")
        raise RuntimeError("Failed to load new auth tokens after fallback.")
        
    # Final pre-flight verification
    try:
        async with NotebookLMClient(new_tokens) as client:
            await client.refresh_auth()
        logger.info("Recovered session successfully.")
        return new_tokens
    except Exception as e:
        logger.critical(f"Final session validation failed after fallback: {e}")
        raise

if __name__ == "__main__":
    # Small test sequence for the module
    async def test():
        tokens = await get_auth_tokens()
        print("Test complete. Tokens successfully retrieved.")
        
    asyncio.run(test())
