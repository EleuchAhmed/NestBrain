from __future__ import annotations

THEME_TOKENS = {
    "bg_app": "#0F0415",  # /* theme-harmonized */
    "bg_surface": "#1A0E2E",  # /* theme-harmonized */
    "bg_surface_soft": "#24143E",  # /* theme-harmonized */
    "bg_surface_raised": "#31204B",  # /* theme-harmonized */
    "bg_input": "#281643",  # /* theme-harmonized */
    "text_primary": "#FFFFFF",  # /* theme-harmonized */
    "text_secondary": "#E8D5FF",  # /* theme-harmonized */
    "text_muted": "#C4AEDF",  # /* theme-harmonized */
    "text_hint": "#A68BC7",  # /* theme-harmonized */
    "accent_primary": "#D8BFFF",  # /* theme-harmonized */
    "accent_deep": "#6B3FA0",  # /* theme-harmonized */
    "accent_indigo": "#5E35B1",  # /* theme-harmonized */
    "accent_blush": "#FFB3C1",  # /* theme-harmonized */
    "border": "#6B4A99",  # /* theme-harmonized */
    "border_soft": "#4A3470",  # /* theme-harmonized */
    "border_strong": "#8D6AC2",  # /* theme-harmonized */
    "selection_bg": "rgba(196, 156, 255, 0.34)",  # /* theme-harmonized */
    "selection_fg": "#FFFFFF",  # /* theme-harmonized */
    "glow_soft": "rgba(216, 191, 255, 0.14)",  # /* theme-harmonized */
    "glow_strong": "rgba(216, 191, 255, 0.24)",  # /* theme-harmonized */
    "gloss": "rgba(255, 255, 255, 0.08)",  # /* theme-harmonized */
}

SPACING_SCALE = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
}

RADIUS_SCALE = {
    "input": 4,
    "sidebar": 6,
    "panel": 8,
    "pill": 100,
}

SPACING_EXTENDED = {
    "button_height_small": 32,
    "button_height_medium": 40,
    "button_height_large": 52,
    "sidebar_width": 280,
}


def get_app_stylesheet() -> str:
    t = THEME_TOKENS
    return f"""
    /* theme-harmonized */
    QWidget {{
        background-color: {t['bg_app']};
        color: {t['text_secondary']};
        font-family: "Segoe UI", "SF Pro Display", "Inter";
        font-size: 13px;
    }}

    QMainWindow::separator {{
        background: {t['border_soft']};
        width: 1px;
        height: 1px;
    }}

    #MainWindowShell,
    #MainWindowContent,
    #AmbientNodeBackground {{
        background: transparent;
        border: none;
    }}

    QMessageBox,
    QDialog#SettingsDialog {{
        background-color: rgba(26, 14, 46, 0.95);
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
    }}

    QDialog#SettingsDialog QLabel,
    QMessageBox QLabel {{
        color: {t['text_secondary']};
    }}

    #SettingsDialogTitle {{
        color: {t['text_primary']};
        font-size: 19px;
        font-weight: 800;
    }}

    #SettingsDialogSectionHint {{
        color: {t['text_hint']};
        font-size: 11px;
        font-weight: 500;
        margin-bottom: 2px;
    }}

    #SettingsSectionCard,
    #SettingsButtonRow {{
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
    }}

    #SettingsSectionTitle {{
        color: {t['text_primary']};
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }}

    #SettingsFieldLabel {{
        color: {t['text_muted']};
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.01em;
    }}

    #SettingsGroupLabel {{
        color: {t['text_primary']};
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.04em;
        margin-top: 4px;
    }}

    #SettingsGroupDivider {{
        background-color: rgba(255, 255, 255, 0.08);
        min-height: 1px;
        max-height: 1px;
        border: none;
        margin: 2px 0;
    }}

    #NotebookLMStatusLabel {{
        color: {t['text_hint']};
        font-size: 11px;
        font-weight: 500;
        padding-left: 6px;
    }}

    #SettingsPrimaryButton {{
        min-height: 30px;
        padding: 0 14px;
        border-radius: {RADIUS_SCALE['pill']}px;
        color: {t['text_primary']};
        border: none;
        background-color: rgba(255, 255, 255, 0.06);
        font-weight: 600;
    }}

    #SettingsPrimaryButton:hover {{
        background-color: rgba(216, 191, 255, 0.10);
    }}

    #SettingsSecondaryButton {{
        min-height: 30px;
        padding: 0 14px;
        border-radius: {RADIUS_SCALE['pill']}px;
        font-weight: 600;
        background-color: rgba(255, 255, 255, 0.06);
        color: {t['text_secondary']};
        border: none;
    }}

    #SettingsSecondaryButton:hover {{
        background-color: rgba(216, 191, 255, 0.10);
        color: {t['text_primary']};
    }}

    #SettingsBrowseButton,
    #SettingsActionButton {{
        min-height: 30px;
        padding: 0 12px;
        border-radius: {RADIUS_SCALE['pill']}px;
        font-weight: 600;
        background-color: rgba(255, 255, 255, 0.06);
        color: {t['text_secondary']};
        border: none;
    }}

    #SettingsBrowseButton:hover,
    #SettingsActionButton:hover {{
        background-color: rgba(216, 191, 255, 0.10);
        color: {t['text_primary']};
    }}

    #TopHeaderBar {{
        background-color: {t['bg_app']};
        border-bottom: 1px solid rgba(216, 191, 255, 0.1);
    }}

    #TopNavBrandContainer {{
        background: transparent;
        border: none;
    }}

    #TopNavLogoFrame {{
        background: transparent;
        border: none;
    }}

    #TopNavLogo {{
        color: {t['text_primary']};
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.05em;
    }}

    #TopNavRail {{
        background: transparent;
        border: none;
        border-radius: {RADIUS_SCALE['pill']}px;
    }}

    #TopNavUtilityStrip {{
        background: transparent;
        border: none;
    }}

    #TopNavTitle {{
        color: {t['text_primary']};
        font-size: 14px;
        font-weight: 800;
        letter-spacing: 1px;
    }}

    #TopNavButton,
    #TopNavUtilityButton {{
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        border-radius: {RADIUS_SCALE['pill']}px;
        color: {t['text_muted']};
        font-size: 12px;
        font-weight: 600;
        min-height: {SPACING_EXTENDED['button_height_small']}px;
        max-height: {SPACING_EXTENDED['button_height_small']}px;
        padding: 0 20px;
    }}

    #TopNavButton:hover,
    #TopNavUtilityButton:hover {{
        color: {t['text_primary']};
        background-color: rgba(216, 191, 255, 0.1);
    }}

    #TopNavButton:checked {{
        color: {t['text_primary']};
        border: none;
        background-color: rgba(216, 191, 255, 0.12);
    }}

    #TopNavButton:focus,
    #TopNavUtilityButton:focus {{
        color: {t['text_primary']};
    }}

    #TopNavButton:pressed,
    #TopNavUtilityButton:pressed {{
        background-color: rgba(216, 191, 255, 0.12);
    }}

    #PipelineHeadline {{
        font-size: 32px;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: {t['text_primary']};
        margin-top: 32px;
    }}

    #PipelineSubHeadline {{
        font-size: 14px;
        color: {t['text_muted']};
        line-height: 1.4;
        margin-top: 8px;
    }}

    #PipelineStatus,
    #VaultPathLabel,
    #PipelineCollectionInfo,
    #PipelineCollectionMeta,
    #PipelineSyncChipSubtitle,
    #FeatureCardDescription {{
        color: {t['text_hint']};
        font-size: 11px;
    }}

    #PipelineSectionHeader {{
        color: {t['text_muted']};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}

    #PipelineStatusBadge {{
        min-height: 24px;
        border-radius: {RADIUS_SCALE['pill']}px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        border: 0.5px solid {t['border']};
        background-color: transparent;
        color: {t['text_muted']};
    }}

    #PanelHeader,
    #FeatureCardTitle,
    #PipelineCollectionName,
    #PipelineHeader,
    #PipelineSyncChipTitle,
    #SourceCardTitle {{
        color: {t['text_primary']};
        font-weight: 700;
    }}

    #FeatureCard,
    #PipelineCollectionCard,
    #PipelineSyncChip,
    #SourceCard,
    #PipelinePanel,
    QDialog {{
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
        padding: 0;
    }}

    QMenu,
    QToolTip,
    QListWidget,
    QTableWidget,
    QTreeWidget,
    QHeaderView::section {{
        background-color: rgba(26, 14, 46, 0.95);
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
    }}

    QMenu {{
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }}

    QTreeWidget,
    QListWidget,
    QTableWidget {{
        background-color: rgba(255, 255, 255, 0.06);
        alternate-background-color: rgba(255, 255, 255, 0.02);
    }}

    QTreeWidget::item:hover,
    QListWidget::item:hover,
    QTableWidget::item:hover {{
        background-color: rgba(216, 191, 255, 0.08);
    }}

    QTreeWidget::item:selected,
    QListWidget::item:selected,
    QTableWidget::item:selected {{
        background-color: rgba(216, 191, 255, 0.12);
        color: {t['text_primary']};
    }}

    QToolTip {{
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }}

    QDialog#SettingsDialog QLineEdit {{
        min-height: 28px;
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        border-radius: {RADIUS_SCALE['input']}px;
        padding: 6px 10px;
        color: {t['text_secondary']};
        selection-background-color: rgba(216, 191, 255, 0.12);
        selection-color: {t['selection_fg']};
    }}

    QDialog#SettingsDialog QLineEdit:focus {{
        border: none;
        background-color: rgba(216, 191, 255, 0.12);
        color: {t['text_primary']};
    }}

    QDialog#SettingsDialog QPushButton {{
        min-height: 30px;
    }}

    #PipelineLeftColumn,
    #PipelineRightColumn {{
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
        padding: 16px;
        border: 1px solid rgba(216, 191, 255, 0.05);
    }}

    #PipelineCollectionDropdown {{
        border-radius: {RADIUS_SCALE['panel']}px;
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        min-height: {SPACING_EXTENDED['button_height_medium']}px;
    }}

    #PipelineSourcesList {{
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
        background-color: rgba(255, 255, 255, 0.06);
        padding: 6px;
        min-height: {SPACING_EXTENDED['button_height_medium']}px;
    }}

    #PipelineCreateCollectionButton {{
        min-height: {SPACING_EXTENDED['button_height_medium']}px;
        border-radius: {RADIUS_SCALE['pill']}px;
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        color: {t['text_primary']};
        font-weight: 600;
        padding: 0 20px;
    }}

    #PipelineCreateCollectionButton:hover {{
        background-color: rgba(216, 191, 255, 0.10);
    }}

    #PipelineSourcesList::item {{
        padding: 8px 10px;
        border-radius: 0;
        margin: 2px 0;
    }}

    #PipelineSourcesList::item:hover {{
        background-color: rgba(216, 191, 255, 0.08);
        color: {t['text_primary']};
        border-radius: 4px;
    }}

    #PipelineSourcesList::item:selected {{
        background-color: rgba(216, 191, 255, 0.12);
        color: {t['text_primary']};
        border-radius: 4px;
    }}

    #NotesWorkspaceShell {{
        background: {t['bg_app']};
    }}

    #NotesMainSplitter::handle {{
        background: rgba(216, 191, 255, 0.04);
        width: 2px;
    }}

    #NotesMainSplitter::handle:hover {{
        background: rgba(216, 191, 255, 0.1);
    }}

    #FeatureCard:hover,
    #PipelineCollectionCard:selected {{
        border-color: {t['accent_primary']};
    }}

    #FeatureCardIcon,
    #PipelineCollectionDot[isSyncing="true"] {{
        color: {t['accent_primary']};
    }}

    #PipelineCollectionDot,
    #PipelineCollectionDot[isSyncing="false"] {{
        color: {t['text_hint']};
    }}

    QPushButton {{
        background-color: rgba(255, 255, 255, 0.06);
        color: {t['text_secondary']};
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
        padding: 9px 16px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        color: {t['text_primary']};
        background-color: rgba(216, 191, 255, 0.10);
    }}

    QPushButton:pressed,
    QPushButton:checked {{
        background-color: rgba(216, 191, 255, 0.12);
        color: {t['text_primary']};
    }}

    QPushButton:focus {{
        color: {t['text_primary']};
    }}

    QPushButton:disabled {{
        background: rgba(255, 255, 255, 0.02);
        color: {t['text_hint']};
    }}

    #PipelineStartButton {{
        min-height: {SPACING_EXTENDED['button_height_large']}px;
        max-height: {SPACING_EXTENDED['button_height_large']}px;
        font-size: 15px;
        font-weight: 600;
        border-radius: {RADIUS_SCALE['pill']}px;
        color: {t['text_primary']};
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        padding: 0 24px;
    }}

    #PipelineStartButton:hover {{
        background-color: rgba(216, 191, 255, 0.10);
    }}

    #PipelineScrollArea {{
        background: {t['bg_app']};
        border: none;
    }}

    QLineEdit,
    QComboBox,
    QPlainTextEdit,
    QTextEdit,
    QSpinBox,
    QDoubleSpinBox {{
        background-color: rgba(255, 255, 255, 0.06);
        color: {t['text_secondary']};
        border: none;
        border-radius: {RADIUS_SCALE['input']}px;
        padding: 8px 12px;
        selection-background-color: rgba(216, 191, 255, 0.12);
        selection-color: {t['selection_fg']};
        min-height: {SPACING_EXTENDED['button_height_medium']}px;
    }}

    QLineEdit:focus,
    QComboBox:focus,
    QTextEdit:focus,
    QPlainTextEdit:focus,
    QSpinBox:focus,
    QDoubleSpinBox:focus {{
        border: none;
        background-color: rgba(216, 191, 255, 0.12);
        color: {t['text_primary']};
    }}

    QSpinBox::up-button,
    QSpinBox::down-button,
    QDoubleSpinBox::up-button,
    QDoubleSpinBox::down-button {{
        background-color: rgba(255, 255, 255, 0.04);
        border: none;
        border-radius: 0;
        width: 24px;
    }}

    QSpinBox::up-button:hover,
    QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover,
    QDoubleSpinBox::down-button:hover {{
        background-color: rgba(216, 191, 255, 0.08);
    }}

    QComboBox QAbstractItemView {{
        background-color: rgba(26, 14, 46, 0.95);
        color: {t['text_secondary']};
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
        selection-background-color: rgba(216, 191, 255, 0.12);
        selection-color: {t['text_primary']};
    }}

    QComboBox QAbstractItemView::item:hover {{
        background-color: rgba(216, 191, 255, 0.08);
    }}

    QComboBox QAbstractItemView::item:selected {{
        background-color: rgba(216, 191, 255, 0.12);
    }}

    QProgressBar,
    #PipelineProgressBar {{
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        border-radius: {RADIUS_SCALE['input']}px;
        text-align: center;
        min-height: 4px;
        color: {t['text_primary']};
    }}

    QProgressBar::chunk,
    #PipelineProgressBar::chunk {{
        border-radius: {RADIUS_SCALE['input']}px;
        background-color: rgba(216, 191, 255, 0.12);
    }}

    QAbstractItemView {{
        outline: none;
        selection-background-color: rgba(216, 191, 255, 0.12);
        selection-color: {t['text_primary']};
        alternate-background-color: rgba(255, 255, 255, 0.02);
        gridline-color: {t['border_soft']};
    }}

    QAbstractItemView::item {{
        padding: 4px 8px;
        border-radius: {RADIUS_SCALE['input']}px;
    }}

    QAbstractItemView::item:hover {{
        background-color: rgba(216, 191, 255, 0.08);
    }}

    QAbstractItemView::item:selected {{
        background-color: rgba(216, 191, 255, 0.12);
    }}

    QHeaderView::section {{
        color: {t['text_muted']};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
    }}

    QToolTip {{
        color: {t['text_primary']};
        padding: 8px 10px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    }}

    QScrollBar:vertical,
    QScrollBar:horizontal {{
        background: {t['bg_app']};
        border: none;
        margin: 0;
    }}

    QScrollBar:vertical {{
        width: 8px;
    }}

    QScrollBar:horizontal {{
        height: 8px;
    }}

    QScrollBar::handle:vertical,
    QScrollBar::handle:horizontal {{
        background: rgba(255, 255, 255, 0.06);
        min-height: 24px;
        min-width: 24px;
        border-radius: 16px;
    }}

    QScrollBar::handle:vertical:hover,
    QScrollBar::handle:horizontal:hover {{
        background: rgba(216, 191, 255, 0.10);
    }}

    QScrollBar::add-line,
    QScrollBar::sub-line,
    QScrollBar::up-arrow,
    QScrollBar::down-arrow,
    QScrollBar::left-arrow,
    QScrollBar::right-arrow,
    QScrollBar::add-page,
    QScrollBar::sub-page {{
        background: transparent;
        width: 0;
        height: 0;
    }}

    #BrainMapLegend {{
        background-color: rgba(255, 255, 255, 0.06);
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
        padding: 12px 16px;
    }}

    #BrainMapLegendTitle {{
        color: {t['text_muted']};
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}

    #BrainMapLegendLabel {{
        color: {t['text_secondary']};
        font-size: 12px;
    }}

    QCheckBox,
    QRadioButton {{
        color: {t['text_secondary']};
        spacing: 8px;
    }}

    QCheckBox::indicator,
    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border-radius: {RADIUS_SCALE['input']}px;
        background-color: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(216, 191, 255, 0.1);
    }}

    QCheckBox::indicator:hover,
    QRadioButton::indicator:hover {{
        background-color: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(216, 191, 255, 0.15);
    }}

    QCheckBox::indicator:checked,
    QRadioButton::indicator:checked {{
        background-color: rgba(216, 191, 255, 0.12);
        border: 1px solid rgba(216, 191, 255, 0.18);
    }}

    QGroupBox {{
        color: {t['text_secondary']};
        border: 1px solid rgba(216, 191, 255, 0.05);
        border-radius: {RADIUS_SCALE['panel']}px;
        padding-top: 12px;
        margin-top: 12px;
        padding: 12px 16px;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 4px;
        color: {t['text_primary']};
        font-weight: 600;
    }}

    QTabWidget::pane {{
        border: 1px solid rgba(216, 191, 255, 0.05);
        background-color: {t['bg_app']};
    }}

    QTabBar::tab {{
        background-color: rgba(255, 255, 255, 0.06);
        color: {t['text_muted']};
        padding: 8px 16px;
        border: none;
        border-radius: {RADIUS_SCALE['panel']}px;
        margin-right: 2px;
    }}

    QTabBar::tab:hover {{
        background-color: rgba(216, 191, 255, 0.08);
        color: {t['text_secondary']};
    }}

    QTabBar::tab:selected {{
        background-color: rgba(216, 191, 255, 0.12);
        color: {t['text_primary']};
        border-bottom: 2px solid rgba(216, 191, 255, 0.18);
    }}

    QSlider::groove:horizontal {{
        background-color: rgba(255, 255, 255, 0.06);
        height: 4px;
        border-radius: 2px;
        margin: 0;
    }}

    QSlider::handle:horizontal {{
        background-color: rgba(216, 191, 255, 0.12);
        width: 16px;
        margin: -6px 0;
        border-radius: 8px;
    }}

    QSlider::handle:horizontal:hover {{
        background-color: rgba(216, 191, 255, 0.16);
    }}
    """


APP_STYLESHEET = get_app_stylesheet()


def note_reader_browser_qss() -> str:
    t = THEME_TOKENS
    return (
        "/* theme-harmonized */"
        "QTextBrowser {"
        f"background-color: rgba(255, 255, 255, 0.06); color: {t['text_secondary']}; border: none;"
        "font-family: 'Segoe UI', 'Inter', 'SF Pro Display';"
        "font-size: 16px; line-height: 2.0; padding: 32px 40px; }"
        "QTextBrowser::selection {"
        f"background-color: {t['selection_bg']}; color: {t['selection_fg']};"
        "}"
    )


def note_reader_document_qss() -> str:
    t = THEME_TOKENS
    return (
        "/* theme-harmonized */"
        f"body {{ color: {t['text_secondary']}; background: rgba(255, 255, 255, 0.06); font-size: 16px; line-height: 2.0; }}"
        f"h1 {{ font-size: 38px; color: {t['text_primary']}; margin-top: 40px; margin-bottom: 32px; font-weight: 800; letter-spacing: -0.04em; padding-bottom: 12px; border-bottom: 2px solid {t['border_strong']}; }}"
        f"h2 {{ font-size: 28px; color: {t['text_secondary']}; margin-top: 40px; margin-bottom: 28px; font-weight: 750; letter-spacing: -0.025em; padding-bottom: 8px; border-bottom: 1px solid {t['border']}; }}"
        f"h3 {{ font-size: 22px; color: {t['text_secondary']}; margin-top: 32px; margin-bottom: 22px; font-weight: 720; letter-spacing: -0.01em; }}"
        f"h4 {{ font-size: 18px; color: {t['text_secondary']}; margin-top: 28px; margin-bottom: 16px; font-weight: 700; }}"
        f"p {{ margin-top: 32px; margin-bottom: 32px; color: {t['text_secondary']}; }}"
        "ul, ol { margin-top: 14px; margin-bottom: 28px; padding-left: 36px; }"
        "ul > li, ol > li { margin-top: 12px; margin-bottom: 14px; }"
        f"li {{ line-height: 1.9; color: {t['text_secondary']}; }}"
        "li > p { margin-top: 0; margin-bottom: 14px; }"
        f"a {{ color: {t['accent_primary']}; text-decoration: underline; font-weight: 500; }}"
        "a:hover { color: #EAD9FF; text-decoration: underline; }"
        f"strong {{ color: {t['text_primary']}; font-weight: 750; }}"
        f"code {{ background: rgba(255, 255, 255, 0.06); color: {t['text_primary']}; padding: 3px 7px; border-radius: 12px; border: 1px solid rgba(216, 191, 255, 0.10); font-family: 'JetBrains Mono', 'Fira Code', 'Courier New'; font-size: 14px; }}"
        f"pre {{ background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(216, 191, 255, 0.10); border-radius: 16px; padding: 18px 20px; margin: 28px 0; font-family: 'JetBrains Mono', 'Fira Code', 'Courier New'; line-height: 1.7; }}"
        f"pre code {{ background: transparent; border: none; padding: 0; color: {t['text_secondary']}; font-size: 14px; }}"
        f"blockquote {{ border-left: 4px solid rgba(216, 191, 255, 0.18); margin: 28px 0; padding: 14px 20px; background: rgba(255, 255, 255, 0.06); color: {t['text_secondary']}; border-radius: 16px; font-style: italic; line-height: 1.95; }}"
        f"hr {{ border: none; border-top: 1px solid {t['border']}; margin: 36px 0; }}"
        "table { border-collapse: collapse; margin: 28px 0; width: 100%; }"
        f"th, td {{ border: 1px solid {t['border']}; padding: 12px 14px; vertical-align: top; text-align: left; }}"
        f"th {{ background: rgba(255, 255, 255, 0.06); color: {t['text_primary']}; font-weight: 750; }}"
        f"td {{ color: {t['text_secondary']}; }}"
    )


def note_reader_panel_qss() -> str:
    t = THEME_TOKENS
    return (
        "/* theme-harmonized */"
        f"#NoteReaderPanel {{ background-color: rgba(255, 255, 255, 0.06); border-left: none; border-radius: {RADIUS_SCALE['panel']}px; }}"
        f"#NoteReaderHeader {{ background-color: rgba(255, 255, 255, 0.06); border-bottom: none; border-radius: {RADIUS_SCALE['panel']}px; }}"
        "QLineEdit#NoteResearchBar {"
        f"background-color: rgba(255, 255, 255, 0.06); color: {t['text_secondary']}; border: none;"
        f"border-radius: {RADIUS_SCALE['pill']}px; padding: 0 12px;"
        f"selection-background-color: {t['selection_bg']}; selection-color: {t['selection_fg']};"
        f"min-height: {SPACING_EXTENDED['button_height_small']}px; max-height: {SPACING_EXTENDED['button_height_small']}px;"
        "}"
        f"QLineEdit#NoteResearchBar:focus {{ background-color: rgba(216, 191, 255, 0.12); color: {t['text_primary']}; }}"
        f"QLineEdit#NoteResearchBar:disabled {{ color: {t['text_hint']}; background-color: rgba(255, 255, 255, 0.02); }}"
        f"QLineEdit#NoteResearchBar::placeholder {{ color: {t['text_hint']}; }}"
        "#NoteReaderNavButton {"
        f"background-color: rgba(255, 255, 255, 0.06); color: {t['text_secondary']}; border: none;"
        f"padding: 0 12px; border-radius: {RADIUS_SCALE['pill']}px; font-size: 11px; font-weight: 600; "
        f"min-height: {SPACING_EXTENDED['button_height_small']}px; max-height: {SPACING_EXTENDED['button_height_small']}px; }}"
        f"#NoteReaderNavButton:hover {{ background-color: rgba(216, 191, 255, 0.10); color: {t['text_primary']}; }}"
        f"#NoteReaderNavButton:disabled {{ color: {t['text_hint']}; background-color: rgba(255, 255, 255, 0.02); }}"
        f"#NoteReaderPlaceholder {{ background-color: rgba(255, 255, 255, 0.06); border-radius: {RADIUS_SCALE['panel']}px; }}"
        f"#NoteReaderPlaceholderLabel {{ color: {t['text_hint']}; font-size: 14px; }}"
    )


def vault_tree_panel_qss() -> str:
    t = THEME_TOKENS
    return (
        "/* theme-harmonized */"
        f"#VaultTreePanel {{ background-color: rgba(255, 255, 255, 0.06); border-right: none; border-radius: {RADIUS_SCALE['panel']}px; }}"
        f"#VaultTreeHeader {{ background-color: rgba(255, 255, 255, 0.06); border-bottom: none; border-radius: {RADIUS_SCALE['panel']}px; }}"
        "QLineEdit#VaultResearchBar {"
        f"background-color: rgba(255, 255, 255, 0.06); color: {t['text_secondary']}; border: none;"
        f"border-radius: {RADIUS_SCALE['pill']}px; padding: 0 12px;"
        f"selection-background-color: {t['selection_bg']}; selection-color: {t['selection_fg']};"
        f"min-height: {SPACING_EXTENDED['button_height_small']}px; max-height: {SPACING_EXTENDED['button_height_small']}px;"
        "}"
        f"QLineEdit#VaultResearchBar:focus {{ background-color: rgba(216, 191, 255, 0.12); color: {t['text_primary']}; }}"
        f"QLineEdit#VaultResearchBar::placeholder {{ color: {t['text_hint']}; }}"
        "QTreeWidget#VaultTreeWidget {"
        f"background-color: rgba(255, 255, 255, 0.06);"
        f"color: {t['text_secondary']};"
        "border: none;"
        "outline: none;"
        "padding: 8px 8px 12px 6px;"
        "show-decoration-selected: 1;"
        "}"
        "QTreeWidget#VaultTreeWidget::item {"
        "height: 28px;"
        "padding-left: 8px;"
        "padding-right: 10px;"
        "border-left: none;"
        f"border-radius: {RADIUS_SCALE['sidebar']}px;"
        "margin: 2px 4px;"
        "}"
        "QTreeWidget#VaultTreeWidget::item:hover {"
        "background-color: rgba(216, 191, 255, 0.08);"
        f"color: {t['text_primary']};"
        "}"
        "QTreeWidget#VaultTreeWidget::item:selected {"
        "background-color: rgba(216, 191, 255, 0.12);"
        f"border-left: none;"
        f"color: {t['text_primary']};"
        "}"
        "QTreeWidget#VaultTreeWidget::item:selected:active {"
        "background-color: rgba(216, 191, 255, 0.14);"
        "}"
        "QTreeWidget#VaultTreeWidget:focus { border: none; }"
    )


def pipeline_status_badge_qss(active: bool) -> str:
    t = THEME_TOKENS
    if active:
        return (
            "/* theme-harmonized */"
            f"background-color: rgba(216, 191, 255, 0.12);"
            f"color: {t['text_primary']};"
            f"border: none;"
            "padding: 4px 10px;"
            f"border-radius: {RADIUS_SCALE['pill']}px;"
            "font-weight: 600;"
        )
    return (
        "/* theme-harmonized */"
        f"background-color: rgba(255, 255, 255, 0.06);"
        f"color: {t['text_muted']};"
        f"border: none;"
        "padding: 4px 10px;"
        f"border-radius: {RADIUS_SCALE['pill']}px;"
        "font-weight: 600;"
    )
