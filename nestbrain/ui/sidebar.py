from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: str


class TopNavBar(QWidget):
    nav_changed = pyqtSignal(str)
    settings_clicked = pyqtSignal()
    refresh_clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopHeaderBar")
        self.setFixedHeight(56)

        self.nav_items: list[NavItem] = [
            NavItem("brain_map", "Brain-Map", "⊙"),
            NavItem("obsidian_notes", "Notes", "≡"),
            NavItem("pipeline", "Pipeline", "✦"),
        ]

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(16, 8, 16, 8)
        root_layout.setSpacing(12)

        title = QLabel("NESTBRAIN")
        title.setObjectName("TopNavTitle")

        root_layout.addWidget(title)

        nav_container = QFrame()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(12, 0, 12, 0)
        nav_layout.setSpacing(8)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}

        for nav in self.nav_items:
            button = QPushButton(f"{nav.icon}  {nav.label}")
            button.setCheckable(True)
            button.setObjectName("TopNavButton")
            button.setMinimumHeight(34)
            button.clicked.connect(lambda checked, key=nav.key: self._emit_nav(key))
            self.button_group.addButton(button)
            nav_layout.addWidget(button)
            self.buttons[nav.key] = button

        root_layout.addWidget(nav_container)
        root_layout.addStretch(1)

        utility_row = QHBoxLayout()
        utility_row.setSpacing(8)

        self.settings_button = QPushButton("⚙  Settings")
        self.settings_button.setObjectName("TopNavUtilityButton")
        self.settings_button.setMinimumHeight(34)
        self.settings_button.clicked.connect(self.settings_clicked.emit)

        self.refresh_button = QPushButton("↻  Refresh")
        self.refresh_button.setObjectName("TopNavUtilityButton")
        self.refresh_button.setMinimumHeight(34)
        self.refresh_button.clicked.connect(self.refresh_clicked.emit)
        utility_row.addWidget(self.refresh_button)
        utility_row.addWidget(self.settings_button)

        utility_container = QWidget()
        utility_container.setLayout(utility_row)
        root_layout.addWidget(utility_container)
        self.set_active("pipeline")

    def set_active(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def _emit_nav(self, key: str) -> None:
        self.nav_changed.emit(key)
