from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from dotenv import load_dotenv
load_dotenv()

from nestbrain.core.pipeline_runner import ensure_config, load_config
from nestbrain.ui.main_window import MainWindow


def _qt_message_handler(msg_type: QtMsgType, context: object, message: str) -> None:
    # Suppress a known non-fatal Qt warning while keeping other diagnostics.
    if message.startswith("QFont::setPointSize: Point size <= 0"):
        return
    print(message, file=sys.stderr)


def main() -> int:
    qInstallMessageHandler(_qt_message_handler)

    app_root = Path(__file__).resolve().parent
    config_path = ensure_config(app_root)
    config = load_config(config_path)

    app = QApplication(sys.argv)
    app.setApplicationName("Nestbrain")
    app.setOrganizationName("Nestbrain")
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow(app_root=app_root, config_path=config_path, config=config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
