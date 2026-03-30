from __future__ import annotations

from typing import Any

import networkx as nx
import numpy as np
import pyqtgraph.opengl as gl
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QMatrix4x4, QVector4D
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QVBoxLayout,
    QWidget,
)


class ClickableGLView(gl.GLViewWidget):
    clicked = pyqtSignal(QPoint)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(event.position().toPoint())
        super().mousePressEvent(event)


class Graph3DView(QWidget):
    node_selected = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.gl_view = ClickableGLView()
        self.gl_view.opts["distance"] = 14
        self.gl_view.clicked.connect(self._handle_click)
        self.gl_view.setBackgroundColor((14, 14, 18, 255))

        self.grid = gl.GLGridItem()
        self.grid.setSize(14, 14)
        self.grid.setSpacing(1, 1)
        self.gl_view.addItem(self.grid)

        self.scatter_item: gl.GLScatterPlotItem | None = None
        self.edge_items: list[gl.GLLinePlotItem] = []

        self.drawer = QFrame()
        self.drawer.setObjectName("NodeDrawer")
        self.drawer.setMinimumWidth(260)
        self.drawer.setMaximumWidth(300)

        drawer_layout = QVBoxLayout(self.drawer)
        self.drawer_title = QLabel("Node Inspector")
        self.drawer_summary = QLabel("Click a node to inspect details")
        self.drawer_summary.setWordWrap(True)
        self.drawer_connections = QListWidget()

        drawer_layout.addWidget(self.drawer_title)
        drawer_layout.addWidget(self.drawer_summary)
        drawer_layout.addWidget(QLabel("Connected Nodes"))
        drawer_layout.addWidget(self.drawer_connections)

        layout.addWidget(self.gl_view, 1)
        layout.addWidget(self.drawer)

        self.graph_payload: dict[str, Any] = {"nodes": [], "edges": []}
        self.node_positions: dict[str, np.ndarray] = {}
        self.node_index_map: dict[int, str] = {}

    def set_graph_data(self, graph_payload: dict[str, Any]) -> None:
        self.graph_payload = graph_payload
        self.node_positions = {}
        self.node_index_map = {}

        for edge in self.edge_items:
            self.gl_view.removeItem(edge)
        self.edge_items.clear()

        if self.scatter_item is not None:
            self.gl_view.removeItem(self.scatter_item)
            self.scatter_item = None

        graph = nx.Graph()
        nodes = graph_payload.get("nodes", [])
        edges = graph_payload.get("edges", [])

        for node in nodes:
            graph.add_node(str(node.get("id")))

        for edge in edges:
            source = str(edge.get("source"))
            target = str(edge.get("target"))
            if source and target:
                graph.add_edge(source, target)

        if graph.number_of_nodes() == 0:
            return

        positions = nx.spring_layout(graph, dim=3, seed=42, k=0.9)

        scatter_positions = []
        scatter_colors = []
        scatter_sizes = []

        for index, node in enumerate(nodes):
            node_id = str(node.get("id"))
            point = np.array(positions.get(node_id, np.random.rand(3) - 0.5), dtype=float) * 8.0
            self.node_positions[node_id] = point
            self.node_index_map[index] = node_id

            scatter_positions.append(point)
            color = node.get("color", (0.7, 0.7, 0.7, 1.0))
            scatter_colors.append(color)
            degree = int(node.get("degree", 1))
            scatter_sizes.append(float(8 + min(degree, 8) * 1.5))

        self.scatter_item = gl.GLScatterPlotItem(
            pos=np.array(scatter_positions),
            color=np.array(scatter_colors, dtype=float),
            size=np.array(scatter_sizes, dtype=float),
            pxMode=False,
        )
        self.gl_view.addItem(self.scatter_item)

        for edge in edges:
            source = str(edge.get("source"))
            target = str(edge.get("target"))
            if source in self.node_positions and target in self.node_positions:
                line = gl.GLLinePlotItem(
                    pos=np.array([self.node_positions[source], self.node_positions[target]], dtype=float),
                    color=(0.75, 0.72, 0.92, 0.50),
                    width=1.0,
                    antialias=True,
                )
                self.edge_items.append(line)
                self.gl_view.addItem(line)

    def _handle_click(self, point: QPoint) -> None:
        node_id = self._pick_node(point.x(), point.y())
        if not node_id:
            return

        nodes = {str(node.get("id")): node for node in self.graph_payload.get("nodes", [])}
        node = nodes.get(node_id)
        if not node:
            return

        connected = []
        for edge in self.graph_payload.get("edges", []):
            source = str(edge.get("source"))
            target = str(edge.get("target"))
            if source == node_id and target in nodes:
                connected.append(nodes[target].get("label", target))
            elif target == node_id and source in nodes:
                connected.append(nodes[source].get("label", source))

        self.drawer_title.setText(str(node.get("label", "Node")))
        self.drawer_summary.setText(str(node.get("summary", "No summary available")) or "No summary available")
        self.drawer_connections.clear()
        self.drawer_connections.addItems(sorted(set(connected)))

        payload = {
            **node,
            "connected": sorted(set(connected)),
        }
        self.node_selected.emit(payload)

    def _pick_node(self, click_x: int, click_y: int) -> str | None:
        if not self.node_positions:
            return None

        width = max(1, self.gl_view.width())
        height = max(1, self.gl_view.height())

        projection_matrix: QMatrix4x4 = self.gl_view.projectionMatrix()
        view_matrix: QMatrix4x4 = self.gl_view.viewMatrix()

        closest_node = None
        closest_distance = float("inf")

        for node_id, position in self.node_positions.items():
            vector = QVector4D(float(position[0]), float(position[1]), float(position[2]), 1.0)
            clip = projection_matrix * view_matrix * vector
            if abs(clip.w()) < 1e-8:
                continue
            ndc_x = clip.x() / clip.w()
            ndc_y = clip.y() / clip.w()

            screen_x = int((ndc_x + 1.0) * 0.5 * width)
            screen_y = int((1.0 - ndc_y) * 0.5 * height)
            distance = float(np.hypot(screen_x - click_x, screen_y - click_y))

            if distance < closest_distance:
                closest_distance = distance
                closest_node = node_id

        if closest_distance <= 24:
            return closest_node
        return None
