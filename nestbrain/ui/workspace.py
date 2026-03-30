from __future__ import annotations

from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
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

        header = QLabel("Obsidian Notes")
        header.setObjectName("PanelHeader")

        self.notes_search = QLineEdit()
        self.notes_search.setPlaceholderText("Search by title or tag...")
        self.notes_search.textChanged.connect(self._filter_notes)

        self.notes_table = QTableWidget(0, 4)
        self.notes_table.setHorizontalHeaderLabels(["Title", "Tags", "Last Modified", "Link Count"])
        self.notes_table.horizontalHeader().setStretchLastSection(True)
        self.notes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.notes_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout.addWidget(header)
        layout.addWidget(self.notes_search)
        layout.addWidget(self.notes_table)
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
