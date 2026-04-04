from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: str


class Sidebar(QWidget):
    nav_changed = pyqtSignal(str)
    settings_clicked = pyqtSignal()
    refresh_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setMinimumWidth(220)
        self.setMaximumWidth(240)

        self.nav_items: list[NavItem] = [
            NavItem("brain_map", "Brain-Map", "⊙"),
            NavItem("archive", "Archive", "⊞"),
            NavItem("obsidian_notes", "Notes", "≡"),
            NavItem("zotero_sync", "Zotero", "♽"),
        ]

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(16)

        title = QLabel("NESTBRAIN")
        title.setObjectName("SidebarTitle")
        subtitle = QLabel("EtherealArchivist")
        subtitle.setObjectName("SidebarSubtitle")

        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        nav_container = QFrame()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 8, 0, 8)
        nav_layout.setSpacing(8)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}

        for nav in self.nav_items:
            button = QPushButton(f"{nav.icon}  {nav.label}")
            button.setCheckable(True)
            button.setObjectName("SidebarButton")
            button.clicked.connect(lambda checked, key=nav.key: self._emit_nav(key))
            self.button_group.addButton(button)
            nav_layout.addWidget(button)
            self.buttons[nav.key] = button

        root_layout.addWidget(nav_container)
        root_layout.addStretch(1)

        self.settings_button = QPushButton("⚙  Settings")
        self.settings_button.setObjectName("SidebarSettingsButton")
        self.settings_button.clicked.connect(self.settings_clicked.emit)

        self.refresh_button = QPushButton("↻  Refresh")
        self.refresh_button.setObjectName("SidebarSettingsButton")
        self.refresh_button.clicked.connect(self.refresh_clicked.emit)

        root_layout.addWidget(self.refresh_button)
        root_layout.addWidget(self.settings_button)
        self.set_active("brain_map")

    def set_active(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def _emit_nav(self, key: str) -> None:
        self.nav_changed.emit(key)
