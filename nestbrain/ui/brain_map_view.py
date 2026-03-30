from __future__ import annotations

from typing import Any

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import networkx as nx
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget


class BrainMapView(QWidget):
    node_selected = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.graph = nx.Graph()
        self.positions: dict[str, tuple[float, float]] = {}
        self.node_data: dict[str, dict[str, Any]] = {}
        self.current_focus: str | None = None

        self.figure = Figure(facecolor="#111217")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.axis = self.figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self.canvas.mpl_connect("button_press_event", self._on_click)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)

        self._draw_empty_state()

    def set_graph_data(self, graph_payload: dict[str, Any]) -> None:
        self.graph.clear()
        self.node_data.clear()

        for node in graph_payload.get("nodes", []):
            node_id = str(node.get("id"))
            self.graph.add_node(node_id)
            self.node_data[node_id] = node

        for edge in graph_payload.get("edges", []):
            source = str(edge.get("source"))
            target = str(edge.get("target"))
            weight = float(edge.get("weight", 1.0))
            if source and target:
                self.graph.add_edge(source, target, weight=weight)

        if self.graph.number_of_nodes() > 0:
            self.positions = nx.spring_layout(self.graph, seed=42, k=0.45)
        else:
            self.positions = {}

        self.current_focus = None
        self._render_graph()

    def _draw_empty_state(self) -> None:
        self.axis.clear()
        self.axis.set_facecolor("#111217")
        self.axis.text(
            0.5,
            0.5,
            "Brain-Map will appear after graph generation",
            color="#B8B8C7",
            ha="center",
            va="center",
            transform=self.axis.transAxes,
            fontsize=12,
        )
        self.axis.set_xticks([])
        self.axis.set_yticks([])
        self.canvas.draw_idle()

    def _render_graph(self) -> None:
        if self.graph.number_of_nodes() == 0:
            self._draw_empty_state()
            return

        self.axis.clear()
        self.axis.set_facecolor("#111217")

        node_colors = []
        node_sizes = []
        for node_id in self.graph.nodes:
            data = self.node_data.get(node_id, {})
            node_type = data.get("type", "note")
            if node_id == self.current_focus:
                node_colors.append("#F7B267")
                node_sizes.append(270)
            elif node_type == "note":
                node_colors.append("#B08CF0")
                node_sizes.append(170)
            elif node_type == "reference":
                node_colors.append("#65C7F7")
                node_sizes.append(150)
            else:
                node_colors.append("#F1A56F")
                node_sizes.append(145)

        nx.draw_networkx_edges(self.graph, self.positions, ax=self.axis, alpha=0.35, width=1.0, edge_color="#A7A1C2")
        nx.draw_networkx_nodes(
            self.graph,
            self.positions,
            node_color=node_colors,
            node_size=node_sizes,
            ax=self.axis,
            linewidths=0.7,
            edgecolors="#1B1E2D",
        )

        if self.current_focus:
            sub_nodes = set(self.graph.neighbors(self.current_focus))
            sub_nodes.add(self.current_focus)
            subgraph = self.graph.subgraph(sub_nodes)
            nx.draw_networkx_edges(subgraph, self.positions, ax=self.axis, alpha=0.95, width=2.0, edge_color="#C9B5FF")

            labels = {
                node_id: self.node_data.get(node_id, {}).get("label", node_id)[:26]
                for node_id in subgraph.nodes
            }
            nx.draw_networkx_labels(subgraph, self.positions, labels=labels, font_size=8, font_color="#ECE9FF", ax=self.axis)

        self.axis.set_xticks([])
        self.axis.set_yticks([])
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _on_click(self, event: Any) -> None:
        if event.xdata is None or event.ydata is None or not self.positions:
            return

        closest_node = None
        closest_distance = float("inf")
        for node_id, (x_pos, y_pos) in self.positions.items():
            distance = (x_pos - event.xdata) ** 2 + (y_pos - event.ydata) ** 2
            if distance < closest_distance:
                closest_distance = distance
                closest_node = node_id

        if closest_node is None or closest_distance > 0.04:
            return

        self.current_focus = closest_node
        self._render_graph()
        payload = self.node_data.get(closest_node, {})
        payload = {
            **payload,
            "connected": [self.node_data.get(neighbor, {}).get("label", neighbor) for neighbor in self.graph.neighbors(closest_node)],
        }
        self.node_selected.emit(payload)

    def _on_scroll(self, event: Any) -> None:
        if event.xdata is None or event.ydata is None:
            return

        scale_factor = 0.8 if event.button == "up" else 1.25
        x_min, x_max = self.axis.get_xlim()
        y_min, y_max = self.axis.get_ylim()

        x_center = event.xdata
        y_center = event.ydata

        new_x_min = x_center - (x_center - x_min) * scale_factor
        new_x_max = x_center + (x_max - x_center) * scale_factor
        new_y_min = y_center - (y_center - y_min) * scale_factor
        new_y_max = y_center + (y_max - y_center) * scale_factor

        self.axis.set_xlim(new_x_min, new_x_max)
        self.axis.set_ylim(new_y_min, new_y_max)
        self.canvas.draw_idle()
