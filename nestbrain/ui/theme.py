from __future__ import annotations


APP_STYLESHEET = """
QWidget {
    background-color: #1a1a1a;
    color: #e0e0e0;
    font-family: "SF Pro Display", "Inter", "Segoe UI";
    font-size: 13px;
}

QMainWindow::separator {
    background: #2a2a2a;
    width: 1px;
    height: 1px;
}

QGroupBox {
    border: none;
    margin-top: 0;
    padding: 0;
}

#TopHeaderBar {
    background-color: #1a1a1a;
    border-bottom: 1px solid #2a2a2a;
}

#HeaderAppLabel {
    color: #e0e0e0;
    font-size: 14px;
    font-weight: 600;
}

#TopNavButton,
#TopNavUtilityButton {
    background: transparent;
    border: none;
}

#TopNavButton,
#TopNavUtilityButton {
    background: transparent;
    color: #888888;
    font-size: 13px;
    min-height: 34px;
    padding: 0 14px;
    border: none;
    margin-right: 8px;
}

#TopNavButton:hover,
#TopNavUtilityButton:hover {
    color: #e0e0e0;
}

#TopNavButton:checked {
    color: #e0e0e0;
    border-bottom: 2px solid #6c63ff;
}

#TopNavButton:last,
#TopNavUtilityButton:last {
    margin-right: 0;
}

QPushButton {
    background-color: #2a2a2a;
    color: #e0e0e0;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
}

QPushButton:hover {
    background-color: #333333;
}

QPushButton:pressed {
    background-color: #6c63ff;
    color: #f5f5f5;
}

QPushButton:checked {
    background-color: #6c63ff;
    color: #f5f5f5;
}

QPushButton:disabled {
    background-color: #202020;
    color: #666666;
}

#PipelineStartButton {
    min-height: 46px;
    font-weight: 600;
}

QLineEdit,
QComboBox,
QPlainTextEdit,
QTextEdit,
QSpinBox,
QDoubleSpinBox {
    background-color: #202020;
    color: #e0e0e0;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 6px 8px;
    selection-background-color: #6c63ff;
    selection-color: #f5f5f5;
}

QComboBox QAbstractItemView {
    background-color: #1f1f1f;
    color: #e0e0e0;
    border: 1px solid #2a2a2a;
    selection-background-color: #6c63ff;
    selection-color: #f5f5f5;
}

QLabel {
    background: transparent;
}

#PipelineHeadline {
    color: #e0e0e0;
    font-size: 30px;
    font-weight: 650;
}

#PipelineSubHeadline,
#PipelineStatus,
#VaultPathLabel,
#PipelineCollectionInfo,
#PipelineCollectionMeta,
#PipelineSyncChipSubtitle {
    color: #888888;
}

#PipelineSectionHeader {
    color: #888888;
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 1px;
}

#PanelHeader,
#FeatureCardTitle,
#PipelineCollectionName,
#PipelineHeader,
#PipelineSyncChipTitle {
    color: #e0e0e0;
    font-weight: 600;
}

#FeatureCard,
#PipelineCollectionCard,
#PipelineSyncChip,
#SourceCard,
QMenu,
QToolTip,
QListWidget,
QTableWidget,
QTreeWidget,
QHeaderView::section {
    background-color: #1f1f1f;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
}

#FeatureCardIcon,
#PipelineCollectionDot[isSyncing="true"] {
    color: #6c63ff;
}

#PipelineCollectionDot,
#PipelineCollectionDot[isSyncing="false"] {
    color: #888888;
}

#StatusBadge {
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}

#StatusBadge[state="active"] {
    background-color: rgba(108, 99, 255, 0.22);
    color: #e0e0e0;
}

#StatusBadge[state="inactive"] {
    background-color: #2a2a2a;
    color: #888888;
}

#PipelinePanel {
    background-color: #1f1f1f;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
}

#PipelineScrollArea {
    background: #1a1a1a;
    border: none;
}

QProgressBar {
    background-color: #202020;
    color: #e0e0e0;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    text-align: center;
    min-height: 18px;
}

QProgressBar::chunk {
    background-color: #6c63ff;
    border-radius: 5px;
}

#PipelineStartButton {
    min-height: 44px;
    max-height: 44px;
    background-color: #6c63ff;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
}

#PipelineStartButton:hover {
    background-color: #7b73ff;
}

#PipelineStartButton:pressed,
#PipelineStartButton:checked {
    background-color: #6c63ff;
}

#SourceCardTitle {
    color: #e0e0e0;
    font-weight: 600;
}

#SourceCardMeta {
    color: #888888;
    font-size: 11px;
}

QAbstractItemView {
    outline: none;
    selection-background-color: rgba(108, 99, 255, 0.35);
    selection-color: #e0e0e0;
    alternate-background-color: #1b1b1b;
    gridline-color: #2a2a2a;
}

QScrollBar:vertical,
QScrollBar:horizontal {
    background: #1a1a1a;
    border: none;
    margin: 0;
}

QScrollBar:vertical {
    width: 6px;
}

QScrollBar:horizontal {
    height: 6px;
}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {
    background: #3a3a3a;
    min-height: 20px;
    min-width: 20px;
    border-radius: 3px;
}

QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::up-arrow,
QScrollBar::down-arrow,
QScrollBar::left-arrow,
QScrollBar::right-arrow,
QScrollBar::add-page,
QScrollBar::sub-page {
    background: transparent;
    width: 0;
    height: 0;
}
"""
