from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .brain_map_view import BrainMapView
from .graph_3d_view import Graph3DView


class FeatureCard(QFrame):
    def __init__(self, title: str, description: str, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FeatureCard")
        self.setMinimumHeight(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)

        icon_label = QLabel(icon)
        icon_label.setObjectName("FeatureCardIcon")
        title_label = QLabel(title)
        title_label.setObjectName("FeatureCardTitle")
        desc_label = QLabel(description)
        desc_label.setObjectName("FeatureCardDescription")
        desc_label.setWordWrap(True)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch(1)


class Workspace(QWidget):
    start_pipeline_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)

        self.stacked = QStackedWidget()
        self.view_keys = {
            "home": 0,
            "notes": 1,
            "archive": 2,
            "brain": 3,
            "graph": 4,
        }

        self._all_notes: list[dict[str, Any]] = []  # Initialize to avoid filter errors before first run

        self.home_view = self._build_home_view()
        self.notes_view = self._build_notes_view()
        self.archive_view = self._build_archive_view()
        self.brain_map_view = BrainMapView()
        self.graph_3d_view = Graph3DView()

        self.stacked.addWidget(self.home_view)
        self.stacked.addWidget(self.notes_view)
        self.stacked.addWidget(self.archive_view)
        self.stacked.addWidget(self.brain_map_view)
        self.stacked.addWidget(self.graph_3d_view)

        root.addWidget(self.stacked)
        self.set_view("home")

    def _build_home_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(18)

        headline = QLabel("Transform raw data into\nconnected intelligence.")
        headline.setObjectName("Headline")

        subtitle = QLabel(
            "Deploy your local neural pipeline to synthesize Obsidian notes, "
            "Zotero references, and research fragments into a cohesive map."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("SubHeadline")

        self.start_button = QPushButton("✦  Start Pipeline")
        self.start_button.setObjectName("StartPipelineButton")
        self.start_button.setFixedHeight(58)
        self.start_button.clicked.connect(self.start_pipeline_requested.emit)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        self.status_label = QLabel("Pipeline idle")
        self.status_label.setObjectName("PipelineStatus")

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        cards_row.addWidget(FeatureCard("AI Synthesis", "Auto-categorize and summarize information nodes.", "✦"))
        cards_row.addWidget(FeatureCard("Semantic Linking", "Discover hidden relationships between notes.", "✤"))
        cards_row.addWidget(FeatureCard("3D Graphing", "Explore your neural network in interactive 3D.", "◉"))

        layout.addWidget(headline)
        layout.addWidget(subtitle)
        layout.addWidget(self.start_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addLayout(cards_row)
        layout.addStretch(1)

        return widget

    def _build_notes_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header = QLabel("Vault Notes (Parsed)")
        header.setObjectName("PanelHeader")
        header.setToolTip("Markdown notes parsed from your configured Obsidian vault")
        header_layout.addWidget(header)
        header_layout.addStretch(1)

        self.vault_path_label = QLabel()
        self.vault_path_label.setObjectName("VaultPathLabel")
        self.vault_path_label.setStyleSheet("color: #999; font-size: 11px;")
        header_layout.addWidget(self.vault_path_label)

        self.notes_search = QLineEdit()
        self.notes_search.setPlaceholderText("Search by title or tag...")
        self.notes_search.textChanged.connect(self._filter_notes)

        self.notes_table = QTableWidget(0, 4)
        self.notes_table.setHorizontalHeaderLabels(["Title", "Tags", "Last Modified", "Link Count"])
        self.notes_table.horizontalHeader().setStretchLastSection(True)
        self.notes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.notes_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        lower_row = QHBoxLayout()

        vault_panel = QFrame()
        vault_panel.setObjectName("FeatureCard")
        vault_layout = QVBoxLayout(vault_panel)
        vault_layout.setContentsMargins(10, 10, 10, 10)

        vault_header = QLabel("Vault Structure")
        vault_header.setObjectName("PanelHeader")
        self.vault_tree = QTreeWidget()
        self.vault_tree.setHeaderLabels(["Path", "Type"])
        self.vault_tree.setAlternatingRowColors(True)

        vault_layout.addWidget(vault_header)
        vault_layout.addWidget(self.vault_tree)

        video_panel = QFrame()
        video_panel.setObjectName("FeatureCard")
        video_layout = QVBoxLayout(video_panel)
        video_layout.setContentsMargins(10, 10, 10, 10)

        video_header = QLabel("NotebookLM Videos")
        video_header.setObjectName("PanelHeader")
        self.video_list = QListWidget()
        self.video_list.itemDoubleClicked.connect(self._open_selected_video)

        video_layout.addWidget(video_header)
        video_layout.addWidget(self.video_list)

        lower_row.addWidget(vault_panel, 2)
        lower_row.addWidget(video_panel, 1)

        layout.addLayout(header_layout)
        layout.addWidget(self.notes_search)
        layout.addWidget(self.notes_table)
        layout.addLayout(lower_row)
        return widget

    def _build_archive_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        header = QLabel("Archive")
        header.setObjectName("PanelHeader")

        self.archive_list = QListWidget()
        self.archive_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)

        layout.addWidget(header)
        layout.addWidget(self.archive_list)
        return widget

    def set_view(self, key: str) -> None:
        index = self.view_keys.get(key, self.view_keys["home"])
        self.stacked.setCurrentIndex(index)

    def set_pipeline_running(self, running: bool) -> None:
        self.start_button.setDisabled(running)
        if running:
            self.status_label.setText("Pipeline running...")
            self.progress_bar.setValue(0)

    def set_pipeline_progress(self, value: int, status: str | None = None) -> None:
        self.progress_bar.setValue(max(0, min(100, value)))
        if status:
            self.status_label.setText(status)

    def update_notes(self, notes: list[dict[str, Any]]) -> None:
        self._all_notes = notes
        self._render_notes_table(notes)

    def update_archive(self, entries: list[dict[str, Any]]) -> None:
        self.archive_list.clear()
        for entry in entries:
            timestamp = entry.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            details = (
                f"{timestamp} | notes: {entry.get('note_count', 0)} | "
                f"collections: {entry.get('collection_count', 0)} | "
                f"graph: {entry.get('graph_nodes', 0)} nodes"
            )
            item = QListWidgetItem(details)
            self.archive_list.addItem(item)

    def update_graph(self, graph_payload: dict[str, Any]) -> None:
        self.graph_3d_view.set_graph_data(graph_payload)
        self.brain_map_view.set_graph_data(graph_payload)

    def update_vault_overview(self, vault_path: str) -> None:
        path = Path(vault_path).expanduser() if vault_path else Path()
        if path.exists() and path.is_dir():
            self.vault_path_label.setText(f"Vault: {path.name}")
            self._render_vault_tree(path)
            self._render_video_list(path)
            return

        self.vault_path_label.setText("Vault: not configured")
        self.vault_tree.clear()
        self.video_list.clear()
        QTreeWidgetItem(self.vault_tree, ["Vault path unavailable", "-"])
        self.video_list.addItem("No videos found")

    def _render_notes_table(self, notes: list[dict[str, Any]]) -> None:
        self.notes_table.setRowCount(len(notes))
        for row, note in enumerate(notes):
            title = str(note.get("title", "Untitled"))
            tags = ", ".join(note.get("tags", []))
            modified = str(note.get("last_modified", ""))
            link_count = str(len(note.get("wikilinks", [])))

            self.notes_table.setItem(row, 0, QTableWidgetItem(title))
            self.notes_table.setItem(row, 1, QTableWidgetItem(tags))
            self.notes_table.setItem(row, 2, QTableWidgetItem(modified))
            self.notes_table.setItem(row, 3, QTableWidgetItem(link_count))

        self.notes_table.resizeColumnsToContents()

    def _filter_notes(self, query: str) -> None:
        all_notes = getattr(self, "_all_notes", [])
        query = query.strip().lower()
        if not query:
            self._render_notes_table(all_notes)
            return

        filtered = []
        for note in all_notes:
            title = str(note.get("title", "")).lower()
            tags = " ".join(note.get("tags", [])).lower()
            if query in title or query in tags:
                filtered.append(note)

        self._render_notes_table(filtered)

    def _render_vault_tree(self, vault_path: Path) -> None:
        self.vault_tree.clear()
        root_item = QTreeWidgetItem([vault_path.name, "folder"])
        self.vault_tree.addTopLevelItem(root_item)

        excluded = {".git", ".obsidian", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
        max_nodes = 1200
        node_count = 0

        def add_children(parent: QTreeWidgetItem, folder: Path, depth: int) -> None:
            nonlocal node_count
            if depth > 4 or node_count >= max_nodes:
                return

            try:
                children = sorted(folder.iterdir(), key=lambda child: (child.is_file(), child.name.lower()))
            except Exception:
                return

            for child in children:
                if node_count >= max_nodes:
                    break
                if child.name in excluded:
                    continue
                if child.is_dir() or child.suffix.lower() in {".md", ".mp4", ".webm", ".mov"}:
                    child_type = "folder" if child.is_dir() else "file"
                    child_item = QTreeWidgetItem([child.name, child_type])
                    parent.addChild(child_item)
                    node_count += 1
                    if child.is_dir():
                        add_children(child_item, child, depth + 1)

        add_children(root_item, vault_path, 0)
        self.vault_tree.expandToDepth(1)

    def _render_video_list(self, vault_path: Path) -> None:
        self.video_list.clear()
        asset_dir = vault_path / "assets"
        video_paths: list[Path] = []

        if asset_dir.exists() and asset_dir.is_dir():
            for suffix in ("*.mp4", "*.webm", "*.mov"):
                video_paths.extend(asset_dir.rglob(suffix))

        if not video_paths:
            self.video_list.addItem("No videos found")
            return

        for video_path in sorted(video_paths, key=lambda item: item.stat().st_mtime, reverse=True):
            modified = datetime.fromtimestamp(video_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            display_path = video_path.relative_to(vault_path).as_posix()
            item = QListWidgetItem(f"{display_path} ({modified})")
            item.setData(Qt.ItemDataRole.UserRole, str(video_path))
            self.video_list.addItem(item)

    def _open_selected_video(self, item: QListWidgetItem) -> None:
        file_path = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not file_path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
