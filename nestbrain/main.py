from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from nestbrain.core.pipeline_runner import ensure_config, load_config
from nestbrain.ui.main_window import MainWindow


def main() -> int:
    app_root = Path(__file__).resolve().parent
    config_path = ensure_config(app_root)
    config = load_config(config_path)

    app = QApplication(sys.argv)
    app.setApplicationName("Nestbrain")
    app.setOrganizationName("Nestbrain")

    window = MainWindow(app_root=app_root, config_path=config_path, config=config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
