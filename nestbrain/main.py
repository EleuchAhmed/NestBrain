from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon
from dotenv import load_dotenv
load_dotenv()

import logging

from nestbrain.core.logging import setup_logging
from nestbrain.core.paths import get_resource_root
from nestbrain.core.pipeline_runner import ensure_config, load_config
# from nestbrain.ui.main_window import MainWindow # MOVED INSIDE main() to avoid startup crash

setup_logging()
logger = logging.getLogger(__name__)

def _qt_message_handler(msg_type: QtMsgType, context: object, message: str) -> None:
    # Suppress a known non-fatal Qt warning while keeping other diagnostics.
    if message.startswith("QFont::setPointSize: Point size <= 0"):
        return
    logger.warning(message)


def main() -> int:
    logger.info("entering main()")
    # qInstallMessageHandler(_qt_message_handler) # Temporarily disabled
    
    logger.info("resolving app_root")
    try:
        app_root = get_resource_root(Path(__file__).resolve().parent)
        logger.info("app_root resolved: %s", app_root)
        
        logger.info("checking config_path")
        config_path = ensure_config(app_root)
        logger.info("config_path: %s", config_path)
        
        logger.info("loading config")
        config = load_config(config_path)
        logger.info("config loaded successfully")

        logger.info("creating QApplication")
        app = QApplication(sys.argv)
        app.setApplicationName("Nestbrain")
        app.setOrganizationName("Nestbrain")
        app.setFont(QFont("Segoe UI", 10))
        icon_path = app_root / "assets" / "app.ico"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
        else:
            logger.warning("app icon missing: %s", icon_path)
        logger.info("QApplication ready")

        logger.info("creating MainWindow")
        from nestbrain.ui.main_window import MainWindow
        window = MainWindow(app_root=app_root, config_path=config_path, config=config)
        logger.info("MainWindow created")
        
        logger.info("showing window")
        window.show()
        logger.info("entering app.exec()")
        
        res = app.exec()
        logger.info("app.exec() returned %s", res)
        return res
    except Exception as e:
        logger.exception("main() caught exception: %s", e)
        return 1

if __name__ == "__main__":
    try:
        logger.info("Application starting...")
        exit_code = main()
        logger.info("Application exited with code %s", exit_code)
        sys.exit(exit_code)
    except Exception as e:
        logger.exception("FATAL ERROR: %s", e)
        sys.exit(1)
