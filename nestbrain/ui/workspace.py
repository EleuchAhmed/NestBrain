from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import quote, unquote

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QStyle,
)

from .brain_map_view import BrainMapView
from .zotero_panel import PipelinePanel


class FeatureCard(QFrame):
    def __init__(self, title: str, description: str, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FeatureCard")
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setObjectName("FeatureCardIcon")
        icon_label.setStyleSheet("font-size: 20px; color: #7c3aed; font-weight: 700;")
        
        title_label = QLabel(title)
        title_label.setObjectName("FeatureCardTitle")
        
        desc_label = QLabel(description)
        desc_label.setObjectName("FeatureCardDescription")
        desc_label.setWordWrap(True)

        layout.addWidget(icon_label)
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch(1)


class NoteReaderPanel(QWidget):
    note_link_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_note_path: Path | None = None
        self._full_note_name = ""
        self._wikilink_pattern = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_bar = QFrame()
        top_bar.setFixedHeight(32)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(10, 0, 10, 0)
        top_bar_layout.setSpacing(8)

        self.note_name_label = QLabel("No note selected")
        self.note_name_label.setStyleSheet("color: #888888; font-size: 12px;")

        self.open_in_editor_button = QPushButton("Open in Editor")
        self.open_in_editor_button.setFixedHeight(22)
        self.open_in_editor_button.setStyleSheet(
            "QPushButton {"
            "background-color: #222222; color: #bdbdbd; border: 1px solid #303030;"
            "padding: 0 8px; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background-color: #2a2a2a; color: #e0e0e0; }"
            "QPushButton:disabled { color: #666666; background-color: #1c1c1c; }"
        )
        self.open_in_editor_button.setEnabled(False)
        self.open_in_editor_button.clicked.connect(self._open_in_editor)

        top_bar_layout.addWidget(self.note_name_label, 1)
        top_bar_layout.addWidget(self.open_in_editor_button)

        self.body_stack = QStackedWidget()

        placeholder_wrap = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_wrap)
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.addStretch(1)
        placeholder = QLabel("Select a note to read")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #888888; font-size: 14px;")
        placeholder_layout.addWidget(placeholder)
        placeholder_layout.addStretch(1)

        self.reader = QTextBrowser()
        self.reader.setReadOnly(True)
        self.reader.setOpenLinks(False)
        self.reader.setOpenExternalLinks(False)
        self.reader.anchorClicked.connect(self._on_anchor_clicked)
        self.reader.setFont(QFont("Segoe UI", 13))
        self.reader.setStyleSheet(
            "QTextBrowser {"
            "background-color: #1a1a1a; color: #d8d8d8; border: none;"
            "font-family: 'Segoe UI', 'Inter', 'SF Pro Display';"
            "font-size: 13px; line-height: 1.8; padding: 26px 34px; }"
            "QTextBrowser::selection { background-color: #47408a; color: #f5f5f5; }"
        )
        self.reader.document().setDefaultStyleSheet(
            "body { color: #d8d8d8; background: #1a1a1a; font-size: 13px; line-height: 1.8; }"
            "h1 { font-size: 31px; color: #f4f4f4; margin-top: 26px; margin-bottom: 14px; font-weight: 750; letter-spacing: -0.03em; }"
            "h2 { font-size: 24px; color: #eeeeee; margin-top: 24px; margin-bottom: 10px; font-weight: 700; letter-spacing: -0.02em; }"
            "h3 { font-size: 19px; color: #e8e8e8; margin-top: 18px; margin-bottom: 8px; font-weight: 700; letter-spacing: -0.01em; }"
            "h4 { font-size: 16px; color: #dfdfdf; margin-top: 16px; margin-bottom: 8px; font-weight: 700; }"
            "p { margin-top: 0; margin-bottom: 13px; }"
            "ul, ol { margin-top: 8px; margin-bottom: 15px; padding-left: 32px; }"
            "ul > li, ol > li { margin-top: 5px; margin-bottom: 7px; }"
            "li { line-height: 1.72; }"
            "li > p { margin-top: 0; margin-bottom: 8px; }"
            "a { color: #8f9eff; text-decoration: none; }"
            "a:hover { color: #c0c8ff; text-decoration: underline; }"
            "strong { color: #f2f2f2; font-weight: 700; }"
            "code { background: #232531; color: #dbe4ff; padding: 2px 6px; border-radius: 4px; border: 1px solid #313548; font-family: 'JetBrains Mono', 'Fira Code', 'Courier New'; }"
            "pre { background: #13141a; border: 1px solid #2d3140; border-radius: 10px; padding: 14px 15px; margin: 12px 0; font-family: 'JetBrains Mono', 'Fira Code', 'Courier New'; }"
            "pre code { background: transparent; border: none; padding: 0; color: #dbe4ff; }"
            "blockquote {"
            "border-left: 3px solid #6c63ff; margin: 12px 0; padding: 6px 14px;"
            "background: #20212a; color: #c9c9d4; border-radius: 8px; }"
            "hr { border: none; border-top: 1px solid #2e2e2e; margin: 20px 0; }"
            "table { border-collapse: collapse; margin: 12px 0; width: 100%; }"
            "th, td { border: 1px solid #2c2f3a; padding: 8px 10px; vertical-align: top; }"
            "th { background: #20212a; color: #f0f0f0; font-weight: 700; }"
            "td { color: #d8d8d8; }"
        )
        self.reader.document().setDefaultFont(QFont("Segoe UI", 13))
        self.reader.document().setTextWidth(760)

        self.body_stack.addWidget(placeholder_wrap)
        self.body_stack.addWidget(self.reader)
        self.body_stack.setCurrentIndex(0)

        root.addWidget(top_bar)
        root.addWidget(self.body_stack, 1)

        self.setStyleSheet("QWidget { background-color: #1a1a1a; } QFrame { background-color: #141414; }")

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self._update_note_title()

    def clear_note(self) -> None:
        self._current_note_path = None
        self._full_note_name = "No note selected"
        self.reader.clear()
        self.body_stack.setCurrentIndex(0)
        self.open_in_editor_button.setEnabled(False)
        self._update_note_title()

    def load_note(self, note_path: Path) -> None:
        try:
            content = note_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            QMessageBox.warning(self, "Read Failed", f"Could not read note:\n{exc}")
            self.clear_note()
            return

        self._current_note_path = note_path
        self._full_note_name = note_path.name
        self.open_in_editor_button.setEnabled(True)
        self.reader.setMarkdown(self._transform_wikilinks(content))
        self.body_stack.setCurrentIndex(1)
        self._update_note_title()

    def _update_note_title(self) -> None:
        metrics = QFontMetrics(self.note_name_label.font())
        available = max(20, self.note_name_label.width())
        elided = metrics.elidedText(self._full_note_name, Qt.TextElideMode.ElideRight, available)
        self.note_name_label.setText(elided)
        self.note_name_label.setToolTip(self._full_note_name)

    def _open_in_editor(self) -> None:
        if self._current_note_path is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._current_note_path)))

    def _transform_wikilinks(self, content: str) -> str:
        def replacer(match: re.Match[str]) -> str:
            target = match.group(1).strip()
            alias = (match.group(2) or target).strip() or target
            encoded_target = quote(target, safe="")
            return f"[{alias}](nestbrain://note/{encoded_target})"

        return self._wikilink_pattern.sub(replacer, content)

    def _on_anchor_clicked(self, url: QUrl) -> None:
        scheme = url.scheme().lower()
        if scheme in {"http", "https", "mailto", "file"}:
            QDesktopServices.openUrl(url)
            return

        if scheme == "nestbrain" and url.host() == "note":
            raw_target = unquote(url.path().lstrip("/"))
            if raw_target:
                self.note_link_requested.emit(raw_target)


class VaultTreePanel(QWidget):
    note_selected = pyqtSignal(str)

    ROLE_PATH = Qt.ItemDataRole.UserRole
    ROLE_KIND = Qt.ItemDataRole.UserRole + 1
    ROLE_IS_ROOT = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vault_root: Path | None = None
        self._path_to_item: dict[str, QTreeWidgetItem] = {}
        self._note_index: dict[str, Path] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemSelectionChanged.connect(self._emit_selection)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(18)

        root.addWidget(self.tree, 1)

        self.setStyleSheet(
            "QWidget { background-color: #141414; }"
            "QTreeWidget { background-color: #141414; color: #d5d5d5; border: none; outline: none; padding: 4px 0; }"
            "QTreeWidget::item { height: 28px; padding-left: 4px; border-left: 2px solid transparent; }"
            "QTreeWidget::item:hover { background-color: #202435; color: #e5e9ff; }"
            "QTreeWidget::item:selected { background-color: #1f2540; border-left: 2px solid #7585ff; color: #f2f4ff; }"
            "QTreeView::branch:has-siblings:!adjoins-item { border-left: 1px solid #2a3046; }"
            "QTreeView::branch:has-siblings:adjoins-item { border-left: 1px solid #2a3046; border-bottom: 1px solid #2a3046; }"
            "QTreeView::branch:!has-children:!has-siblings:adjoins-item { border-bottom: 1px solid #2a3046; }"
            "QTreeView::branch:closed:has-children { image: none; border-image: none; }"
            "QTreeView::branch:open:has-children { image: none; border-image: none; }"
        )

    def set_vault_root(self, vault_root: Path | None) -> None:
        self._vault_root = vault_root
        self.refresh_tree()

    def refresh_tree(self, selected_path: Path | None = None) -> None:
        self.tree.clear()
        self._path_to_item.clear()
        self._note_index.clear()

        if self._vault_root is None or not self._vault_root.exists() or not self._vault_root.is_dir():
            placeholder = QTreeWidgetItem(["Vault path unavailable"])
            placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.tree.addTopLevelItem(placeholder)
            self.note_selected.emit("")
            return

        target_path = str(selected_path.resolve()) if selected_path else ""
        target_item: QTreeWidgetItem | None = None

        def build_tree(parent_item: QTreeWidgetItem, folder: Path) -> None:
            nonlocal target_item
            try:
                children = sorted(folder.iterdir(), key=lambda child: (child.is_file(), child.name.lower()))
            except Exception:
                return

            for child in children:
                if child.is_dir():
                    folder_item = self._create_item(child.name, child, "folder")
                    parent_item.addChild(folder_item)
                    self._path_to_item[str(child.resolve())] = folder_item
                    if target_path and str(child.resolve()) == target_path:
                        target_item = folder_item
                    build_tree(folder_item, child)
                elif child.is_file() and child.suffix.lower() == ".md":
                    note_item = self._create_item(child.stem, child, "note")
                    parent_item.addChild(note_item)
                    resolved = child.resolve()
                    self._path_to_item[str(resolved)] = note_item
                    self._index_note_path(resolved)
                    if target_path and str(child.resolve()) == target_path:
                        target_item = note_item

        build_tree(self.tree.invisibleRootItem(), self._vault_root)
        self.tree.expandToDepth(1)

        if target_item is not None:
            self.tree.setCurrentItem(target_item)
        else:
            self.tree.clearSelection()
            self.note_selected.emit("")

    def _create_item(self, label: str, path: Path, kind: str, is_root: bool = False) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        icon_type = QStyle.StandardPixmap.SP_DirIcon if kind == "folder" else QStyle.StandardPixmap.SP_FileIcon
        item.setIcon(0, self.style().standardIcon(icon_type))
        item.setData(0, self.ROLE_PATH, str(path))
        item.setData(0, self.ROLE_KIND, kind)
        item.setData(0, self.ROLE_IS_ROOT, is_root)
        return item

    def resolve_note_link(self, target: str) -> Path | None:
        if self._vault_root is None:
            return None

        clean_target = target.strip().replace("\\", "/")
        if not clean_target:
            return None

        candidate = self._vault_root / clean_target
        if candidate.suffix.lower() != ".md":
            candidate = candidate.with_suffix(".md")

        if candidate.exists() and candidate.is_file():
            return candidate

        key = self._normalize_key(Path(clean_target).stem)
        return self._note_index.get(key)

    def create_note_from_link(self, target: str) -> Path | None:
        if self._vault_root is None:
            return None

        clean_target = target.strip().replace("\\", "/")
        if not clean_target:
            return None

        segments = [segment.strip() for segment in clean_target.split("/") if segment.strip()]
        if not segments:
            return None

        safe_segments = [self._sanitize_segment(segment) for segment in segments]
        parent = self._vault_root.joinpath(*safe_segments[:-1]) if len(safe_segments) > 1 else self._vault_root
        filename = safe_segments[-1]
        if not filename.lower().endswith(".md"):
            filename = f"{filename}.md"

        note_path = parent / filename
        try:
            parent.mkdir(parents=True, exist_ok=True)
            if not note_path.exists():
                note_path.write_text(f"# {Path(filename).stem}\n", encoding="utf-8")
        except Exception:
            return None

        self.refresh_tree(selected_path=note_path)
        return note_path

    def select_note_path(self, note_path: Path) -> bool:
        key = str(note_path.resolve())
        item = self._path_to_item.get(key)
        if item is None:
            return False

        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)
        return True

    def _index_note_path(self, note_path: Path) -> None:
        stem_key = self._normalize_key(note_path.stem)
        if stem_key not in self._note_index:
            self._note_index[stem_key] = note_path

        try:
            rel = note_path.relative_to(self._vault_root)
            rel_key = self._normalize_key(str(rel.with_suffix("")).replace("\\", "/"))
            if rel_key not in self._note_index:
                self._note_index[rel_key] = note_path
        except Exception:
            return

    def _normalize_key(self, value: str) -> str:
        return " ".join(value.replace("_", " ").replace("-", " ").split()).lower()

    def _sanitize_segment(self, name: str) -> str:
        cleaned = name.strip().replace(":", "-")
        for ch in ('"', "<", ">", "|", "?", "*"):
            cleaned = cleaned.replace(ch, "")
        return cleaned or "Untitled"

    def _emit_selection(self) -> None:
        current = self.tree.currentItem()
        if current is None:
            self.note_selected.emit("")
            return

        kind = str(current.data(0, self.ROLE_KIND) or "")
        path_str = str(current.data(0, self.ROLE_PATH) or "")
        if kind == "note" and path_str:
            self.note_selected.emit(path_str)
            return

        self.note_selected.emit("")

    def _show_context_menu(self, pos: Any) -> None:
        item = self.tree.itemAt(pos)
        if item is None:
            return

        path_str = str(item.data(0, self.ROLE_PATH) or "")
        kind = str(item.data(0, self.ROLE_KIND) or "")
        is_root = bool(item.data(0, self.ROLE_IS_ROOT) or False)
        target = Path(path_str) if path_str else None
        if target is None:
            return

        menu = QMenu(self)
        if kind == "folder":
            new_note_action = menu.addAction("New Note")
            new_folder_action = menu.addAction("New Folder")
            rename_action = menu.addAction("Rename")
            delete_action = menu.addAction("Delete Folder")

            if is_root:
                rename_action.setEnabled(False)
                delete_action.setEnabled(False)

            chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
            if chosen == new_note_action:
                self._create_note(target)
            elif chosen == new_folder_action:
                self._create_folder(target)
            elif chosen == rename_action:
                self._rename_target(target, kind)
            elif chosen == delete_action:
                self._delete_folder(target)
            return

        if kind == "note":
            rename_action = menu.addAction("Rename")
            delete_action = menu.addAction("Delete Note")

            chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
            if chosen == rename_action:
                self._rename_target(target, kind)
            elif chosen == delete_action:
                self._delete_note(target)

    def _create_note(self, folder_path: Path) -> None:
        default_name = "Untitled"
        name, ok = QInputDialog.getText(self, "New Note", "Note name:", text=default_name)
        if not ok:
            return

        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Note name cannot be empty.")
            return
        if any(ch in name for ch in ("/", "\\")):
            QMessageBox.warning(self, "Invalid Name", "Note name cannot contain path separators.")
            return

        note_name = name if name.lower().endswith(".md") else f"{name}.md"
        note_path = folder_path / note_name
        if note_path.exists():
            QMessageBox.warning(self, "Already Exists", "A note with that name already exists.")
            return

        try:
            note_path.write_text("", encoding="utf-8")
        except Exception as exc:
            QMessageBox.warning(self, "Create Failed", f"Could not create note:\n{exc}")
            return

        self.refresh_tree(selected_path=note_path)

    def _create_folder(self, parent_path: Path) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok:
            return

        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Folder name cannot be empty.")
            return
        if any(ch in name for ch in ("/", "\\")):
            QMessageBox.warning(self, "Invalid Name", "Folder name cannot contain path separators.")
            return

        folder_path = parent_path / name
        if folder_path.exists():
            QMessageBox.warning(self, "Already Exists", "A folder with that name already exists.")
            return

        try:
            folder_path.mkdir(parents=False, exist_ok=False)
        except Exception as exc:
            QMessageBox.warning(self, "Create Failed", f"Could not create folder:\n{exc}")
            return

        self.refresh_tree(selected_path=folder_path)

    def _rename_target(self, target_path: Path, kind: str) -> None:
        default_name = target_path.stem if kind == "note" else target_path.name
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=default_name)
        if not ok:
            return

        name = name.strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Name cannot be empty.")
            return
        if any(ch in name for ch in ("/", "\\")):
            QMessageBox.warning(self, "Invalid Name", "Name cannot contain path separators.")
            return

        new_name = f"{name}.md" if kind == "note" else name
        if kind == "note" and name.lower().endswith(".md"):
            new_name = name
        new_path = target_path.with_name(new_name)

        if new_path.exists() and new_path != target_path:
            QMessageBox.warning(self, "Already Exists", "A file or folder with that name already exists.")
            return

        try:
            target_path.rename(new_path)
        except Exception as exc:
            QMessageBox.warning(self, "Rename Failed", f"Could not rename target:\n{exc}")
            return

        self.refresh_tree(selected_path=new_path)

    def _delete_note(self, note_path: Path) -> None:
        answer = QMessageBox.question(
            self,
            "Delete Note",
            f"Delete note '{note_path.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            note_path.unlink(missing_ok=False)
        except Exception as exc:
            QMessageBox.warning(self, "Delete Failed", f"Could not delete note:\n{exc}")
            return

        self.refresh_tree()

    def _delete_folder(self, folder_path: Path) -> None:
        answer = QMessageBox.question(
            self,
            "Delete Folder",
            f"Delete folder '{folder_path.name}' and all its contents?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            shutil.rmtree(folder_path)
        except Exception as exc:
            QMessageBox.warning(self, "Delete Failed", f"Could not delete folder:\n{exc}")
            return

        self.refresh_tree()


class Workspace(QWidget):
    start_pipeline_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(10)

        self.stacked = QStackedWidget()
        self.view_keys = {
            "pipeline": 0,
            "notes": 1,
            "brain": 2,
        }

        self._all_notes: list[dict[str, Any]] = []  # Initialize to avoid filter errors before first run

        self.pipeline_view = self._build_pipeline_view()
        self.notes_view = self._build_notes_view()
        self.brain_map_view = BrainMapView()
        
        self.stacked.addWidget(self.pipeline_view)
        self.stacked.addWidget(self.notes_view)
        self.stacked.addWidget(self.brain_map_view)

        root.addWidget(self.stacked)
        self.set_view("pipeline")

    def _build_pipeline_view(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("PipelineScrollArea")
        scroll.setWidgetResizable(True)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        headline = QLabel("Pipeline")
        headline.setObjectName("PipelineHeadline")

        subtitle = QLabel(
            "Deploy your local pipeline to synthesize Obsidian notes, Zotero collections, "
            "and research fragments into a cohesive map."
        )
        subtitle.setWordWrap(True)
        subtitle.setObjectName("PipelineSubHeadline")

        self.pipeline_panel = PipelinePanel()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setObjectName("PipelineProgressBar")

        self.status_label = QLabel("Pipeline idle")
        self.status_label.setObjectName("PipelineStatus")

        self.start_button = QPushButton("✦  Start Pipeline")
        self.start_button.setObjectName("PipelineStartButton")
        self.start_button.setFixedHeight(46)
        self.start_button.clicked.connect(self.start_pipeline_requested.emit)

        layout.addWidget(headline)
        layout.addWidget(subtitle)
        layout.addWidget(self.pipeline_panel)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)
        layout.addSpacing(8)
        layout.addWidget(self.start_button)

        return scroll

    def _build_notes_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.vault_tree_panel = VaultTreePanel()
        self.note_reader_panel = NoteReaderPanel()
        self.vault_tree_panel.note_selected.connect(self._on_note_selected)
        self.note_reader_panel.note_link_requested.connect(self._on_note_link_requested)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.vault_tree_panel)
        splitter.addWidget(self.note_reader_panel)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([260, 900])

        layout.addWidget(splitter, 1)
        return widget

    def set_view(self, key: str) -> None:
        index = self.view_keys.get(key, self.view_keys["pipeline"])
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
        self.vault_tree_panel.refresh_tree()

    def update_graph(self, graph_payload: dict[str, Any]) -> None:
        self.brain_map_view.set_graph_data(graph_payload)

    def update_vault_overview(self, vault_path: str) -> None:
        path = Path(vault_path).expanduser() if vault_path else Path()
        if path.exists() and path.is_dir():
            self.vault_tree_panel.set_vault_root(path)
            return

        self.vault_tree_panel.set_vault_root(None)
        self.note_reader_panel.clear_note()

    def _on_note_selected(self, note_path: str) -> None:
        if not note_path:
            self.note_reader_panel.clear_note()
            return

        path = Path(note_path)
        if not path.exists() or not path.is_file():
            self.note_reader_panel.clear_note()
            return

        self.note_reader_panel.load_note(path)

    def _on_note_link_requested(self, target: str) -> None:
        target_path = self.vault_tree_panel.resolve_note_link(target)
        if target_path is None:
            target_path = self.vault_tree_panel.create_note_from_link(target)
            if target_path is None:
                QMessageBox.warning(self, "Link Navigation Failed", f"Could not resolve or create note for link: {target}")
                return

        if not target_path.exists() or not target_path.is_file():
            QMessageBox.warning(self, "Link Navigation Failed", f"Target note not found: {target_path}")
            return

        if not self.vault_tree_panel.select_note_path(target_path):
            self.vault_tree_panel.refresh_tree(selected_path=target_path)

        self.note_reader_panel.load_note(target_path)
