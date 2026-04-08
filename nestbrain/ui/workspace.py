from __future__ import annotations

from pathlib import Path
import re
import shutil
from typing import Any
from urllib.parse import quote, unquote

from PyQt6.QtCore import QEvent, QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QTextBlockFormat, QTextCursor, QTextDocument
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
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
)

from .brain_map_widget import BrainMapWidget
from .theme import (
    SPACING_SCALE,
    THEME_TOKENS,
    note_reader_browser_qss,
    note_reader_document_qss,
    note_reader_panel_qss,
    vault_tree_panel_qss,
)
from .zotero_panel import PipelinePanel


class FeatureCard(QFrame):
    def __init__(self, title: str, description: str, icon: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FeatureCard")
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(SPACING_SCALE["sm"])

        icon_label = QLabel(icon)
        icon_label.setObjectName("FeatureCardIcon")
        icon_label.setStyleSheet(
            "/* theme-harmonized */ "
            f"font-size: 20px; color: {THEME_TOKENS['accent_primary']}; font-weight: 700;"
        )
        
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
    previous_note_requested = pyqtSignal()
    next_note_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NoteReaderPanel")
        self._current_note_path: Path | None = None
        self._wikilink_pattern = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("NoteReaderHeader")
        top_bar.setFixedHeight(38)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(14, 0, 12, 0)
        top_bar_layout.setSpacing(10)

        self.note_search_input = QLineEdit()
        self.note_search_input.setObjectName("NoteResearchBar")
        self.note_search_input.setPlaceholderText("Research in note... (Press Enter to jump to the next result)")
        self.note_search_input.setClearButtonEnabled(True)
        self.note_search_input.setEnabled(False)
        self.note_search_input.textChanged.connect(self._on_note_search_changed)
        self.note_search_input.installEventFilter(self)

        self.previous_note_button = QPushButton("Previous")
        self.previous_note_button.setObjectName("NoteReaderNavButton")
        self.previous_note_button.setFixedHeight(24)
        self.previous_note_button.setEnabled(False)
        self.previous_note_button.clicked.connect(self.previous_note_requested.emit)

        self.next_note_button = QPushButton("Next")
        self.next_note_button.setObjectName("NoteReaderNavButton")
        self.next_note_button.setFixedHeight(24)
        self.next_note_button.setEnabled(False)
        self.next_note_button.clicked.connect(self.next_note_requested.emit)

        top_bar_layout.addWidget(self.note_search_input, 1)
        top_bar_layout.addWidget(self.previous_note_button)
        top_bar_layout.addWidget(self.next_note_button)

        self.body_stack = QStackedWidget()

        placeholder_wrap = QWidget()
        placeholder_wrap.setObjectName("NoteReaderPlaceholder")
        placeholder_layout = QVBoxLayout(placeholder_wrap)
        placeholder_layout.setContentsMargins(0, 0, 0, 0)
        placeholder_layout.addStretch(1)
        placeholder = QLabel("Select a note to read")
        placeholder.setObjectName("NoteReaderPlaceholderLabel")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder)
        placeholder_layout.addStretch(1)

        self.reader = QTextBrowser()
        self.reader.setObjectName("NoteReaderBrowser")
        self.reader.setReadOnly(True)
        self.reader.setOpenLinks(False)
        self.reader.setOpenExternalLinks(False)
        self.reader.anchorClicked.connect(self._on_anchor_clicked)
        self.reader.setFont(QFont("Segoe UI", 15))
        self.reader.setStyleSheet(note_reader_browser_qss())
        self.reader.document().setDefaultStyleSheet(note_reader_document_qss())
        self.reader.document().setDefaultFont(QFont("Segoe UI", 15))
        self.reader.document().setTextWidth(820)

        self.body_stack.addWidget(placeholder_wrap)
        self.body_stack.addWidget(self.reader)
        self.body_stack.setCurrentIndex(0)

        root.addWidget(top_bar)
        root.addWidget(self.body_stack, 1)
        self.setStyleSheet(note_reader_panel_qss())

    @property
    def current_note_path(self) -> Path | None:
        return self._current_note_path

    def clear_note(self) -> None:
        self._current_note_path = None
        self.reader.clear()
        self.body_stack.setCurrentIndex(0)
        self.note_search_input.setEnabled(False)
        self.set_navigation_state(False, False)

    def load_note(self, note_path: Path) -> None:
        try:
            content = note_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            QMessageBox.warning(self, "Read Failed", f"Could not read note:\n{exc}")
            self.clear_note()
            return

        self._current_note_path = note_path
        self.reader.setMarkdown(self._transform_wikilinks(content))
        self._apply_block_spacing()
        self.body_stack.setCurrentIndex(1)
        self.note_search_input.setEnabled(True)
        if self.note_search_input.text().strip():
            self._search_from_start()

    def set_navigation_state(self, has_previous: bool, has_next: bool) -> None:
        self.previous_note_button.setEnabled(has_previous)
        self.next_note_button.setEnabled(has_next)

    def eventFilter(self, watched: Any, event: Any) -> bool:
        if watched is self.note_search_input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                backward = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                self._find_in_note(backward=backward)
                return True
        return super().eventFilter(watched, event)

    def _on_note_search_changed(self, _: str) -> None:
        if self._current_note_path is None:
            return

        query = self.note_search_input.text().strip()
        if not query:
            cursor = self.reader.textCursor()
            cursor.clearSelection()
            self.reader.setTextCursor(cursor)
            return

        self._search_from_start()

    def _search_from_start(self) -> None:
        if self._current_note_path is None:
            return

        cursor = self.reader.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.reader.setTextCursor(cursor)
        self._find_in_note(backward=False)

    def _find_in_note(self, backward: bool = False) -> bool:
        if self._current_note_path is None:
            return False

        query = self.note_search_input.text().strip()
        if not query:
            return False

        flags = QTextDocument.FindFlag.FindBackward if backward else QTextDocument.FindFlag(0)
        found = self.reader.find(query, flags)
        if found:
            return True

        cursor = self.reader.textCursor()
        if backward:
            cursor.movePosition(QTextCursor.MoveOperation.End)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.reader.setTextCursor(cursor)
        return self.reader.find(query, flags)

    def _transform_wikilinks(self, content: str) -> str:
        def replacer(match: re.Match[str]) -> str:
            target = match.group(1).strip()
            alias = (match.group(2) or target).strip() or target
            encoded_target = quote(target, safe="")
            return f"[{alias}](nestbrain://note/{encoded_target})"

        return self._wikilink_pattern.sub(replacer, content)

    def _apply_block_spacing(self) -> None:
        doc = self.reader.document()
        if doc is None:
            return

        block = doc.firstBlock()
        while block.isValid():
            fmt = block.blockFormat()
            text = block.text().strip()
            heading_level = fmt.headingLevel()

            if not text:
                top_margin = 0.0
                bottom_margin = 0.0
            elif heading_level > 0:
                if heading_level == 1:
                    top_margin = 34.0
                    bottom_margin = 26.0
                elif heading_level == 2:
                    top_margin = 30.0
                    bottom_margin = 22.0
                else:
                    top_margin = 24.0
                    bottom_margin = 18.0
            elif block.textList() is not None:
                top_margin = 8.0
                bottom_margin = 10.0
            else:
                top_margin = 18.0
                bottom_margin = 18.0

            fmt.setTopMargin(top_margin)
            fmt.setBottomMargin(bottom_margin)

            block_cursor = QTextCursor(block)
            block_cursor.setBlockFormat(fmt)
            block = block.next()

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
        self.setObjectName("VaultTreePanel")
        self._vault_root: Path | None = None
        self._path_to_item: dict[str, QTreeWidgetItem] = {}
        self._note_index: dict[str, Path] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("VaultTreeHeader")
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 0, 12, 0)
        header_layout.setSpacing(8)

        self.tree_search_input = QLineEdit()
        self.tree_search_input.setObjectName("VaultResearchBar")
        self.tree_search_input.setPlaceholderText("Research notes...")
        self.tree_search_input.setClearButtonEnabled(True)
        self.tree_search_input.textChanged.connect(self._apply_tree_filter)

        header_layout.addWidget(self.tree_search_input, 1)

        self.tree = QTreeWidget()
        self.tree.setObjectName("VaultTreeWidget")
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemSelectionChanged.connect(self._emit_selection)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(14)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(False)
        self.tree.setIconSize(QSize(0, 0))

        root.addWidget(header)
        root.addWidget(self.tree, 1)

        self.setStyleSheet(vault_tree_panel_qss())

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
                    if child.name == ".obsidian":
                        continue
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
        self._apply_tree_filter(self.tree_search_input.text())

        if target_item is not None:
            self.tree.setCurrentItem(target_item)
        else:
            self.tree.clearSelection()
            self.note_selected.emit("")

    def _apply_tree_filter(self, text: str) -> None:
        query = text.strip().lower()

        for index in range(self.tree.topLevelItemCount()):
            top_item = self.tree.topLevelItem(index)
            if not query:
                self._set_item_visibility(top_item, True)
                continue
            self._filter_tree_item(top_item, query)

    def _set_item_visibility(self, item: QTreeWidgetItem, visible: bool) -> None:
        item.setHidden(not visible)
        for child_index in range(item.childCount()):
            self._set_item_visibility(item.child(child_index), visible)

    def _filter_tree_item(self, item: QTreeWidgetItem, query: str) -> bool:
        label = item.text(0).lower()
        path_text = str(item.data(0, self.ROLE_PATH) or "").lower()
        item_matches = query in label or query in path_text

        has_visible_child = False
        for child_index in range(item.childCount()):
            child_visible = self._filter_tree_item(item.child(child_index), query)
            has_visible_child = has_visible_child or child_visible

        visible = item_matches or has_visible_child
        item.setHidden(not visible)
        return visible

    def _create_item(self, label: str, path: Path, kind: str, is_root: bool = False) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        if kind == "folder":
            font = QFont(item.font(0))
            font.setWeight(QFont.Weight.DemiBold)
            item.setFont(0, font)
            item.setForeground(0, Qt.GlobalColor.lightGray)
        else:
            font = QFont(item.font(0))
            font.setWeight(QFont.Weight.Normal)
            item.setFont(0, font)
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
        root.setSpacing(SPACING_SCALE["md"])

        self.stacked = QStackedWidget()
        self.view_keys = {
            "pipeline": 0,
            "notes": 1,
            "brain": 2,
        }

        self._all_notes: list[dict[str, Any]] = []  # Initialize to avoid filter errors before first run
        self._ordered_note_paths: list[Path] = []
        self._current_note_index = -1

        self.pipeline_view = self._build_pipeline_view()
        self.notes_view = self._build_notes_view()
        self.brain_map_view = BrainMapWidget()
        self.brain_map_view.node_double_clicked.connect(self._on_brain_map_node_double_clicked)
        
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
        layout.setSpacing(SPACING_SCALE["xl"])

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
        layout.addSpacing(SPACING_SCALE["sm"])
        layout.addWidget(self.start_button)

        return scroll

    def _build_notes_view(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("NotesWorkspaceShell")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.vault_tree_panel = VaultTreePanel()
        self.note_reader_panel = NoteReaderPanel()
        self.vault_tree_panel.note_selected.connect(self._on_note_selected)
        self.note_reader_panel.note_link_requested.connect(self._on_note_link_requested)
        self.note_reader_panel.previous_note_requested.connect(self._on_previous_note_requested)
        self.note_reader_panel.next_note_requested.connect(self._on_next_note_requested)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("NotesMainSplitter")
        splitter.addWidget(self.vault_tree_panel)
        splitter.addWidget(self.note_reader_panel)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([280, 960])

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
        self._rebuild_note_order()
        self._sync_navigation_state(self.note_reader_panel.current_note_path)

    def update_graph(self, graph_payload: dict[str, Any]) -> None:
        self.brain_map_view.set_graph_data(graph_payload)

    def _open_note_path(self, note_path: Path) -> bool:
        if not note_path.exists() or not note_path.is_file():
            QMessageBox.warning(self, "Note Navigation Failed", f"Target note not found: {note_path}")
            return False

        if not self.vault_tree_panel.select_note_path(note_path):
            self.vault_tree_panel.refresh_tree(selected_path=note_path)

        self.note_reader_panel.load_note(note_path)
        self._sync_navigation_state(note_path)
        self.set_view("notes")
        return True

    def _resolve_note_path_from_label(self, label: str) -> Path | None:
        candidate = label.strip()
        if not candidate:
            return None

        resolved = self.vault_tree_panel.resolve_note_link(candidate)
        if resolved is not None:
            return resolved

        normalized_label = candidate.casefold()
        stem_label = Path(candidate).stem.casefold()

        for note in self._all_notes:
            path_value = str(note.get("path", "")).strip()
            if not path_value:
                continue

            note_path = Path(path_value)
            note_title = str(note.get("title", "")).strip()
            if note_title.casefold() == normalized_label or note_title.casefold() == stem_label:
                return note_path
            if note_path.stem.casefold() == normalized_label or note_path.stem.casefold() == stem_label:
                return note_path

        return None

    def _on_brain_map_node_double_clicked(self, label: str) -> None:
        note_path = self._resolve_note_path_from_label(label)
        if note_path is None:
            QMessageBox.warning(self, "Note Navigation Failed", f"Could not resolve note for node: {label}")
            return

        self._open_note_path(note_path)

    def update_vault_overview(self, vault_path: str) -> None:
        path = Path(vault_path).expanduser() if vault_path else Path()
        if path.exists() and path.is_dir():
            self.vault_tree_panel.set_vault_root(path)
            self._rebuild_note_order()
            self._sync_navigation_state(self.note_reader_panel.current_note_path)
            return

        self.vault_tree_panel.set_vault_root(None)
        self.note_reader_panel.clear_note()
        self._ordered_note_paths = []
        self._current_note_index = -1

    def _on_note_selected(self, note_path: str) -> None:
        if not note_path:
            self.note_reader_panel.clear_note()
            self._sync_navigation_state(None)
            return

        path = Path(note_path)
        if not path.exists() or not path.is_file():
            self.note_reader_panel.clear_note()
            self._sync_navigation_state(None)
            return

        self.note_reader_panel.load_note(path)
        self._sync_navigation_state(path)

    def _on_note_link_requested(self, target: str) -> None:
        target_path = self.vault_tree_panel.resolve_note_link(target)
        if target_path is None:
            target_path = self.vault_tree_panel.create_note_from_link(target)
            if target_path is None:
                QMessageBox.warning(self, "Link Navigation Failed", f"Could not resolve or create note for link: {target}")
                return

        self._open_note_path(target_path)

    def _on_previous_note_requested(self) -> None:
        self._navigate_relative(-1)

    def _on_next_note_requested(self) -> None:
        self._navigate_relative(1)

    def _navigate_relative(self, step: int) -> None:
        self._rebuild_note_order()
        if not self._ordered_note_paths:
            self._sync_navigation_state(None)
            return

        current_path = self.note_reader_panel.current_note_path
        if current_path is None:
            self._sync_navigation_state(None)
            return

        current_key = str(current_path.resolve())
        idx = -1
        for i, path in enumerate(self._ordered_note_paths):
            if str(path) == current_key:
                idx = i
                break

        if idx < 0:
            self._sync_navigation_state(None)
            return

        target_idx = idx + step
        if target_idx < 0 or target_idx >= len(self._ordered_note_paths):
            self._sync_navigation_state(self._ordered_note_paths[idx])
            return

        target_path = self._ordered_note_paths[target_idx]
        if not target_path.exists() or not target_path.is_file():
            self._rebuild_note_order()
            self._sync_navigation_state(current_path)
            return

        if not self.vault_tree_panel.select_note_path(target_path):
            self.vault_tree_panel.refresh_tree(selected_path=target_path)

        self.note_reader_panel.load_note(target_path)
        self._sync_navigation_state(target_path)

    def _rebuild_note_order(self) -> None:
        root = self.vault_tree_panel._vault_root
        if root is None or not root.exists() or not root.is_dir():
            self._ordered_note_paths = []
            self._current_note_index = -1
            return

        ordered: list[Path] = []

        def walk(folder: Path) -> None:
            try:
                children = sorted(folder.iterdir(), key=lambda child: (child.is_file(), child.name.lower()))
            except Exception:
                return

            for child in children:
                if child.is_dir():
                    if child.name == ".obsidian":
                        continue
                    walk(child)
                elif child.is_file() and child.suffix.lower() == ".md":
                    ordered.append(child.resolve())

        walk(root)
        self._ordered_note_paths = ordered

    def _sync_navigation_state(self, current_path: Path | None) -> None:
        self._rebuild_note_order()
        if current_path is None:
            self._current_note_index = -1
            self.note_reader_panel.set_navigation_state(False, False)
            return

        current_key = str(current_path.resolve())
        self._current_note_index = -1
        for i, path in enumerate(self._ordered_note_paths):
            if str(path) == current_key:
                self._current_note_index = i
                break

        if self._current_note_index < 0:
            self.note_reader_panel.set_navigation_state(False, False)
            return

        has_previous = self._current_note_index > 0
        has_next = self._current_note_index < len(self._ordered_note_paths) - 1
        self.note_reader_panel.set_navigation_state(has_previous, has_next)
