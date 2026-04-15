from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
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

    def __init__(self, parent: QWidget | None = None, logo_path: str | Path | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TopHeaderBar")
        self.setFixedHeight(56)

        self._logo_path = Path(logo_path) if logo_path is not None else None

        self.nav_items: list[NavItem] = [
            NavItem("brain_map", "Brain-Map", "⊙"),
            NavItem("notes", "Notes", "≡"),
            NavItem("pipeline", "Pipeline", "✦"),
        ]

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(16, 8, 16, 8)
        root_layout.setSpacing(12)

        brand_container = QWidget()
        brand_container.setObjectName("TopNavBrandContainer")
        brand_layout = QHBoxLayout(brand_container)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(10)

        logo_frame = QFrame()
        logo_frame.setObjectName("TopNavLogoFrame")
        logo_frame.setFixedSize(32, 32)

        logo_layout = QHBoxLayout(logo_frame)
        logo_layout.setContentsMargins(4, 4, 4, 4)
        logo_layout.setSpacing(0)

        self.logo_label = QLabel()
        self.logo_label.setObjectName("TopNavLogo")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setFixedSize(24, 24)
        self._set_logo_pixmap()
        logo_layout.addWidget(self.logo_label)

        title = QLabel("NESTBRAIN")
        title.setObjectName("TopNavTitle")

        brand_layout.addWidget(logo_frame)
        brand_layout.addWidget(title)
        root_layout.addWidget(brand_container)

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

    def _set_logo_pixmap(self) -> None:
        if self._logo_path is not None and self._logo_path.exists():
            pixmap = QPixmap(str(self._logo_path))
            if not pixmap.isNull():
                self.logo_label.setPixmap(
                    pixmap.scaled(
                        self.logo_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.logo_label.setToolTip(f"Custom logo loaded from {self._logo_path}")
                return

        self.logo_label.setText("NB")
        self.logo_label.setToolTip("Place your PNG at nestbrain/assets/logo.png")

    def set_active(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def _emit_nav(self, key: str) -> None:
        self.nav_changed.emit(key)
