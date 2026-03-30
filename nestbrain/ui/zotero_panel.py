from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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


@dataclass
class CollectionDisplay:
    name: str
    item_count: int
    modified: str
    status: str


class CollectionItemWidget(QFrame):
    def __init__(self, collection: CollectionDisplay, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.collection = collection

        self.setObjectName("CollectionCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        name_label = QLabel(f"📁  {collection.name}")
        name_label.setObjectName("CollectionName")
        self.dot = QLabel("●")

        top.addWidget(name_label, 1)
        top.addWidget(self.dot)

        info = QLabel(f"{collection.item_count} items synced")
        info.setObjectName("CollectionInfo")
        meta = QLabel(f"Modified {collection.modified}")
        meta.setObjectName("CollectionMeta")

        layout.addLayout(top)
        layout.addWidget(info)
        layout.addWidget(meta)

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(550)
        self._blink_timer.timeout.connect(self._blink)
        self._visible = True

        self.set_status(collection.status)

    def set_status(self, status: str) -> None:
        if status.lower() == "syncing":
            self.dot.setStyleSheet("color: #ff9f6b;")
            if not self._blink_timer.isActive():
                self._blink_timer.start()
        else:
            self.dot.setStyleSheet("color: #c8afff;")
            self.dot.setVisible(True)
            self._blink_timer.stop()

    def _blink(self) -> None:
        self._visible = not self._visible
        self.dot.setVisible(self._visible)


class ZoteroPanel(QWidget):
    library_submitted = pyqtSignal(str)
    collection_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(380)
        self.setObjectName("ZoteroPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        header_row = QHBoxLayout()
        title = QLabel("Zotero Integration")
        title.setObjectName("ZoteroHeader")

        self.badge = QLabel("INACTIVE")
        self.badge.setObjectName("StatusBadge")

        header_row.addWidget(title)
        header_row.addStretch(1)
        header_row.addWidget(self.badge)

        source_label = QLabel("SOURCE URL / LIBRARY ID")
        source_label.setObjectName("PanelSubLabel")

        source_row = QHBoxLayout()
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("Paste Zotero URL/ID...")
        self.add_button = QPushButton("+")
        self.add_button.setFixedWidth(34)
        self.add_button.clicked.connect(self._emit_library)

        source_row.addWidget(self.source_input)
        source_row.addWidget(self.add_button)

        collections_label_row = QHBoxLayout()
        collections_label = QLabel("ACTIVE COLLECTIONS")
        collections_label.setObjectName("PanelSubLabel")
        self.folder_count = QLabel("0 Folders")

        collections_label_row.addWidget(collections_label)
        collections_label_row.addStretch(1)
        collections_label_row.addWidget(self.folder_count)

        self.collection_list = QListWidget()
        self.collection_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.collection_list.itemSelectionChanged.connect(self._emit_selected_collection)

        self.sync_chip = QFrame()
        self.sync_chip.setObjectName("SyncChip")
        chip_layout = QHBoxLayout(self.sync_chip)
        chip_layout.setContentsMargins(10, 8, 10, 8)

        icon = QLabel("☁")
        self.sync_title = QLabel("CLOUD SYNCHRONIZED")
        self.sync_title.setObjectName("SyncChipTitle")
        self.sync_subtitle = QLabel("EVERYTHING UP TO DATE")
        self.sync_subtitle.setObjectName("SyncChipSubtitle")

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        text_col.addWidget(self.sync_title)
        text_col.addWidget(self.sync_subtitle)

        chip_layout.addWidget(icon)
        chip_layout.addLayout(text_col)

        root.addLayout(header_row)
        root.addWidget(source_label)
        root.addLayout(source_row)
        root.addLayout(collections_label_row)
        root.addWidget(self.collection_list, 1)
        root.addWidget(self.sync_chip)
        self._selected_collection_key = ""

    def set_connection_active(self, active: bool) -> None:
        if active:
            self.badge.setText("ACTIVE")
            self.badge.setStyleSheet("background-color: #3a3450; color: #d8c4ff; padding: 4px 8px; border-radius: 9px;")
        else:
            self.badge.setText("INACTIVE")
            self.badge.setStyleSheet("background-color: #35252a; color: #f1afb8; padding: 4px 8px; border-radius: 9px;")

    def update_collections(self, collections: list[dict[str, Any]]) -> None:
        self.collection_list.clear()
        self.folder_count.setText(f"{len(collections)} Folders")

        selected_item: QListWidgetItem | None = None

        for collection in collections:
            display = CollectionDisplay(
                name=str(collection.get("name", "Untitled")),
                item_count=int(collection.get("item_count", 0)),
                modified=str(collection.get("last_modified", "Unknown")),
                status=str(collection.get("status", "Idle")),
            )
            collection_key = str(collection.get("key", "")).strip()
            widget = CollectionItemWidget(display)
            item = QListWidgetItem(self.collection_list)
            item.setData(Qt.ItemDataRole.UserRole, collection_key)
            item.setSizeHint(widget.sizeHint())
            self.collection_list.addItem(item)
            self.collection_list.setItemWidget(item, widget)

            if collection_key and collection_key == self._selected_collection_key:
                selected_item = item

        if selected_item is not None:
            selected_item.setSelected(True)

    def update_sync_chip(self, title: str, subtitle: str) -> None:
        self.sync_title.setText(title)
        self.sync_subtitle.setText(subtitle)

    def set_selected_collection_key(self, collection_key: str) -> None:
        self._selected_collection_key = collection_key.strip()

    def _emit_library(self) -> None:
        self.library_submitted.emit(self.source_input.text().strip())

    def _emit_selected_collection(self) -> None:
        items = self.collection_list.selectedItems()
        if not items:
            self._selected_collection_key = ""
            self.collection_selected.emit("")
            return

        selected = items[0]
        key = str(selected.data(Qt.ItemDataRole.UserRole) or "").strip()
        self._selected_collection_key = key
        self.collection_selected.emit(key)
