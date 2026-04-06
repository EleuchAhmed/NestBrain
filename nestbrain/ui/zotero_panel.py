from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class _VaultEventHandler(FileSystemEventHandler):
    def __init__(self, manager: "LocalSyncManager") -> None:
        super().__init__()
        self.manager = manager

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self.manager.register_file_event(Path(event.src_path).as_posix())


class LocalSyncManager(QObject):
    sync_status_changed = pyqtSignal(str, str)

    def __init__(self, vault_path: str = "", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.vault_path = vault_path
        self.pending_events: dict[str, float] = {}
        self.last_sync = datetime.now()

        self._observer: Any = None
        self._handler = _VaultEventHandler(self)

        self._ticker = QTimer(self)
        self._ticker.setInterval(1200)
        self._ticker.timeout.connect(self._refresh_state)
        self._ticker.start()

    def start(self) -> None:
        self.stop()
        if not self.vault_path:
            self._emit_state("ALL UP TO DATE", "NO VAULT PATH CONFIGURED")
            return

        vault = Path(self.vault_path)
        if not vault.exists() or not vault.is_dir():
            self._emit_state("ALL UP TO DATE", "VAULT NOT FOUND")
            return

        self._observer = Observer()
        self._observer.schedule(self._handler, str(vault), recursive=True)
        self._observer.start()
        self._emit_state("ALL UP TO DATE", "WATCHING LOCAL VAULT")

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    def set_vault_path(self, vault_path: str) -> None:
        self.vault_path = vault_path
        self.start()

    def register_file_event(self, path: str) -> None:
        self.pending_events[path] = datetime.now().timestamp()
        self._refresh_state()

    def mark_synced(self) -> None:
        self.pending_events.clear()
        self.last_sync = datetime.now()
        self._emit_state("ALL UP TO DATE", f"LAST SYNC {self.last_sync.strftime('%H:%M:%S')}")

    def _refresh_state(self) -> None:
        now_ts = datetime.now().timestamp()
        stale_keys = [path for path, ts in self.pending_events.items() if now_ts - ts > 8]
        for key in stale_keys:
            self.pending_events.pop(key, None)

        pending_count = len(self.pending_events)
        if pending_count > 0:
            self._emit_state(f"{pending_count} FILES PENDING", "LOCAL VAULT CHANGED")
        else:
            self._emit_state("ALL UP TO DATE", f"LAST SYNC {self.last_sync.strftime('%H:%M:%S')}")

    def _emit_state(self, title: str, subtitle: str) -> None:
        self.sync_status_changed.emit(title, subtitle)


class PipelinePanel(QWidget):
    collection_selected = pyqtSignal(str)
    create_collection_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PipelinePanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        header_row = QHBoxLayout()
        title = QLabel("Pipeline")
        title.setObjectName("PipelineHeader")

        self.badge = QLabel("INACTIVE")
        self.badge.setObjectName("PipelineStatusBadge")

        header_row.addWidget(title)
        header_row.addStretch(1)
        header_row.addWidget(self.badge)

        def section_header(text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("PipelineSectionHeader")
            return label

        create_label = section_header("ADD COLLECTION")

        create_row = QHBoxLayout()
        self.new_collection_input = QLineEdit()
        self.new_collection_input.setPlaceholderText("Collection name...")
        self.create_collection_button = QPushButton("Create")
        self.create_collection_button.clicked.connect(self._emit_create_collection)

        create_row.addWidget(self.new_collection_input)
        create_row.addWidget(self.create_collection_button)

        collections_label = section_header("COLLECTION")

        sources_label = section_header("SOURCES")

        self._selected_collection_key = ""
        self._suppress_dropdown_signal = False

        self.collection_dropdown = QComboBox()
        self.collection_dropdown.setObjectName("PipelineCollectionDropdown")
        self.collection_dropdown.currentIndexChanged.connect(self._emit_selected_dropdown_collection)
        self.collection_dropdown.addItem("Select collection...", "")

        self.sources_list = QListWidget()
        self.sources_list.setObjectName("PipelineSourcesList")
        self.sources_list.addItem("Select a collection to load sources")

        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        content_row = QHBoxLayout()
        content_row.setSpacing(14)

        left_layout.addWidget(create_label)
        left_layout.addLayout(create_row)
        left_layout.addWidget(collections_label)
        left_layout.addWidget(self.collection_dropdown)
        left_layout.addStretch(1)

        right_layout.addWidget(sources_label)
        right_layout.addWidget(self.sources_list, 1)

        content_row.addWidget(left_col, 1)
        content_row.addWidget(right_col, 2)

        root.addLayout(header_row)
        root.addLayout(content_row, 1)

    def set_connection_active(self, active: bool) -> None:
        if active:
            self.badge.setText("ACTIVE")
            self.badge.setStyleSheet("background-color: #3a3450; color: #d8c4ff; padding: 4px 8px; border-radius: 9px;")
        else:
            self.badge.setText("INACTIVE")
            self.badge.setStyleSheet("background-color: #35252a; color: #f1afb8; padding: 4px 8px; border-radius: 9px;")

    def update_collections(self, collections: list[dict[str, Any]]) -> None:
        self._suppress_dropdown_signal = True
        self.collection_dropdown.clear()
        self.collection_dropdown.addItem("Select collection...", "")

        for collection in collections:
            display_name = str(collection.get("name", "Untitled"))
            collection_key = str(collection.get("key", "")).strip()
            item_count = int(collection.get("item_count", 0))
            self.collection_dropdown.addItem(f"{display_name} ({item_count})", collection_key)

        if self._selected_collection_key:
            idx = self.collection_dropdown.findData(self._selected_collection_key)
            if idx >= 0:
                self.collection_dropdown.setCurrentIndex(idx)
            else:
                self.collection_dropdown.setCurrentIndex(0)
        else:
            self.collection_dropdown.setCurrentIndex(0)

        self._suppress_dropdown_signal = False

    def set_selected_collection_key(self, collection_key: str) -> None:
        self._selected_collection_key = collection_key.strip()
        idx = self.collection_dropdown.findData(self._selected_collection_key)
        self._suppress_dropdown_signal = True
        if idx >= 0:
            self.collection_dropdown.setCurrentIndex(idx)
        else:
            self.collection_dropdown.setCurrentIndex(0)
        self._suppress_dropdown_signal = False

    def update_collection_elements(self, items: list[dict[str, Any]]) -> None:
        self.sources_list.clear()
        if not items:
            self.sources_list.addItem("No sources found")
            return

        for item in items:
            title = str(item.get("title") or "Untitled")
            item_type = str(item.get("item_type") or "item")
            self.sources_list.addItem(f"{title} [{item_type}]")

    def _emit_create_collection(self) -> None:
        self.create_collection_requested.emit(self.new_collection_input.text().strip())

    def clear_create_collection_input(self) -> None:
        self.new_collection_input.clear()

    def _emit_selected_dropdown_collection(self, index: int) -> None:
        if self._suppress_dropdown_signal:
            return

        key = str(self.collection_dropdown.itemData(index) or "").strip()
        if key == self._selected_collection_key:
            return

        self._selected_collection_key = key
        self.collection_selected.emit(key)
