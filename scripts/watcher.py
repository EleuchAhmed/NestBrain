"""
Zotero Storage → Staging Directory File Watcher
================================================
Monitors the Zotero `storage/` directory for new PDF attachments.
When a new PDF is detected, copies it into `staging/` with a
timestamp prefix so the pipeline agent can process it.

Usage:
    python scripts/watcher.py

Required env vars (from .env):
    ZOTERO_STORAGE_PATH  — path to Zotero's storage/ dir
                           (default: ~/Zotero/storage)
    STAGING_DIR          — path to the staging directory
                           (default: ./staging)
"""

import os
import sys
import shutil
import time
import signal
import logging
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

# ── Configuration ────────────────────────────────────────────────

load_dotenv()

ZOTERO_STORAGE_PATH: str = os.getenv(
    "ZOTERO_STORAGE_PATH",
    str(Path.home() / "Zotero" / "storage"),
)
STAGING_DIR: str = os.getenv(
    "STAGING_DIR",
    str(Path(__file__).resolve().parent.parent / "staging"),
)

# ── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("watcher")


# ── Event Handler ────────────────────────────────────────────────

class PDFHandler(FileSystemEventHandler):
    """Copies newly created PDFs from Zotero storage into staging."""

    def __init__(self, staging_dir: str) -> None:
        super().__init__()
        self.staging = Path(staging_dir)
        self.staging.mkdir(parents=True, exist_ok=True)

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return

        src = Path(event.src_path)

        # Only react to PDF files
        if src.suffix.lower() != ".pdf":
            return

        # Wait briefly for the file to finish writing
        self._wait_for_stable(src)

        # Build destination: <timestamp>_<original_name>.pdf
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = self.staging / f"{ts}_{src.name}"

        try:
            shutil.copy2(str(src), str(dest))
            log.info("Staged: %s → %s", src.name, dest.name)
        except Exception as exc:
            log.error("Failed to stage %s: %s", src.name, exc)

    @staticmethod
    def _wait_for_stable(path: Path, timeout: float = 10.0, interval: float = 0.5) -> None:
        """Block until the file size stops changing or timeout is reached."""
        deadline = time.monotonic() + timeout
        prev_size = -1
        while time.monotonic() < deadline:
            try:
                size = path.stat().st_size
            except OSError:
                return
            if size == prev_size and size > 0:
                return
            prev_size = size
            time.sleep(interval)


# ── Main ─────────────────────────────────────────────────────────

def main() -> None:
    storage = Path(ZOTERO_STORAGE_PATH)
    if not storage.is_dir():
        log.error("Zotero storage path does not exist: %s", storage)
        log.error("Set ZOTERO_STORAGE_PATH in .env or ensure Zotero is installed.")
        sys.exit(1)

    log.info("╔══════════════════════════════════════════╗")
    log.info("║     Zotero → Staging File Watcher        ║")
    log.info("╚══════════════════════════════════════════╝")
    log.info("Watching : %s", storage)
    log.info("Staging  : %s", STAGING_DIR)

    handler = PDFHandler(STAGING_DIR)
    observer = Observer()
    observer.schedule(handler, str(storage), recursive=True)
    observer.start()

    # Graceful shutdown on Ctrl+C / SIGTERM
    def _shutdown(signum, frame):
        log.info("Shutting down watcher…")
        observer.stop()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while observer.is_alive():
            observer.join(timeout=1)
    finally:
        observer.stop()
        observer.join()
        log.info("Watcher stopped.")


if __name__ == "__main__":
    main()