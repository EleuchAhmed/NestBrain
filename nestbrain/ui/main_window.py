from __future__ import annotations

from dataclasses import replace
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QThread, Qt
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
        form.addRow("Ollama Model", self.ollama_model_input)
        form.addRow("Zotero Library ID", self.zotero_id_input)
        form.addRow("Zotero API Key", self.zotero_api_key_input)
        form.addRow("Ollama Host", self.ollama_host_input)
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
            ollama_model=self.ollama_model_input.text().strip() or "mistral",
            zotero_library_id=self.zotero_id_input.text().strip(),
            zotero_api_key=self.zotero_api_key_input.text().strip(),
            ollama_host=self.ollama_host_input.text().strip() or "http://localhost:11434",
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

    def closeEvent(self, event: Any) -> None:
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
            "knowledge_map": "graph",
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
                background-color: #0e0f14;
                color: #ece9ff;
                font-family: Segoe UI;
                font-size: 13px;
            }
            #Sidebar {
                background-color: #161822;
                border-right: 1px solid #232536;
            }
            #SidebarTitle {
                font-size: 30px;
                font-weight: 700;
                color: #cdb7ff;
            }
            #SidebarSubtitle {
                color: #9ba0bf;
                margin-bottom: 10px;
            }
            #SidebarButton, #SidebarSettingsButton {
                background-color: #1b1d2a;
                border: 1px solid #262a3e;
                border-radius: 10px;
                min-height: 36px;
                text-align: left;
                padding-left: 12px;
            }
            #SidebarButton:checked {
                background-color: #2a2740;
                border-color: #6358a6;
            }
            #Headline {
                font-size: 48px;
                font-weight: 800;
                line-height: 1.1;
                color: #e9e1ff;
            }
            #SubHeadline {
                font-size: 20px;
                color: #b8b4cc;
            }
            #StartPipelineButton {
                background-color: #a88bf4;
                color: #1a1230;
                border: none;
                border-radius: 14px;
                font-weight: 700;
                font-size: 18px;
            }
            #StartPipelineButton:disabled {
                background-color: #5b5678;
                color: #dad3f7;
            }
            #FeatureCard {
                background-color: #141722;
                border: 1px solid #262a3f;
                border-radius: 12px;
            }
            #FeatureCardTitle {
                font-weight: 700;
                font-size: 15px;
            }
            #FeatureCardDescription {
                color: #b9bad1;
            }
            #ZoteroPanel {
                background-color: #161822;
                border-left: 1px solid #232536;
            }
            #ZoteroHeader {
                font-size: 20px;
                font-weight: 700;
            }
            #PanelSubLabel {
                color: #9196b8;
                font-size: 11px;
                letter-spacing: 1px;
            }
            #CollectionCard {
                background-color: #1a1d2b;
                border: 1px solid #282d42;
                border-radius: 10px;
            }
            #CollectionName {
                font-size: 14px;
                font-weight: 600;
            }
            #CollectionInfo, #CollectionMeta {
                color: #9ba0bf;
                font-size: 12px;
            }
            #SyncChip {
                background-color: #17192a;
                border: 1px solid #2a2d45;
                border-radius: 10px;
            }
            #SyncChipTitle {
                color: #d8c8ff;
                font-size: 11px;
                font-weight: 700;
            }
            #SyncChipSubtitle {
                color: #a1a7c8;
                font-size: 10px;
            }
            QLineEdit, QListWidget, QTableWidget {
                background-color: #161a25;
                border: 1px solid #2b3147;
                border-radius: 8px;
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #191c2a;
                color: #dcd9ef;
                border: none;
                padding: 6px;
            }
            QProgressBar {
                border: 1px solid #2f3350;
                border-radius: 8px;
                background-color: #141720;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #ab8df6;
                border-radius: 7px;
            }
            #PanelHeader {
                font-size: 26px;
                font-weight: 700;
            }
            #NodeDrawer {
                background-color: #161a25;
                border: 1px solid #2a2f44;
                border-radius: 10px;
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
