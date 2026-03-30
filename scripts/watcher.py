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
    STAGING_DIR          — destination directory for staged files
                           (default: ./staging)
"""

import sys
import os
import shutil
import time
import signal
import logging
import sqlite3
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
# Fix Windows home path expansion if necessary
if ZOTERO_STORAGE_PATH.startswith("~/"):
    ZOTERO_STORAGE_PATH = str(Path.home() / ZOTERO_STORAGE_PATH[2:])

STAGING_DIR: str = os.getenv(
    "STAGING_DIR",
    str(Path(__file__).resolve().parent.parent / "staging"),
)

ZOTERO_DB_PATH: str = os.getenv(
    "ZOTERO_DB_PATH",
    str(Path(ZOTERO_STORAGE_PATH).parent / "zotero.sqlite"),
)

SUPPORTED_EXTENSIONS = {".pdf", ".html", ".url", ".link", ".txt"}

# ── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("watcher")


# ── Zotero Metadata ─────────────────────────────────────────────

def get_collection_name(item_key: str) -> str:
    """Queries Zotero SQLite to find the collection name for a given item key."""
    if not os.path.exists(ZOTERO_DB_PATH):
        log.warning("Zotero database not found at %s. Using 'Uncategorized'.", ZOTERO_DB_PATH)
        return "Uncategorized"

    try:
        # Use URI with mode=ro to avoid locking issues while Zotero is open
        conn = sqlite3.connect(f"file:{ZOTERO_DB_PATH}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        # 1. Get Item ID from Key
        cursor.execute("SELECT itemID FROM items WHERE key = ?", (item_key,))
        row = cursor.fetchone()
        if not row:
            return "Uncategorized"
        item_id = row[0]

        # 2. Check if this is an attachment and get its parent ID
        cursor.execute("SELECT parentItemID FROM itemAttachments WHERE itemID = ?", (item_id,))
        parent_row = cursor.fetchone()
        if parent_row and parent_row[0]:
            item_id = parent_row[0]

        # 3. Get Collection ID and Name
        cursor.execute("SELECT collectionID FROM collectionItems WHERE itemID = ?", (item_id,))
        coll_row = cursor.fetchone()
        if not coll_row:
            return "Uncategorized"
        coll_id = coll_row[0]

        cursor.execute("SELECT collectionName FROM collections WHERE collectionID = ?", (coll_id,))
        name_row = cursor.fetchone()
        conn.close()
        
        return name_row[0] if name_row else "Uncategorized"
    except Exception as exc:
        log.error("Failed to query Zotero DB: %s", exc)
        return "Uncategorized"


# ── Event Handler ────────────────────────────────────────────────

class PDFHandler(FileSystemEventHandler):
    """Copies newly created research files from Zotero storage into hierarchical staging."""

    def __init__(self, staging_dir: str) -> None:
        super().__init__()
        self.staging = Path(staging_dir)
        self.staging.mkdir(parents=True, exist_ok=True)

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return

        src = Path(event.src_path)

        # Only react to supported file types
        if src.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return

        # Zotero storage structure: storage/ITEM_KEY/filename.ext
        # We need the ITEM_KEY (the parent directory name)
        item_key = src.parent.name
        if len(item_key) != 8: # Zotero keys are typically 8 chars
            # Might be a top-level file or unexpected structure
            log.debug("Skipping file outside item directory: %s", src)
            return

        # Wait briefly for the file to finish writing
        self._wait_for_stable(src)

        # Map to Collection
        collection_name = get_collection_name(item_key)
        
        # Build destination: staging/CollectionName/<timestamp>_<original_name>.pdf
        collection_dir = self.staging / collection_name
        collection_dir.mkdir(parents=True, exist_ok=True)
        
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = collection_dir / f"{ts}_{src.name}"

        try:
            shutil.copy2(str(src), str(dest))
            log.info("Staged: [%s] %s → %s", collection_name, src.name, dest.name)
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
    log.info("║   Zotero → Hierarchical File Watcher     ║")
    log.info("╚══════════════════════════════════════════╝")
    log.info("Watching : %s", storage)
    log.info("Staging  : %s", STAGING_DIR)
    log.info("Database : %s", ZOTERO_DB_PATH)

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