from __future__ import annotations

from dataclasses import replace
from dataclasses import asdict
from datetime import datetime
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QProcess, QThread, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from ..core.app_service import NestbrainAppService
from ..core.paths import get_resource_root
from ..core.pipeline_runner import PipelineConfig, save_config
from ..ui.ambient_background import AmbientNodeBackground
from ..ui.sidebar import TopNavBar
from ..ui.theme import get_app_stylesheet
from ..ui.workspace import Workspace
from ..ui.zotero_panel import LocalSyncManager
from ..workers.graph_worker import GraphWorker
from ..workers.pipeline_worker import PipelineWorker
from ..workers.sync_worker import SyncWorker


class SettingsDialog(QDialog):
    def __init__(self, config: PipelineConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SettingsDialog")
        self.setWindowTitle("Nestbrain Settings")
        self.setModal(True)
        self.resize(700, 460)

        self._config = config
        self._auth_process: QProcess | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        title = QLabel("Settings")
        title.setObjectName("SettingsDialogTitle")
        subtitle = QLabel("Configure your vault, API credentials, and service endpoints.")
        subtitle.setObjectName("SettingsDialogSectionHint")

        config_card = QWidget()
        config_card.setObjectName("SettingsSectionCard")
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(16, 14, 16, 14)
        config_layout.setSpacing(12)

        config_title = QLabel("Configuration")
        config_title.setObjectName("SettingsSectionTitle")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)

        def _field_label(text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("SettingsFieldLabel")
            return label

        vault_row = QHBoxLayout()
        vault_row.setSpacing(8)
        self.vault_input = QLineEdit(config.vault_path)
        self.vault_input.setPlaceholderText("Path to your note vault")
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("SettingsBrowseButton")
        browse_btn.clicked.connect(self._browse_vault)
        vault_row.addWidget(self.vault_input, 1)
        vault_row.addWidget(browse_btn)

        vault_wrap = QWidget()
        vault_wrap.setLayout(vault_row)

        self.nvidia_api_key_input = QLineEdit(config.nvidia_api_key)
        self.nvidia_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.nvidia_api_key_input.setPlaceholderText("NVIDIA API key")
        self.zotero_id_input = QLineEdit(config.zotero_library_id)
        self.zotero_id_input.setPlaceholderText("Zotero library ID")
        self.zotero_api_key_input = QLineEdit(config.zotero_api_key)
        self.zotero_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.zotero_api_key_input.setPlaceholderText("Zotero API key")
        nvidia_host_value = str(getattr(config, "nvidia_host", getattr(config, "ollama_host", "")))
        self.nvidia_host_input = QLineEdit(nvidia_host_value)
        self.nvidia_host_input.setPlaceholderText("https://integrate.api.nvidia.com/v1")
        self.zotero_host_input = QLineEdit(config.zotero_host)
        self.zotero_host_input.setPlaceholderText("http://localhost:23119")

        notebooklm_row = QHBoxLayout()
        notebooklm_row.setSpacing(8)
        self.notebooklm_auth_btn = QPushButton("Authenticate")
        self.notebooklm_auth_btn.setObjectName("SettingsActionButton")
        self.notebooklm_refresh_btn = QPushButton("Refresh Status")
        self.notebooklm_refresh_btn.setObjectName("SettingsActionButton")
        self.notebooklm_status_label = QLabel("")
        self.notebooklm_status_label.setObjectName("NotebookLMStatusLabel")
        notebooklm_row.addWidget(self.notebooklm_auth_btn)
        notebooklm_row.addWidget(self.notebooklm_refresh_btn)
        notebooklm_row.addWidget(self.notebooklm_status_label, 1)

        notebooklm_wrap = QWidget()
        notebooklm_wrap.setLayout(notebooklm_row)

        self.notebooklm_auth_btn.clicked.connect(self._authenticate_notebooklm)
        self.notebooklm_refresh_btn.clicked.connect(self._refresh_notebooklm_status)

        form.addRow(_field_label("Vault Path"), vault_wrap)
        form.addRow(_field_label("NVIDIA API Key"), self.nvidia_api_key_input)
        form.addRow(_field_label("Zotero Library ID"), self.zotero_id_input)
        form.addRow(_field_label("Zotero API Key"), self.zotero_api_key_input)
        form.addRow(_field_label("NVIDIA NIM Host / Base URL"), self.nvidia_host_input)
        form.addRow(_field_label("Zotero Host"), self.zotero_host_input)
        form.addRow(_field_label("NotebookLM Account"), notebooklm_wrap)

        config_layout.addWidget(config_title)
        config_layout.addLayout(form)

        button_row = QHBoxLayout()
        button_row_wrap = QWidget()
        button_row_wrap.setObjectName("SettingsButtonRow")
        button_row_wrap.setLayout(button_row)
        button_row.setSpacing(8)
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("SettingsSecondaryButton")
        save_button = QPushButton("Save")
        save_button.setObjectName("SettingsPrimaryButton")

        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)

        button_row.addStretch(1)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(config_card)
        root.addWidget(button_row_wrap)
        self._refresh_notebooklm_status()

    def _browse_vault(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Note Vault", self.vault_input.text() or str(Path.home()))
        if folder:
            self.vault_input.setText(folder)

    def _authenticate_notebooklm(self) -> None:
        try:
            if self._auth_process and self._auth_process.state() != QProcess.ProcessState.NotRunning:
                self.notebooklm_status_label.setText("Authentication is already in progress.")
                return

            if getattr(sys, "frozen", False):
                arguments = ["--notebooklm-auth"]
            else:
                arguments = ["-m", "nestbrain.core.notebooklm_browser_auth"]

            process = QProcess(self)
            process.setProgram(sys.executable)
            process.setArguments(arguments)
            process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            process.finished.connect(self._on_notebooklm_auth_finished)
            process.errorOccurred.connect(self._on_notebooklm_auth_error)
            self._auth_process = process

            self.notebooklm_auth_btn.setEnabled(False)
            self.notebooklm_status_label.setText("Authentication in progress. Complete login in the browser window.")
            process.start()
            if not process.waitForStarted(3000):
                self.notebooklm_auth_btn.setEnabled(True)
                self._auth_process = None
                process.deleteLater()
                raise RuntimeError(process.errorString() or "Process failed to start.")
        except Exception as exc:
            QMessageBox.critical(self, "NotebookLM Authentication Failed", f"Could not launch authentication flow:\n{exc}")

    def _on_notebooklm_auth_error(self, _error: QProcess.ProcessError) -> None:
        self.notebooklm_auth_btn.setEnabled(True)
        self.notebooklm_status_label.setText("Authentication failed to start. Please try again.")
        if self._auth_process:
            self._auth_process.deleteLater()
            self._auth_process = None

    def _on_notebooklm_auth_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self.notebooklm_auth_btn.setEnabled(True)

        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
            self._refresh_notebooklm_status()
            if self.notebooklm_status_label.text() == "Not authenticated":
                self.notebooklm_status_label.setText(
                    "Authentication finished, but tokens were not detected. Please retry."
                )
        else:
            self.notebooklm_status_label.setText(
                "Authentication did not complete successfully. Please try again."
            )

        if self._auth_process:
            self._auth_process.deleteLater()
            self._auth_process = None

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
            ollama_host=self.nvidia_host_input.text().strip() or "https://integrate.api.nvidia.com/v1",
            zotero_host=self.zotero_host_input.text().strip() or "http://localhost:23119",
        )


class MainWindow(QMainWindow):
    def __init__(self, app_root: Path, config_path: Path, config: PipelineConfig) -> None:
        super().__init__()
        assets_dir = app_root / "assets"
        icon_path = assets_dir / "app.ico"
        if not icon_path.exists() and assets_dir.exists():
            fallback_icons = sorted(assets_dir.glob("*.ico"))
            icon_path = fallback_icons[0] if fallback_icons else icon_path

        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Use a native top-level window so Windows owns resize/maximize/snap behavior.
        self.setWindowFlags(Qt.WindowType.Window)

        self.app_root = app_root
        self.config_path = config_path
        self.config = config
        self.app_service = NestbrainAppService(app_root)

        self.setWindowTitle("Nestbrain | Pipeline")
        self.setMinimumSize(800, 600)
        self._apply_default_window_geometry()

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
        self.ambient_background = AmbientNodeBackground()

        self.pipeline_panel = self.workspace.pipeline_panel
        self.pipeline_panel.set_selected_collection_key(self._selected_collection_key)

        self.sync_manager = LocalSyncManager(vault_path=self.config.vault_path, parent=self)
        self.sync_manager.start()

        container = QWidget()
        container.setObjectName("MainWindowShell")
        stacked = QStackedLayout(container)
        stacked.setStackingMode(QStackedLayout.StackingMode.StackAll)
        stacked.setContentsMargins(0, 0, 0, 0)
        stacked.setSpacing(0)

        content = QWidget()
        content.setObjectName("MainWindowContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.top_nav)
        content_layout.addWidget(self.workspace, 1)

        stacked.addWidget(self.ambient_background)
        stacked.addWidget(content)

        self.setCentralWidget(container)
        self._apply_dark_theme()
        self._connect_signals()
        self.workspace.update_vault_overview(self.config.vault_path)
        self._run_startup_health_check()
        self._start_initial_sync()
        self._trigger_startup_scan()

    def _apply_default_window_geometry(self) -> None:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(1280, 720)
            return

        available = screen.availableGeometry()
        width = max(800, int(available.width() * 0.8))
        height = max(600, int(available.height() * 0.8))
        self.resize(width, height)

        centered_x = available.x() + (available.width() - width) // 2
        centered_y = available.y() + (available.height() - height) // 2
        self.move(centered_x, centered_y)

    def _trigger_startup_scan(self) -> None:
        """Scan vault and render brain map immediately on startup."""
        if not self.config.vault_path:
            return
            
        try:
            from ..core.note_parser import MarkdownNoteParser
            parser = MarkdownNoteParser(self.config.vault_path)
            notes = parser.parse_vault()

            # Convert notes to dicts for the worker
            notes_payload = [asdict(note) for note in notes]
            self.workspace.update_notes(notes_payload)

            # Start graph worker with initial notes (empty collections for now)
            self._start_graph_worker(notes_payload, [])
        except Exception as exc:
            self.statusBar().showMessage(f"Startup scan failed: {exc}", 5000)

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
            "notes": "notes",
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
                    f"⚠️ {validation['error']}\n\nPlease reconfigure your note vault path in Settings.")
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
                f"Cannot start pipeline: {vault_error}\n\nPlease configure your note vault path in Settings.")
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
        self.setStyleSheet(get_app_stylesheet())

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
