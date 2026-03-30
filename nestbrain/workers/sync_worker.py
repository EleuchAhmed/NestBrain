from __future__ import annotations

from dataclasses import asdict

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ..core.zotero_sync import ZoteroSyncClient


class SyncWorker(QObject):
    collection_updated = pyqtSignal(dict)
    sync_done = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, host: str, library_id: str = "") -> None:
        super().__init__()
        self.host = host
        self.library_id = library_id

    @pyqtSlot()
    def run(self) -> None:
        try:
            client = ZoteroSyncClient(host=self.host, library_id=self.library_id)
            collections = client.sync_all()
            for collection in collections:
                self.collection_updated.emit(asdict(collection))
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.sync_done.emit()
