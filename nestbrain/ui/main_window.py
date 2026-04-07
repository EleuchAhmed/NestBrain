from __future__ import annotations

from dataclasses import replace
from dataclasses import asdict
from datetime import datetime
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QEvent, QThread, Qt, QPoint, QRect
from PyQt6.QtGui import QMouseEvent, QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.app_service import NestbrainAppService
from ..core.paths import get_distribution_root, get_resource_root
from ..core.pipeline_runner import PipelineConfig, save_config
from ..ui.sidebar import TopNavBar
from ..ui.workspace import Workspace
from ..ui.zotero_panel import LocalSyncManager
from ..workers.graph_worker import GraphWorker
from ..workers.pipeline_worker import PipelineWorker
from ..workers.sync_worker import SyncWorker


class SettingsDialog(QDialog):
    def __init__(self, config: PipelineConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nestbrain Settings")
        self.setModal(True)
        self.resize(620, 360)

        self._config = config

        root = QVBoxLayout(self)
        form = QFormLayout()

        vault_row = QHBoxLayout()
        self.vault_input = QLineEdit(config.vault_path)
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_vault)
        vault_row.addWidget(self.vault_input, 1)
        vault_row.addWidget(browse_btn)

        vault_wrap = QWidget()
        vault_wrap.setLayout(vault_row)

        self.nvidia_api_key_input = QLineEdit(config.nvidia_api_key)
        self.nvidia_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.zotero_id_input = QLineEdit(config.zotero_library_id)
        self.zotero_api_key_input = QLineEdit(config.zotero_api_key)
        self.zotero_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ollama_host_input = QLineEdit(config.ollama_host)
        self.zotero_host_input = QLineEdit(config.zotero_host)

        notebooklm_row = QHBoxLayout()
        self.notebooklm_auth_btn = QPushButton("Authenticate")
        self.notebooklm_refresh_btn = QPushButton("Refresh Status")
        self.notebooklm_status_label = QLabel("")
        notebooklm_row.addWidget(self.notebooklm_auth_btn)
        notebooklm_row.addWidget(self.notebooklm_refresh_btn)
        notebooklm_row.addWidget(self.notebooklm_status_label, 1)

        notebooklm_wrap = QWidget()
        notebooklm_wrap.setLayout(notebooklm_row)

        self.notebooklm_auth_btn.clicked.connect(self._authenticate_notebooklm)
        self.notebooklm_refresh_btn.clicked.connect(self._refresh_notebooklm_status)

        form.addRow("Vault Path", vault_wrap)
        form.addRow("NVIDIA API Key", self.nvidia_api_key_input)
        form.addRow("Zotero Library ID", self.zotero_id_input)
        form.addRow("Zotero API Key", self.zotero_api_key_input)
        form.addRow("LLM Host/Base URL", self.ollama_host_input)
        form.addRow("Zotero Host", self.zotero_host_input)
        form.addRow("NotebookLM Account", notebooklm_wrap)

        button_row = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        save_button = QPushButton("Save")

        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)

        button_row.addStretch(1)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)

        root.addLayout(form)
        root.addLayout(button_row)
        self._refresh_notebooklm_status()

    def _browse_vault(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Obsidian Vault", self.vault_input.text() or str(Path.home()))
        if folder:
            self.vault_input.setText(folder)

    def _authenticate_notebooklm(self) -> None:
        launcher = get_distribution_root() / "launcher" / "windows" / "start-notebooklm-authentication.bat"

        override = os.getenv("NOTEBOOKLM_AUTH_LAUNCHER", "").strip()
        if override:
            launcher = Path(override).expanduser().resolve()

        if not launcher.exists():
            QMessageBox.warning(self, "Authentication Launcher Missing", f"Could not find launcher at:\n{launcher}")
            return

        try:
            if os.name == "nt":
                os.startfile(str(launcher))
            else:
                subprocess.Popen([str(launcher)])
            self.notebooklm_status_label.setText("Authentication launched. Complete login, then click Refresh Status.")
        except Exception as exc:
            QMessageBox.critical(self, "NotebookLM Authentication Failed", f"Could not launch authentication flow:\n{exc}")

    def _refresh_notebooklm_status(self) -> None:
        from ..core.notebooklm_auth import _get_auth_file_path, has_cached_auth_tokens

        auth_file = _get_auth_file_path()
        if not auth_file.exists() or not has_cached_auth_tokens():
            self.notebooklm_status_label.setText("Not authenticated")
            return

        try:
            updated_at = datetime.fromtimestamp(auth_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            self.notebooklm_status_label.setText(f"Authenticated (updated {updated_at})")
        except Exception:
            self.notebooklm_status_label.setText("Authentication expired or invalid")

    def get_config(self) -> PipelineConfig:
        return replace(
            self._config,
            vault_path=self.vault_input.text().strip(),
            nvidia_api_key=self.nvidia_api_key_input.text().strip(),
            zotero_library_id=self.zotero_id_input.text().strip(),
            zotero_api_key=self.zotero_api_key_input.text().strip(),
            ollama_host=self.ollama_host_input.text().strip() or "https://integrate.api.nvidia.com/v1",
            zotero_host=self.zotero_host_input.text().strip() or "http://localhost:23119",
        )


class MainWindow(QMainWindow):
    def __init__(self, app_root: Path, config_path: Path, config: PipelineConfig) -> None:
        super().__init__()
        icon_path = app_root / "assets" / "app.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Remove OS window frame and title bar for custom frameless design
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        # Enable hover-based mouseMoveEvent so resize cursors appear without holding a button
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        
        self.app_root = app_root
        self.config_path = config_path
        self.config = config
        self.app_service = NestbrainAppService(app_root)

        self.setWindowTitle("Nestbrain | Pipeline")
        self.resize(1440, 900)

        # Resizing/dragging state for pure Qt implementation
        self._resize_border = 8
        self._dragging = False
        self._drag_pos = QPoint()
        self._resizing_edge = Qt.Edge(0)
        self._mouse_press_pos = QPoint()
        self._mouse_press_geometry = QRect()

        # Native Windows resize border for frameless window hit testing
        self._resize_border = 8

        self._pipeline_thread: QThread | None = None
        self._pipeline_worker: PipelineWorker | None = None

        self._sync_thread: QThread | None = None
        self._sync_worker: SyncWorker | None = None
        self._live_collections: list[dict[str, Any]] = []
        self._collection_items_cache: dict[str, list[dict[str, Any]]] = {}

        self._graph_thread: QThread | None = None
        self._graph_worker: GraphWorker | None = None
        self._selected_collection_key = self.config.selected_collection_key.strip()

        self.top_nav = TopNavBar(self)
        self.workspace = Workspace(self)

        self.pipeline_panel = self.workspace.pipeline_panel
        self.pipeline_panel.set_selected_collection_key(self._selected_collection_key)

        self.sync_manager = LocalSyncManager(vault_path=self.config.vault_path, parent=self)
        self.sync_manager.start()

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self.top_nav)
        root.addWidget(self.workspace, 1)

        self.setCentralWidget(container)
        self._apply_dark_theme()
        self._connect_signals()
        self.workspace.update_vault_overview(self.config.vault_path)
        self._run_startup_health_check()
        self._start_initial_sync()
        self._trigger_startup_scan()

    def _trigger_startup_scan(self) -> None:
        """Scan vault and render brain map immediately on startup."""
        if not self.config.vault_path:
            return
            
        try:
            from ..core.obsidian_parser import ObsidianParser
            parser = ObsidianParser(self.config.vault_path)
            notes = parser.parse_vault()
            
            # Convert notes to dicts for the worker
            notes_payload = [asdict(note) for note in notes]
            self.workspace.update_notes(notes_payload)
            
            # Start graph worker with initial notes (empty collections for now)
            self._start_graph_worker(notes_payload, [])
        except Exception as exc:
            self.statusBar().showMessage(f"Startup scan failed: {exc}", 5000)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            edge = self._resize_edges_for_pos(event.pos())
            if edge != Qt.Edge(0):
                self._resizing_edge = edge
                self._mouse_press_pos = event.globalPosition().toPoint()
                self._mouse_press_geometry = self.geometry()
            elif self.top_nav.underMouse() and not self.top_nav.is_utility_area(event.pos()):
                # Drag window via title bar (if not clicking buttons)
                self._dragging = True
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.pos()
        global_pos = event.globalPosition().toPoint()

        if self._resizing_edge != Qt.Edge(0):
            diff = global_pos - self._mouse_press_pos
            new_geo = QRect(self._mouse_press_geometry)
            
            if self._resizing_edge & Qt.Edge.LeftEdge:
                new_geo.setLeft(self._mouse_press_geometry.left() + diff.x())
            if self._resizing_edge & Qt.Edge.RightEdge:
                new_geo.setRight(self._mouse_press_geometry.right() + diff.x())
            if self._resizing_edge & Qt.Edge.TopEdge:
                new_geo.setTop(self._mouse_press_geometry.top() + diff.y())
            if self._resizing_edge & Qt.Edge.BottomEdge:
                new_geo.setBottom(self._mouse_press_geometry.bottom() + diff.y())
                
            if new_geo.width() >= self.minimumWidth() and new_geo.height() >= self.minimumHeight():
                self.setGeometry(new_geo)
            event.accept()
        elif self._dragging:
            self.move(global_pos - self._drag_pos)
            event.accept()
        else:
            # Update cursor for resize preview
            edges = self._resize_edges_for_pos(pos)
            cursor = Qt.CursorShape.ArrowCursor
            if edges in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
                cursor = Qt.CursorShape.SizeVerCursor
            elif edges in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
                cursor = Qt.CursorShape.SizeHorCursor
            elif edges in (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
                cursor = Qt.CursorShape.SizeFDiagCursor
            elif edges in (Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.Edge.BottomEdge | Qt.Edge.LeftEdge):
                cursor = Qt.CursorShape.SizeBDiagCursor
            self.setCursor(cursor)
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        self._resizing_edge = Qt.Edge(0)
        self.unsetCursor()
        event.accept()

    def _resize_edges_for_pos(self, pos) -> Qt.Edge:
        """Return edge flags near the frame border for native system resize."""
        if self.isMaximized():
            return Qt.Edge(0)

        x = pos.x()
        y = pos.y()
        w = self.width()
        h = self.height()
        b = self._resize_border

        edges = Qt.Edge(0)
        if x <= b:
            edges |= Qt.Edge.LeftEdge
        elif x >= w - b:
            edges |= Qt.Edge.RightEdge
        if y <= b:
            edges |= Qt.Edge.TopEdge
        elif y >= h - b:
            edges |= Qt.Edge.BottomEdge
        return edges

    def toggle_maximize_restore(self) -> None:
        """Toggle between maximized and restored window state."""
        if self.isMaximized():
            self.showNormal()
            self.top_nav.maximize_button.setToolTip("Maximize")
            self.top_nav.maximize_button.setText("□")
        else:
            self.showMaximized()
            self.top_nav.maximize_button.setToolTip("Restore")
            self.top_nav.maximize_button.setText("❐")

    def changeEvent(self, event: QEvent) -> None:
        """Sync maximize/restore button visuals when window state changes externally
        (e.g. via taskbar click, Win+Arrow, or double-click title bar)."""
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMaximized():
                self.top_nav.maximize_button.setText("❐")
                self.top_nav.maximize_button.setToolTip("Restore")
            else:
                self.top_nav.maximize_button.setText("□")
                self.top_nav.maximize_button.setToolTip("Maximize")
        super().changeEvent(event)

    def closeEvent(self, event: Any) -> None:
        save_config(self.config_path, self.config)
        self.sync_manager.stop()
        self._stop_thread(self._pipeline_thread)
        self._stop_thread(self._sync_thread)
        self._stop_thread(self._graph_thread)
        super().closeEvent(event)

    def _connect_signals(self) -> None:
        self.top_nav.nav_changed.connect(self._on_nav_changed)
        self.top_nav.settings_clicked.connect(self._open_settings)
        self.top_nav.refresh_clicked.connect(self._refresh_all_sections)
        self.top_nav.minimize_requested.connect(self.showMinimized)
        self.top_nav.maximize_requested.connect(self.toggle_maximize_restore)
        self.top_nav.close_requested.connect(self.close)
        self.workspace.start_pipeline_requested.connect(self._start_pipeline)
        self.pipeline_panel.collection_selected.connect(self._set_selected_collection)
        self.pipeline_panel.create_collection_requested.connect(self._create_collection)

    def _refresh_all_sections(self) -> None:
        """Refresh Zotero collections, parsed notes, and brain map sections."""
        self.statusBar().showMessage("Refreshing pipeline, notes, and brain map...", 3000)
        self.workspace.update_vault_overview(self.config.vault_path)
        self._run_startup_health_check()
        self._trigger_startup_scan()
        self._start_collection_sync()

    def _on_nav_changed(self, key: str) -> None:
        mapping = {
            "obsidian_notes": "notes",
            "pipeline": "pipeline",
            "brain_map": "brain",
        }
        self.top_nav.set_active(key)
        self.workspace.set_view(mapping.get(key, "pipeline"))

    def _run_startup_health_check(self) -> None:
        issues = self.app_service.startup_health_check(self.config)
        if not issues:
            self.statusBar().showMessage("Startup health check passed", 3000)
            return

        summary = "; ".join(issues[:3])
        self.statusBar().showMessage(f"Startup health issues: {summary}", 6000)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = dialog.get_config()
            self._selected_collection_key = self.config.selected_collection_key.strip()
            
            # Validate vault path immediately after settings save
            validation = self.app_service.validate_vault_path(self.config.vault_path)
            
            save_config(self.config_path, self.config)
            self.sync_manager.set_vault_path(self.config.vault_path)
            self.workspace.update_vault_overview(self.config.vault_path)
            
            if validation["error"]:
                QMessageBox.warning(self, "Vault Configuration Warning", 
                    f"⚠️ {validation['error']}\n\nPlease reconfigure your Obsidian vault path in Settings.")
                self.statusBar().showMessage("⚠️ Vault path needs configuration", 5000)
            else:
                self.statusBar().showMessage("Settings saved", 3000)

    def _set_selected_collection(self, collection_key: str) -> None:
        self._selected_collection_key = collection_key.strip()
        self.pipeline_panel.set_selected_collection_key(self._selected_collection_key)
        self.config = replace(self.config, selected_collection_key=self._selected_collection_key)
        save_config(self.config_path, self.config)
        self._load_collection_elements(self._selected_collection_key)
        if self._selected_collection_key:
            self.statusBar().showMessage(f"Pipeline target collection set: {self._selected_collection_key}", 3500)
        else:
            self.statusBar().showMessage("Pipeline target collection cleared (all collections)", 3500)

    def _create_collection(self, name: str) -> None:
        collection_name = name.strip()
        if not collection_name:
            self.statusBar().showMessage("Enter a collection name before creating", 3000)
            return

        try:
            created = self.app_service.create_collection(self.config, collection_name)

            self._selected_collection_key = created.key.strip()
            self.pipeline_panel.set_selected_collection_key(self._selected_collection_key)
            self.config = replace(self.config, selected_collection_key=self._selected_collection_key)
            save_config(self.config_path, self.config)

            self.pipeline_panel.clear_create_collection_input()
            self.statusBar().showMessage(f"Created collection: {created.name}", 5000)
            self._start_collection_sync()
            self._load_collection_elements(self._selected_collection_key)
        except Exception as exc:
            QMessageBox.critical(self, "Create Collection Failed", f"Could not create collection:\n{exc}")

    def _start_pipeline(self) -> None:
        if self._thread_running(self._pipeline_thread):
            return

        self.workspace.set_pipeline_running(True)
        run_config = replace(self.config, selected_collection_key=self._selected_collection_key)

        self._pipeline_thread = QThread(self)
        self._pipeline_worker = PipelineWorker(self.app_root, run_config)
        self._pipeline_worker.moveToThread(self._pipeline_thread)

        self._pipeline_thread.started.connect(self._pipeline_worker.run)
        self._pipeline_worker.progress.connect(lambda progress: self.workspace.set_pipeline_progress(progress, None))
        self._pipeline_worker.status.connect(lambda text: self.workspace.set_pipeline_progress(self.workspace.progress_bar.value(), text))
        self._pipeline_worker.result.connect(self._on_pipeline_result)
        self._pipeline_worker.error.connect(self._on_pipeline_error)
        self._pipeline_worker.finished.connect(self._on_pipeline_finished)
        self._pipeline_worker.finished.connect(self._pipeline_thread.quit)
        self._pipeline_worker.finished.connect(self._cleanup_pipeline_refs)

        self._pipeline_thread.finished.connect(self._pipeline_thread.deleteLater)
        self._pipeline_thread.start()

    def _on_pipeline_result(self, payload: dict[str, Any]) -> None:
        notes = payload.get("notes", [])
        collections = payload.get("collections", [])
        graph_payload = payload.get("graph", {})
        errors = payload.get("errors", {})

        # Check for vault configuration error
        vault_error = errors.get("vault", "")
        if vault_error:
            QMessageBox.critical(self, "Pipeline Error", 
                f"Cannot start pipeline: {vault_error}\n\nPlease configure your Obsidian vault path in Settings.")
            self.workspace.set_pipeline_running(False)
            return

        self.workspace.update_vault_overview(self.config.vault_path)

        self.workspace.update_notes(notes)
        self.workspace.update_graph(graph_payload)
        self.pipeline_panel.update_collections(collections)
        self.pipeline_panel.set_connection_active(bool(collections))
        self.sync_manager.mark_synced()
        self.workspace.update_vault_overview(self.config.vault_path)

        if notes or collections:
            self._start_graph_worker(notes, collections)

        # Check for vault scan warning
        visible_errors = [message for message in errors.values() if message]
        if notes and len(notes) > 300:
            QMessageBox.warning(self, "Vault Scan Warning", 
                f"⚠️ Parsed {len(notes)} notes from vault. This seems high.\n\n"
                f"Your vault path may be too broad (e.g., Desktop instead of a specific vault folder).\n"
                f"Please update it in Settings.")
        elif visible_errors:
            self.statusBar().showMessage("Pipeline completed with warnings", 6000)

    def _on_pipeline_error(self, payload: dict[str, Any]) -> None:
        message = payload.get("message", "Unknown error")
        source = payload.get("source", "pipeline")
        QMessageBox.critical(self, "Pipeline Error", f"{message}\n\nSource: {source}")

    def _on_pipeline_finished(self) -> None:
        self.workspace.set_pipeline_running(False)
        self.workspace.set_pipeline_progress(100, "Pipeline complete")

    def _start_initial_sync(self) -> None:
        self._start_collection_sync()

    def _start_collection_sync(self) -> None:
        if self._thread_running(self._sync_thread):
            return

        self._live_collections = []
        self._collection_items_cache.clear()
        self.pipeline_panel.update_collections([])

        self._sync_thread = QThread(self)
        self._sync_worker = SyncWorker(host=self.config.zotero_host, library_id=self.config.zotero_library_id)
        self._sync_worker.moveToThread(self._sync_thread)

        self._sync_thread.started.connect(self._sync_worker.run)
        self._sync_worker.collection_updated.connect(self._on_collection_updated)
        self._sync_worker.error.connect(self._on_sync_error)
        self._sync_worker.sync_done.connect(self._on_sync_done)
        self._sync_worker.sync_done.connect(self._sync_thread.quit)
        self._sync_worker.sync_done.connect(self._cleanup_sync_refs)

        self._sync_thread.finished.connect(self._sync_thread.deleteLater)
        self._sync_thread.start()

    def _on_collection_updated(self, collection: dict[str, Any]) -> None:
        self._live_collections.append(collection)
        self.pipeline_panel.update_collections(self._live_collections)

    def _on_sync_done(self) -> None:
        self.pipeline_panel.set_connection_active(bool(self._live_collections))
        self._load_collection_elements(self._selected_collection_key)

    def _on_sync_error(self, payload: dict[str, Any]) -> None:
        message = payload.get("message", "Unknown error")
        self.pipeline_panel.set_connection_active(False)
        self.statusBar().showMessage(f"Pipeline sync failed: {message}", 6000)

    def _load_collection_elements(self, collection_key: str) -> None:
        key = collection_key.strip()
        if not key:
            self.pipeline_panel.update_collection_elements([])
            return

        if key in self._collection_items_cache:
            self.pipeline_panel.update_collection_elements(self._collection_items_cache[key])
            return

        try:
            items = self.app_service.get_collection_items(self.config, key)
            self._collection_items_cache[key] = items
            self.pipeline_panel.update_collection_elements(items)
        except Exception as exc:
            self.pipeline_panel.update_collection_elements([])
            self.statusBar().showMessage(f"Failed to load collection elements: {exc}", 6000)

    def _start_graph_worker(self, notes: list[dict[str, Any]], collections: list[dict[str, Any]]) -> None:
        if self._thread_running(self._graph_thread):
            return

        self._graph_thread = QThread(self)
        self._graph_worker = GraphWorker(notes, collections)
        self._graph_worker.moveToThread(self._graph_thread)

        self._graph_thread.started.connect(self._graph_worker.run)
        self._graph_worker.graph_ready.connect(self.workspace.update_graph)
        self._graph_worker.error.connect(
            lambda payload: self.statusBar().showMessage(
                f"Graph worker error: {payload.get('message', 'Unknown error')}",
                6000,
            )
        )
        self._graph_worker.finished.connect(self._graph_thread.quit)
        self._graph_worker.finished.connect(self._cleanup_graph_refs)

        self._graph_thread.finished.connect(self._graph_thread.deleteLater)
        self._graph_thread.start()

    def _apply_dark_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background-color: #09090b;
                color: #fafafa;
                font-family: "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 13px;
            }
            QMainWindow::separator {
                background: #27272a;
                width: 1px;
                height: 1px;
            }
            #TopHeaderBar {
                background-color: #09090b;
                border-bottom: 1px solid #27272a;
            }
            #TopNavTitle {
                color: #fafafa;
                font-size: 14px;
                font-weight: 800;
                letter-spacing: 1px;
            }
            #TopNavButton, #TopNavUtilityButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
                min-height: 34px;
                padding: 0 12px;
                color: #a1a1aa;
                text-align: center;
            }
            #TopNavButton:hover, #TopNavUtilityButton:hover {
                background-color: #18181b;
                color: #fafafa;
            }
            #TopNavButton:checked {
                background-color: #1e1b4b;
                color: #c4b5fd;
                border: 1px solid #312e81;
                font-weight: 600;
            }
            #PipelineHeadline {
                font-size: 42px;
                font-weight: 800;
                letter-spacing: -1.5px;
                line-height: 1;
                color: #fafafa;
            }
            #PipelineSubHeadline {
                font-size: 18px;
                font-weight: 400;
                color: #a1a1aa;
                line-height: 1.4;
            }
            #PipelineStatus,
            #VaultPathLabel {
                color: #a1a1aa;
                font-size: 11px;
            }
            #PipelineCollectionInfo,
            #PipelineCollectionMeta,
            #PipelineSyncChipSubtitle {
                color: #a1a1aa;
                font-size: 11px;
            }
            #PipelineStartButton {
                background-color: #7c3aed;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 16px;
                padding: 0 24px;
            }
            #PipelineStartButton:hover {
                background-color: #8b5cf6;
            }
            #PipelineStartButton:pressed {
                background-color: #6d28d9;
            }
            #PipelineStartButton:disabled {
                background-color: #27272a;
                color: #52525b;
            }
            #FeatureCard {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 12px;
            }
            #FeatureCard:hover {
                border-color: #3f3f46;
                background-color: #121214;
            }
            #FeatureCardTitle {
                font-weight: 600;
                font-size: 14px;
                color: #fafafa;
            }
            #FeatureCardDescription {
                color: #a1a1aa;
                font-size: 12px;
            }
            #PipelinePanel {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 12px;
            }
            #PipelineHeader {
                font-size: 18px;
                font-weight: 700;
                color: #fafafa;
                letter-spacing: -0.5px;
            }
            #PipelineSectionHeader {
                color: #71717a;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            #PipelineCollectionCard {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
            #PipelineCollectionCard[selected="true"] {
                border-color: #7c3aed;
                background-color: #1e1b4b;
            }
            #PipelineCollectionName {
                font-size: 13px;
                font-weight: 600;
                color: #fafafa;
            }
            #PipelineCollectionInfo, #PipelineCollectionMeta {
                color: #a1a1aa;
                font-size: 11px;
            }
            #PipelineSyncChip {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
            #PipelineSyncChipTitle {
                color: #c4b5fd;
                font-size: 11px;
                font-weight: 700;
            }
            #PipelineSyncChipSubtitle {
                color: #71717a;
                font-size: 10px;
            }
            #PipelineScrollArea {
                background: #09090b;
                border: none;
            }
            #PipelineProgressBar {
                border: 1px solid #27272a;
                border-radius: 6px;
                background-color: #18181b;
                text-align: center;
                height: 8px;
                color: transparent;
            }
            QLineEdit, QListWidget, QTableWidget, QTreeWidget {
                background-color: #09090b;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 8px;
                color: #fafafa;
                selection-background-color: #312e81;
                selection-color: #c4b5fd;
            }
            QLineEdit:focus {
                border-color: #7c3aed;
            }
            QHeaderView::section {
                background-color: #18181b;
                color: #a1a1aa;
                border: none;
                border-bottom: 1px solid #27272a;
                padding: 8px;
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
            }
            QProgressBar {
                border: 1px solid #27272a;
                border-radius: 6px;
                background-color: #18181b;
                text-align: center;
                height: 8px;
                color: transparent;
            }
            QProgressBar::chunk {
                background-color: #7c3aed;
                border-radius: 5px;
            }
            #PanelHeader {
                font-size: 22px;
                font-weight: 700;
                color: #fafafa;
                letter-spacing: -0.5px;
            }
            #NodeDrawer {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                border: none;
                background: #09090b;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #27272a;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3f3f46;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            /* Window control buttons — frameless title bar */
            #WindowMinimizeButton, #WindowMaximizeButton, #WindowCloseButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                color: #a1a1aa;
                font-size: 14px;
                font-weight: 600;
            }
            #WindowMinimizeButton:hover {
                background-color: #27272a;
                color: #fafafa;
            }
            #WindowMaximizeButton:hover {
                background-color: #27272a;
                color: #fafafa;
            }
            #WindowCloseButton:hover {
                background-color: #dc2626;
                color: #ffffff;
            }
            #WindowCloseButton:pressed {
                background-color: #b91c1c;
            }
            """
        )

    def _stop_thread(self, thread: QThread | None) -> None:
        if thread is None:
            return
        try:
            if thread.isRunning():
                thread.quit()
                thread.wait(2000)
        except RuntimeError:
            return

    def _thread_running(self, thread: QThread | None) -> bool:
        if thread is None:
            return False
        try:
            return thread.isRunning()
        except RuntimeError:
            return False

    def _cleanup_pipeline_refs(self) -> None:
        self._pipeline_worker = None
        self._pipeline_thread = None

    def _cleanup_sync_refs(self) -> None:
        self._sync_worker = None
        self._sync_thread = None

    def _cleanup_graph_refs(self) -> None:
        self._graph_worker = None
        self._graph_thread = None
