from __future__ import annotations

import math
from dataclasses import dataclass
from random import Random

from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from .theme import THEME_TOKENS


@dataclass(slots=True)
class AmbientNode:
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    phase: float
    color_key: str


class AmbientNodeBackground(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AmbientNodeBackground")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(False)

        self._rng = Random(42)
        self._palette = [
            THEME_TOKENS["accent_primary"],
            THEME_TOKENS["accent_indigo"],
            THEME_TOKENS["accent_blush"],
            THEME_TOKENS["accent_deep"],
            THEME_TOKENS["border_strong"],
        ]
        self._nodes: list[AmbientNode] = self._build_nodes(18)

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def _build_nodes(self, count: int) -> list[AmbientNode]:
        nodes: list[AmbientNode] = []
        for index in range(count):
            nodes.append(
                AmbientNode(
                    x=self._rng.uniform(0.06, 0.94),
                    y=self._rng.uniform(0.08, 0.92),
                    vx=self._rng.uniform(-0.00045, 0.00045),
                    vy=self._rng.uniform(-0.00035, 0.00035),
                    radius=self._rng.uniform(2.0, 4.2),
                    phase=self._rng.uniform(0.0, 6.28318),
                    color_key=self._palette_key(index),
                )
            )
        return nodes

    def _palette_key(self, index: int) -> str:
        return self._palette[index % len(self._palette)]

    def _advance(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return

        for node in self._nodes:
            node.phase += 0.012
            node.x += node.vx + (math.sin(node.phase) * 0.00002)
            node.y += node.vy + (math.cos(node.phase * 0.9) * 0.000018)

            if node.x < 0.05:
                node.x = 0.05
                node.vx = abs(node.vx)
            elif node.x > 0.95:
                node.x = 0.95
                node.vx = -abs(node.vx)

            if node.y < 0.05:
                node.y = 0.05
                node.vy = abs(node.vy)
            elif node.y > 0.95:
                node.y = 0.95
                node.vy = -abs(node.vy)

        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)

        width = max(1.0, float(self.width()))
        height = max(1.0, float(self.height()))

        point_cache: list[QPointF] = []
        for node in self._nodes:
            x_pos = node.x * width
            y_pos = node.y * height
            point_cache.append(QPointF(x_pos, y_pos))

        for index, start in enumerate(point_cache):
            for offset in (1, 5):
                end = point_cache[(index + offset) % len(point_cache)]
                line_color = QColor(self._nodes[index].color_key)
                line_color.setAlpha(10 if offset == 1 else 5)
                painter.setPen(QPen(line_color, 1.0))
                painter.drawLine(start, end)

        for node, center in zip(self._nodes, point_cache):
            pulse = 0.35 + (0.25 * (1.0 + math.sin(node.phase)))
            outer_radius = node.radius * (2.6 + pulse)
            inner_radius = node.radius * (0.75 + (pulse * 0.2))

            glow_color = QColor(node.color_key)
            glow_color.setAlpha(10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow_color)
            painter.drawEllipse(center, outer_radius, outer_radius)

            core_color = QColor(node.color_key)
            core_color.setAlpha(36)
            painter.setBrush(core_color)
            painter.drawEllipse(center, inner_radius, inner_radius)

        painter.end()
