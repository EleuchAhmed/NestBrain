from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ..core.errors import build_error_payload
from ..core.pipeline_runner import PipelineConfig, PipelineRunner


class PipelineWorker(QObject):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    result = pyqtSignal(dict)
    error = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self, app_root: str | Path, config: PipelineConfig) -> None:
        super().__init__()
        self.app_root = Path(app_root)
        self.config = config

    @pyqtSlot()
    def run(self) -> None:
        try:
            runner = PipelineRunner(self.app_root)
            result = runner.run(
                config=self.config,
                progress_callback=self.progress.emit,
                status_callback=self.status.emit,
            )
            self.result.emit(result)
        except Exception as exc:
            self.error.emit(build_error_payload(exc, source="pipeline_worker"))
        finally:
            self.finished.emit()
