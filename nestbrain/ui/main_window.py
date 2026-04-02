from __future__ import annotations

from dataclasses import replace
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.pipeline_runner import PipelineConfig, PipelineRunner, save_config
from ..core.zotero_sync import ZoteroSyncClient
from ..ui.sidebar import Sidebar
from ..ui.workspace import Workspace
from ..ui.zotero_panel import LocalSyncManager, ZoteroPanel
from ..workers.graph_worker import GraphWorker
from ..workers.pipeline_worker import PipelineWorker
from ..workers.sync_worker import SyncWorker


class SettingsDialog(QDialog):
    def __init__(self, config: PipelineConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nestbrain Settings")
        self.setModal(True)
        self.resize(520, 260)

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

        self.ollama_model_input = QLineEdit(config.ollama_model)
        self.zotero_id_input = QLineEdit(config.zotero_library_id)
        self.zotero_api_key_input = QLineEdit(config.zotero_api_key)
        self.zotero_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ollama_host_input = QLineEdit(config.ollama_host)
        self.zotero_host_input = QLineEdit(config.zotero_host)

        form.addRow("Vault Path", vault_wrap)
        form.addRow("LLM Model", self.ollama_model_input)
        form.addRow("Zotero Library ID", self.zotero_id_input)
        form.addRow("Zotero API Key", self.zotero_api_key_input)
        form.addRow("LLM Host/Base URL", self.ollama_host_input)
        form.addRow("Zotero Host", self.zotero_host_input)

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

    def _browse_vault(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Obsidian Vault", self.vault_input.text() or str(Path.home()))
        if folder:
            self.vault_input.setText(folder)

    def get_config(self) -> PipelineConfig:
        return replace(
            self._config,
            vault_path=self.vault_input.text().strip(),
            ollama_model=self.ollama_model_input.text().strip() or "deepseek-ai/deepseek-r1",
            zotero_library_id=self.zotero_id_input.text().strip(),
            zotero_api_key=self.zotero_api_key_input.text().strip(),
            ollama_host=self.ollama_host_input.text().strip() or "https://integrate.api.nvidia.com/v1",
            zotero_host=self.zotero_host_input.text().strip() or "http://localhost:23119",
        )


class MainWindow(QMainWindow):
    def __init__(self, app_root: Path, config_path: Path, config: PipelineConfig) -> None:
        super().__init__()
        self.app_root = app_root
        self.config_path = config_path
        self.config = config

        self.setWindowTitle("Nestbrain")
        self.resize(1440, 900)

        self._pipeline_thread: QThread | None = None
        self._pipeline_worker: PipelineWorker | None = None

        self._sync_thread: QThread | None = None
        self._sync_worker: SyncWorker | None = None
        self._live_collections: list[dict[str, Any]] = []
        self._collection_items_cache: dict[str, list[dict[str, Any]]] = {}

        self._graph_thread: QThread | None = None
        self._graph_worker: GraphWorker | None = None
        self._selected_collection_key = self.config.selected_collection_key.strip()

        self.sidebar = Sidebar()
        self.workspace = Workspace()
        self.zotero_panel = ZoteroPanel()
        self.zotero_panel.set_selected_collection_key(self._selected_collection_key)

        self.sync_manager = LocalSyncManager(vault_path=self.config.vault_path, parent=self)
        self.sync_manager.sync_status_changed.connect(self.zotero_panel.update_sync_chip)
        self.sync_manager.start()

        container = QWidget()
        root = QHBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self.sidebar)
        root.addWidget(self.workspace, 1)
        root.addWidget(self.zotero_panel)

        self.setCentralWidget(container)
        self._apply_dark_theme()
        self._connect_signals()
        self._load_archive()
        self.workspace.update_vault_overview(self.config.vault_path)
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

    def closeEvent(self, event: Any) -> None:
        save_config(self.config_path, self.config)
        self.sync_manager.stop()
        self._stop_thread(self._pipeline_thread)
        self._stop_thread(self._sync_thread)
        self._stop_thread(self._graph_thread)
        super().closeEvent(event)

    def _connect_signals(self) -> None:
        self.sidebar.nav_changed.connect(self._on_nav_changed)
        self.sidebar.settings_clicked.connect(self._open_settings)
        self.workspace.start_pipeline_requested.connect(self._start_pipeline)
        self.zotero_panel.library_submitted.connect(self._set_zotero_library)
        self.zotero_panel.collection_selected.connect(self._set_selected_collection)
        self.zotero_panel.create_collection_requested.connect(self._create_zotero_collection)

    def _on_nav_changed(self, key: str) -> None:
        mapping = {
            "archive": "archive",
            "obsidian_notes": "notes",
            "zotero_sync": "home",
            "brain_map": "brain",
        }
        self.workspace.set_view(mapping.get(key, "home"))

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.config = dialog.get_config()
            self._selected_collection_key = self.config.selected_collection_key.strip()
            
            # Validate vault path immediately after settings save
            from ..core.pipeline_runner import PipelineRunner
            runner = PipelineRunner(self.app_root)
            validation = runner._validate_vault_path(self.config.vault_path)
            
            save_config(self.config_path, self.config)
            self.sync_manager.set_vault_path(self.config.vault_path)
            self.workspace.update_vault_overview(self.config.vault_path)
            
            if validation["error"]:
                QMessageBox.warning(self, "Vault Configuration Warning", 
                    f"⚠️ {validation['error']}\n\nPlease reconfigure your Obsidian vault path in Settings.")
                self.statusBar().showMessage("⚠️ Vault path needs configuration", 5000)
            else:
                self.statusBar().showMessage("Settings saved", 3000)

    def _set_zotero_library(self, value: str) -> None:
        self.config = replace(self.config, zotero_library_id=value)
        save_config(self.config_path, self.config)
        self._collection_items_cache.clear()
        self._start_zotero_sync()

    def _set_selected_collection(self, collection_key: str) -> None:
        self._selected_collection_key = collection_key.strip()
        self.zotero_panel.set_selected_collection_key(self._selected_collection_key)
        self.config = replace(self.config, selected_collection_key=self._selected_collection_key)
        save_config(self.config_path, self.config)
        self._load_collection_elements(self._selected_collection_key)
        if self._selected_collection_key:
            self.statusBar().showMessage(f"Pipeline target collection set: {self._selected_collection_key}", 3500)
        else:
            self.statusBar().showMessage("Pipeline target collection cleared (all collections)", 3500)

    def _create_zotero_collection(self, name: str) -> None:
        collection_name = name.strip()
        if not collection_name:
            self.statusBar().showMessage("Enter a collection name before creating", 3000)
            return

        try:
            client = ZoteroSyncClient(
                host=self.config.zotero_host,
                library_id=self.config.zotero_library_id,
                api_key=self.config.zotero_api_key,
            )
            created = client.create_collection(collection_name)

            self._selected_collection_key = created.key.strip()
            self.zotero_panel.set_selected_collection_key(self._selected_collection_key)
            self.config = replace(self.config, selected_collection_key=self._selected_collection_key)
            save_config(self.config_path, self.config)

            self.zotero_panel.clear_create_collection_input()
            self.statusBar().showMessage(f"Created Zotero collection: {created.name}", 5000)
            self._start_zotero_sync()
            self._load_collection_elements(self._selected_collection_key)
        except Exception as exc:
            QMessageBox.critical(self, "Create Collection Failed", f"Could not create Zotero collection:\n{exc}")

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
        self.zotero_panel.update_collections(collections)
        self.zotero_panel.set_connection_active(bool(collections))

        self._load_archive()
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

    def _on_pipeline_error(self, message: str) -> None:
        QMessageBox.critical(self, "Pipeline Error", message)

    def _on_pipeline_finished(self) -> None:
        self.workspace.set_pipeline_running(False)
        self.workspace.set_pipeline_progress(100, "Pipeline complete")

    def _start_initial_sync(self) -> None:
        self._start_zotero_sync()

    def _start_zotero_sync(self) -> None:
        if self._thread_running(self._sync_thread):
            return

        self._live_collections = []
        self._collection_items_cache.clear()
        self.zotero_panel.update_collections([])

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
        self.zotero_panel.update_collections(self._live_collections)

    def _on_sync_done(self) -> None:
        self.zotero_panel.set_connection_active(bool(self._live_collections))
        self._load_collection_elements(self._selected_collection_key)

    def _on_sync_error(self, message: str) -> None:
        self.zotero_panel.set_connection_active(False)
        self.statusBar().showMessage(f"Zotero sync failed: {message}", 6000)

    def _load_collection_elements(self, collection_key: str) -> None:
        key = collection_key.strip()
        if not key:
            self.zotero_panel.update_collection_elements([])
            return

        if key in self._collection_items_cache:
            self.zotero_panel.update_collection_elements(self._collection_items_cache[key])
            return

        try:
            client = ZoteroSyncClient(
                host=self.config.zotero_host,
                library_id=self.config.zotero_library_id,
                api_key=self.config.zotero_api_key,
            )
            items = [asdict(item) for item in client.get_items_for_collection(key)]
            self._collection_items_cache[key] = items
            self.zotero_panel.update_collection_elements(items)
        except Exception as exc:
            self.zotero_panel.update_collection_elements([])
            self.statusBar().showMessage(f"Failed to load collection elements: {exc}", 6000)

    def _start_graph_worker(self, notes: list[dict[str, Any]], collections: list[dict[str, Any]]) -> None:
        if self._thread_running(self._graph_thread):
            return

        self._graph_thread = QThread(self)
        self._graph_worker = GraphWorker(notes, collections)
        self._graph_worker.moveToThread(self._graph_thread)

        self._graph_thread.started.connect(self._graph_worker.run)
        self._graph_worker.graph_ready.connect(self.workspace.update_graph)
        self._graph_worker.error.connect(lambda message: self.statusBar().showMessage(f"Graph worker error: {message}", 6000))
        self._graph_worker.finished.connect(self._graph_thread.quit)
        self._graph_worker.finished.connect(self._cleanup_graph_refs)

        self._graph_thread.finished.connect(self._graph_thread.deleteLater)
        self._graph_thread.start()

    def _load_archive(self) -> None:
        archive = PipelineRunner(self.app_root).load_archive()
        self.workspace.update_archive(archive)

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
            #Sidebar {
                background-color: #09090b;
                border-right: 1px solid #27272a;
            }
            #SidebarTitle {
                font-size: 24px;
                font-weight: 800;
                letter-spacing: -0.5px;
                color: #fafafa;
                margin-top: 10px;
            }
            #SidebarSubtitle {
                color: #a1a1aa;
                font-size: 11px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 20px;
            }
            #SidebarButton, #SidebarSettingsButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                min-height: 32px;
                text-align: left;
                padding-left: 10px;
                color: #a1a1aa;
            }
            #SidebarButton:hover, #SidebarSettingsButton:hover {
                background-color: #18181b;
                color: #fafafa;
            }
            #SidebarButton:checked {
                background-color: #1e1b4b;
                color: #c4b5fd;
                border: 1px solid #312e81;
                font-weight: 600;
            }
            #Headline {
                font-size: 42px;
                font-weight: 800;
                letter-spacing: -1.5px;
                line-height: 1;
                color: #fafafa;
            }
            #SubHeadline {
                font-size: 18px;
                font-weight: 400;
                color: #a1a1aa;
                line-height: 1.4;
            }
            #StartPipelineButton {
                background-color: #7c3aed;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 16px;
                padding: 0 24px;
            }
            #StartPipelineButton:hover {
                background-color: #8b5cf6;
            }
            #StartPipelineButton:pressed {
                background-color: #6d28d9;
            }
            #StartPipelineButton:disabled {
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
            #ZoteroPanel {
                background-color: #09090b;
                border-left: 1px solid #27272a;
            }
            #ZoteroHeader {
                font-size: 18px;
                font-weight: 700;
                color: #fafafa;
                letter-spacing: -0.5px;
            }
            #PanelSubLabel {
                color: #71717a;
                font-size: 10px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            #CollectionCard {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
            #CollectionCard[selected="true"] {
                border-color: #7c3aed;
                background-color: #1e1b4b;
            }
            #CollectionName {
                font-size: 13px;
                font-weight: 600;
                color: #fafafa;
            }
            #CollectionInfo, #CollectionMeta {
                color: #a1a1aa;
                font-size: 11px;
            }
            #SyncChip {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
            #SyncChipTitle {
                color: #c4b5fd;
                font-size: 11px;
                font-weight: 700;
            }
            #SyncChipSubtitle {
                color: #71717a;
                font-size: 10px;
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
