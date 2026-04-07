from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Any

import networkx as nx
from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)


class CategoryColorManager:
    CATEGORY_PALETTE = [
        "#6c63ff",  # purple
        "#ff6584",  # pink
        "#43b89c",  # teal
        "#f7b731",  # amber
        "#4fc3f7",  # sky blue
        "#ff7043",  # deep orange
        "#ab47bc",  # violet
        "#66bb6a",  # green
        "#ef5350",  # red
        "#26c6da",  # cyan
    ]

    def get_color(self, folder_name: str) -> QColor:
        key = (folder_name or "uncategorized").strip().lower()
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        palette_index = int(digest[:8], 16) % len(self.CATEGORY_PALETTE)
        return QColor(self.CATEGORY_PALETTE[palette_index])


class RoundedRectItem(QGraphicsRectItem):
    def __init__(self, radius: float = 6.0) -> None:
        super().__init__()
        self.radius = radius

    def paint(self, painter: QPainter, option: Any, widget: Any = None) -> None:
        painter.save()
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawRoundedRect(self.rect(), self.radius, self.radius)
        painter.restore()


class NoteEdge(QGraphicsLineItem):
    def __init__(self, source: "NoteNode", target: "NoteNode") -> None:
        super().__init__()
        self.source = source
        self.target = target

        base_color = QColor("#3a3a3a")
        base_color.setAlpha(140)
        self._base_pen = QPen(base_color, 1.0)
        self._base_pen.setCosmetic(True)

        highlight_color = QColor("#b5b5b5")
        highlight_color.setAlpha(235)
        self._highlight_pen = QPen(highlight_color, 2.1)
        self._highlight_pen.setCosmetic(True)

        self.setPen(self._base_pen)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(-1)
        self.update_position()

    def update_position(self) -> None:
        self.setLine(
            self.source.scenePos().x(),
            self.source.scenePos().y(),
            self.target.scenePos().x(),
            self.target.scenePos().y(),
        )

    def set_highlighted(self, highlighted: bool) -> None:
        self.setPen(self._highlight_pen if highlighted else self._base_pen)


class NoteNode(QGraphicsEllipseItem):
    def __init__(
        self,
        view: "BrainMapWidget",
        node_id: str,
        title: str,
        category: str,
        color: QColor,
        is_hub: bool,
        payload: dict[str, Any],
    ) -> None:
        super().__init__()
        self.view = view
        self.node_id = node_id
        self.payload = payload
        self.note_name = title
        self.category = category
        self.is_hub = is_hub

        self.base_radius = 14.0 if is_hub else 8.0
        self.hover_radius = 17.0 if is_hub else 11.0
        self.current_radius = self.base_radius

        self.category_color = QColor(color)
        self.base_fill_color = QColor(color)
        self.base_fill_color.setAlphaF(0.8)
        self.hover_fill_color = QColor(color)
        self.hover_fill_color.setAlphaF(1.0)
        self.border_color = QColor(color)
        self.border_color.setAlphaF(1.0)
        self.connected_edges: list[NoteEdge] = []
        self.velocity = QPointF(0.0, 0.0)
        self._is_dragging = False
        self._drag_offset = QPointF()
        self._drag_restore_brush = QColor(self.base_fill_color)
        self._drag_restore_z = 0.0

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        self._glow_effect = QGraphicsDropShadowEffect()
        self._glow_effect.setBlurRadius(26)
        self._glow_effect.setOffset(0, 0)
        self._glow_effect.setColor(QColor(255, 255, 255, 95))

        self.label_item = QGraphicsSimpleTextItem(self._truncate(self.note_name, 34), self)
        label_font = QFont("Segoe UI", 10)
        self.label_item.setFont(label_font)
        self.label_item.setBrush(QColor("#ffffff"))
        self.label_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.label_item.setVisible(False)

        self._apply_geometry(self.base_radius)
        self._apply_pen(selected=False)
        self.setBrush(self.base_fill_color)

    def _truncate(self, text: str, max_chars: int) -> str:
        cleaned = text.strip()
        if len(cleaned) <= max_chars:
            return cleaned
        return cleaned[: max_chars - 1] + "..."

    def add_edge(self, edge: NoteEdge) -> None:
        self.connected_edges.append(edge)

    def _apply_pen(self, selected: bool) -> None:
        if selected:
            pen = QPen(QColor("#ffffff"), 2.0)
            pen.setCosmetic(True)
            self.setPen(pen)
            self.setGraphicsEffect(self._glow_effect)
        else:
            pen = QPen(self.border_color, 1.5)
            pen.setCosmetic(True)
            self.setPen(pen)
            self.setGraphicsEffect(None)

    def _apply_geometry(self, radius: float) -> None:
        self.current_radius = radius
        self.setRect(-radius, -radius, radius * 2, radius * 2)
        self._layout_label()

    def _layout_label(self) -> None:
        rect = self.label_item.boundingRect()
        self.label_item.setPos(-rect.width() / 2.0, self.current_radius + 4)

    def set_connected_edges_hover(self, hovered: bool) -> None:
        for edge in self.connected_edges:
            edge.set_highlighted(hovered)

    def hoverEnterEvent(self, event: Any) -> None:
        self.view.set_hover_node(self)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: Any) -> None:
        self.view.clear_hover_node(self)
        super().hoverLeaveEvent(event)

    def begin_manual_drag(self, scene_pos: QPointF) -> None:
        self._is_dragging = True
        self._drag_offset = scene_pos - self.scenePos()
        self._drag_restore_z = self.zValue()
        self._drag_restore_brush = QColor(self.brush().color())

        drag_brush = QColor(self._drag_restore_brush)
        drag_brush.setAlphaF(1.0)
        self.setBrush(drag_brush)
        self.setZValue(100)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.view.begin_component_drag(self, scene_pos, self._drag_offset)

    def drag_manual_to(self, scene_pos: QPointF) -> None:
        if not self._is_dragging:
            return

        self.view.update_component_drag(scene_pos)

    def end_manual_drag(self, scene_pos: QPointF | None = None) -> None:
        if not self._is_dragging:
            return

        self.view.end_component_drag(scene_pos)

        self.setBrush(self._drag_restore_brush)
        self.setZValue(self._drag_restore_z)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._is_dragging = False
        self._drag_offset = QPointF()

        if self.view.tooltip_visible_for is self:
            self.view.show_tooltip_for_node(self)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin_manual_drag(event.scenePos())
            self.grabMouse()
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self._is_dragging:
            self.drag_manual_to(event.scenePos())

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        if self._is_dragging and event.button() == Qt.MouseButton.LeftButton:
            self.end_manual_drag(event.scenePos())
            self.ungrabMouse()

            event.accept()
            return

        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self.view.node_double_clicked.emit(self.note_name)
        super().mouseDoubleClickEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.connected_edges:
                edge.update_position()
            if self.view.tooltip_visible_for is self:
                self.view.show_tooltip_for_node(self)

        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._apply_pen(bool(value))

        return super().itemChange(change, value)


class BrainMapWidget(QGraphicsView):
    node_double_clicked = pyqtSignal(str)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)

        self.graph = nx.Graph()
        self.node_items: dict[str, NoteNode] = {}
        self.edge_items: list[NoteEdge] = []
        self._adjacency: dict[str, set[str]] = {}
        self._component_cache: dict[str, set[str]] = {}
        self.color_manager = CategoryColorManager()

        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(QRectF(-1000, -1000, 2000, 2000))
        self.setScene(self.scene)

        self.setBackgroundBrush(QColor("#141414"))
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 3.0

        self._panning = False
        self._pan_last_pos = QPoint()
        self._active_drag_node: NoteNode | None = None
        self._active_drag_anchor_offset = QPointF()
        self._active_drag_component_ids: set[str] = set()
        self._active_drag_direct_ids: set[str] = set()
        self._active_drag_second_degree_ids: set[str] = set()
        self._active_drag_direct_rest_lengths: dict[str, float] = {}
        self._active_drag_second_rest_lengths: dict[str, float] = {}
        self._hovered_node: NoteNode | None = None
        self.tooltip_visible_for: NoteNode | None = None

        self._tooltip_bg: RoundedRectItem | None = None
        self._tooltip_title: QGraphicsSimpleTextItem | None = None
        self._tooltip_meta: QGraphicsSimpleTextItem | None = None
        self._empty_label: QGraphicsSimpleTextItem | None = None
        self._legend_bg: RoundedRectItem | None = None

        self._repulsion_threshold = 120.0
        self._repulsion_constant = 1800.0
        self._damping = 0.85
        self._max_speed = 14.0
        self._direct_spring_stiffness = 0.07
        self._second_spring_stiffness = 0.03
        self._second_degree_damping_scale = 0.8

        self._physics_timer = QTimer(self)
        self._physics_timer.setInterval(16)
        self._physics_timer.timeout.connect(self._physics_step)
        self._physics_timer.start()

        self._init_overlay_items()

    def _init_overlay_items(self) -> None:
        self._tooltip_bg = RoundedRectItem(radius=6.0)
        self._tooltip_bg.setBrush(QColor(20, 20, 20, 220))
        self._tooltip_bg.setPen(QPen(QColor("#2a2a2a"), 1.0))
        self._tooltip_bg.setZValue(1000)

        self._tooltip_title = QGraphicsSimpleTextItem(self._tooltip_bg)
        self._tooltip_meta = QGraphicsSimpleTextItem(self._tooltip_bg)

        title_font = QFont("Segoe UI", 10)
        title_font.setWeight(QFont.Weight.Medium)
        self._tooltip_title.setFont(title_font)
        self._tooltip_title.setBrush(QColor("#ffffff"))

        meta_font = QFont("Segoe UI", 9)
        self._tooltip_meta.setFont(meta_font)
        self._tooltip_meta.setBrush(QColor("#bbbbbb"))

        self.scene.addItem(self._tooltip_bg)
        self._tooltip_bg.hide()

        self._empty_label = QGraphicsSimpleTextItem("Neural Map will appear after pipeline execution")
        empty_font = QFont("Segoe UI", 11)
        self._empty_label.setFont(empty_font)
        self._empty_label.setBrush(QColor("#888888"))
        self._empty_label.setZValue(10)
        self.scene.addItem(self._empty_label)
        self._center_empty_label()

    def _center_empty_label(self) -> None:
        if self._empty_label is None:
            return
        br = self._empty_label.boundingRect()
        self._empty_label.setPos(-br.width() / 2.0, -br.height() / 2.0)

    def set_graph_data(self, graph_payload: dict[str, Any]) -> None:
        self.resetTransform()
        self._zoom = 1.0
        self.hide_tooltip()

        self.graph.clear()
        self.node_items.clear()
        self.edge_items.clear()
        self._adjacency.clear()
        self._component_cache.clear()
        self._active_drag_node = None
        self._active_drag_component_ids.clear()
        self._active_drag_direct_ids.clear()
        self._active_drag_second_degree_ids.clear()
        self._active_drag_direct_rest_lengths.clear()
        self._active_drag_second_rest_lengths.clear()
        self._hovered_node = None

        self.scene.clear()
        self._init_overlay_items()

        node_data: dict[str, dict[str, Any]] = {}
        note_ids: set[str] = set()

        for node in graph_payload.get("nodes", []):
            node_id = str(node.get("id") or "")
            if not node_id:
                continue
            node_type = str(node.get("type") or "")
            if node_type != "note":
                continue
            node_data[node_id] = node
            note_ids.add(node_id)
            self.graph.add_node(node_id)

        for edge in graph_payload.get("edges", []):
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            reason = str(edge.get("reason") or "").lower()
            if source in note_ids and target in note_ids and "wikilink" in reason:
                self.graph.add_edge(source, target)

        self._adjacency = {node_id: set() for node_id in self.graph.nodes}
        for source, target in self.graph.edges:
            self._adjacency[source].add(target)
            self._adjacency[target].add(source)

        self._component_cache = {}
        for component in nx.connected_components(self.graph):
            component_set = set(component)
            for node_id in component_set:
                self._component_cache[node_id] = component_set

        if self.graph.number_of_nodes() == 0:
            if self._empty_label is not None:
                self._empty_label.show()
                self._center_empty_label()
            self.centerOn(0, 0)
            return

        positions = nx.spring_layout(self.graph, seed=42, k=0.45)
        scaled_positions = self._scale_positions(positions)
        hub_nodes = self._compute_hubs()
        vault_root_index = self._infer_vault_root_index(node_data)

        category_color_map: dict[str, QColor] = {}
        for node_id in self.graph.nodes:
            payload = node_data.get(node_id, {"id": node_id, "label": node_id, "type": "note"})
            title = str(payload.get("label") or node_id)
            note_path = str(payload.get("path") or payload.get("note_path") or "")
            category = self._extract_category(note_path, vault_root_index)
            color = self.color_manager.get_color(category)
            category_color_map.setdefault(category, color)

            node_item = NoteNode(
                self,
                node_id=node_id,
                title=title,
                category=category,
                color=color,
                is_hub=node_id in hub_nodes,
                payload=payload,
            )
            x_pos, y_pos = scaled_positions.get(node_id, (0.0, 0.0))
            node_item.setPos(float(x_pos), float(y_pos))
            self.scene.addItem(node_item)
            self.node_items[node_id] = node_item

        for source, target in self.graph.edges:
            source_item = self.node_items[source]
            target_item = self.node_items[target]
            edge_item = NoteEdge(source_item, target_item)
            source_item.add_edge(edge_item)
            target_item.add_edge(edge_item)
            self.scene.addItem(edge_item)
            self.edge_items.append(edge_item)

        if self._empty_label is not None:
            self._empty_label.hide()

        self._build_legend(category_color_map)

        center = self._graph_centroid()
        self.centerOn(center.x(), center.y())

    def _infer_vault_root_index(self, node_data: dict[str, dict[str, Any]]) -> int:
        note_paths: list[Path] = []
        for payload in node_data.values():
            raw_path = str(payload.get("path") or payload.get("note_path") or "").strip()
            if not raw_path:
                continue
            note_paths.append(Path(raw_path))

        if not note_paths:
            return 0

        try:
            common_path = Path(os.path.commonpath([str(path) for path in note_paths]))
            return max(0, len(common_path.parts) - 1)
        except Exception:
            return max(0, len(note_paths[0].parts) - 2)

    def _extract_category(self, note_path: str, vault_root_index: int) -> str:
        path = Path(note_path)
        parts = path.parts
        category_index = vault_root_index + 1

        if category_index >= len(parts):
            return "Uncategorized"

        category = parts[category_index].strip()
        if not category:
            return "Uncategorized"

        if Path(category).suffix:
            return "Uncategorized"

        return category

    def _build_legend(self, category_color_map: dict[str, QColor]) -> None:
        if self._legend_bg is not None and self._legend_bg.scene() is self.scene:
            self.scene.removeItem(self._legend_bg)
        self._legend_bg = None

        if not category_color_map:
            return

        legend = RoundedRectItem(radius=6.0)
        bg_color = QColor("#1f1f1f")
        bg_color.setAlphaF(0.9)
        legend.setBrush(bg_color)
        legend.setPen(QPen(QColor("#2a2a2a"), 1.0))
        legend.setZValue(300)

        title_item = QGraphicsSimpleTextItem("CATEGORIES", legend)
        title_font = QFont("Segoe UI", 10)
        title_font.setCapitalization(QFont.Capitalization.AllUppercase)
        title_item.setFont(title_font)
        title_item.setBrush(QColor("#888888"))
        title_item.setPos(12, 10)

        entry_font = QFont("Segoe UI", 10)

        y_cursor = 30.0
        max_width = 90.0
        for category in sorted(category_color_map.keys(), key=lambda value: value.lower()):
            color = category_color_map[category]

            dot = QGraphicsEllipseItem(12, y_cursor + 2, 8, 8, legend)
            dot.setPen(QPen(color, 1.0))
            dot.setBrush(color)

            label = QGraphicsSimpleTextItem(category, legend)
            label.setFont(entry_font)
            label.setBrush(QColor("#cccccc"))
            label.setPos(26, y_cursor)

            max_width = max(max_width, label.boundingRect().width() + 40)
            y_cursor += 18.0

        legend_height = y_cursor + 8.0
        legend.setRect(0, 0, max_width + 12.0, legend_height)

        scene_rect = self.scene.sceneRect()
        legend.setPos(scene_rect.left() + 16.0, scene_rect.bottom() - legend_height - 16.0)

        self.scene.addItem(legend)
        self._legend_bg = legend

    def _scale_positions(self, positions: dict[str, Any]) -> dict[str, tuple[float, float]]:
        if not positions:
            return {}

        xs = [float(pos[0]) for pos in positions.values()]
        ys = [float(pos[1]) for pos in positions.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        span_x = max(max_x - min_x, 1e-6)
        span_y = max(max_y - min_y, 1e-6)
        usable = 1800.0

        scaled: dict[str, tuple[float, float]] = {}
        for node_id, (x_pos, y_pos) in positions.items():
            nx_pos = ((float(x_pos) - min_x) / span_x) * usable - usable / 2.0
            ny_pos = ((float(y_pos) - min_y) / span_y) * usable - usable / 2.0
            scaled[node_id] = (nx_pos, ny_pos)
        return scaled

    def _compute_hubs(self) -> set[str]:
        if self.graph.number_of_nodes() == 0:
            return set()

        ranked = sorted(self.graph.degree, key=lambda item: item[1], reverse=True)
        if not ranked:
            return set()

        hub_count = max(1, int(len(ranked) * 0.15))
        return {node for node, degree in ranked[:hub_count] if degree > 0}

    def _graph_centroid(self) -> QPointF:
        if not self.node_items:
            return QPointF(0.0, 0.0)

        xs = [item.scenePos().x() for item in self.node_items.values()]
        ys = [item.scenePos().y() for item in self.node_items.values()]
        return QPointF(sum(xs) / len(xs), sum(ys) / len(ys))

    def _note_node_from_item(self, item: Any) -> NoteNode | None:
        current_item = item
        while current_item is not None:
            if isinstance(current_item, NoteNode):
                return current_item
            current_item = current_item.parentItem()
        return None

    def _component_ids_for(self, node_id: str) -> set[str]:
        component = self._component_cache.get(node_id)
        if component is not None:
            return component
        return {node_id}

    def _component_nodes_for(self, node_id: str) -> list[NoteNode]:
        component_ids = self._component_ids_for(node_id)
        return [self.node_items[nid] for nid in component_ids if nid in self.node_items]

    def _second_degree_ids_for(self, node_id: str) -> set[str]:
        direct_ids = self._adjacency.get(node_id, set())
        second_degree: set[str] = set()
        for neighbor_id in direct_ids:
            second_degree.update(self._adjacency.get(neighbor_id, set()))
        second_degree.discard(node_id)
        second_degree.difference_update(direct_ids)
        return second_degree

    def _apply_node_hover_style(self, node: NoteNode, hovered: bool) -> None:
        if hovered:
            node._apply_geometry(node.hover_radius)
            node.setBrush(node.hover_fill_color)
            node.label_item.setVisible(True)
        else:
            node._apply_geometry(node.base_radius)
            node.setBrush(node.base_fill_color)
            node.label_item.setVisible(False)

    def _set_direct_hover(self, root: NoteNode, hovered: bool) -> None:
        for node in self.node_items.values():
            self._apply_node_hover_style(node, hovered and node is root)

        for edge in self.edge_items:
            source_id = edge.source.node_id
            target_id = edge.target.node_id
            is_direct = source_id == root.node_id or target_id == root.node_id
            edge.set_highlighted(hovered and is_direct)

        if hovered and self.tooltip_visible_for is not None:
            self.hide_tooltip()

    def set_hover_node(self, node: NoteNode | None) -> None:
        if node is self._hovered_node:
            return

        if self._hovered_node is not None:
            self._set_direct_hover(self._hovered_node, False)

        self._hovered_node = node

        if self._hovered_node is not None:
            self._set_direct_hover(self._hovered_node, True)

    def clear_hover_node(self, node: NoteNode | None) -> None:
        if node is None:
            self.set_hover_node(None)
            return

        if self._hovered_node is node:
            self.set_hover_node(None)

    def begin_component_drag(self, node: NoteNode, scene_pos: QPointF, drag_offset: QPointF) -> None:
        self._active_drag_node = node
        self._active_drag_anchor_offset = QPointF(drag_offset)
        self._active_drag_component_ids = set(self._component_ids_for(node.node_id))
        self._active_drag_direct_ids = set(self._adjacency.get(node.node_id, set()))
        self._active_drag_second_degree_ids = self._second_degree_ids_for(node.node_id)
        self._active_drag_direct_rest_lengths = {}
        self._active_drag_second_rest_lengths = {}

        anchor_pos = node.scenePos()
        for neighbor_id in self._active_drag_direct_ids:
            neighbor = self.node_items.get(neighbor_id)
            if neighbor is None:
                continue
            rest_length = math.hypot(
                neighbor.scenePos().x() - anchor_pos.x(),
                neighbor.scenePos().y() - anchor_pos.y(),
            )
            self._active_drag_direct_rest_lengths[neighbor_id] = max(1.0, rest_length)

        for neighbor_id in self._active_drag_second_degree_ids:
            neighbor = self.node_items.get(neighbor_id)
            if neighbor is None:
                continue
            rest_length = math.hypot(
                neighbor.scenePos().x() - anchor_pos.x(),
                neighbor.scenePos().y() - anchor_pos.y(),
            )
            self._active_drag_second_rest_lengths[neighbor_id] = max(1.0, rest_length)

        self.update_component_drag(scene_pos)

    def _update_edges_for_ids(self, node_ids: set[str]) -> None:
        for edge in self.edge_items:
            if edge.source.node_id in node_ids or edge.target.node_id in node_ids:
                edge.update_position()

    def update_component_drag(self, scene_pos: QPointF) -> None:
        if self._active_drag_node is None:
            return

        anchor_target_pos = scene_pos - self._active_drag_anchor_offset
        self._active_drag_node.setPos(anchor_target_pos)
        moved_ids: set[str] = {self._active_drag_node.node_id}

        if moved_ids:
            self._update_edges_for_ids(moved_ids)

        if self.tooltip_visible_for is self._active_drag_node:
            self.show_tooltip_for_node(self._active_drag_node)

    def end_component_drag(self, scene_pos: QPointF | None = None) -> None:
        if self._active_drag_node is None:
            return

        if scene_pos is not None:
            self.update_component_drag(scene_pos)

        self._active_drag_node._is_dragging = False
        self._active_drag_node = None
        self._active_drag_anchor_offset = QPointF()
        self._active_drag_component_ids.clear()
        self._active_drag_direct_ids.clear()
        self._active_drag_second_degree_ids.clear()
        self._active_drag_direct_rest_lengths.clear()
        self._active_drag_second_rest_lengths.clear()

    def _physics_step(self) -> None:
        if not self.node_items:
            return
        if not self.isVisible():
            return

        nodes = list(self.node_items.values())
        dragging_ids: set[str] = set()
        if self._active_drag_node is not None:
            dragging_ids.add(self._active_drag_node.node_id)

        simulation_scope_ids: set[str] = {node.node_id for node in nodes}
        if self._active_drag_node is not None and self._active_drag_component_ids:
            simulation_scope_ids = set(self._active_drag_component_ids)

        force_map: dict[str, QPointF] = {
            node.node_id: QPointF(0.0, 0.0)
            for node in nodes
            if node.node_id in simulation_scope_ids and node.node_id not in dragging_ids
        }

        threshold_sq = self._repulsion_threshold * self._repulsion_threshold
        moved_any = False

        for index in range(len(nodes)):
            node_a = nodes[index]
            for next_index in range(index + 1, len(nodes)):
                node_b = nodes[next_index]

                if (
                    node_a.node_id not in simulation_scope_ids
                    or node_b.node_id not in simulation_scope_ids
                ):
                    continue

                a_dragging = node_a.node_id in dragging_ids
                b_dragging = node_b.node_id in dragging_ids
                if a_dragging and b_dragging:
                    continue

                delta = node_b.scenePos() - node_a.scenePos()
                dx = delta.x()
                dy = delta.y()
                distance_sq = (dx * dx) + (dy * dy)

                if distance_sq <= 1e-6:
                    dx = 0.5
                    dy = 0.0
                    distance_sq = 0.25

                if distance_sq > threshold_sq:
                    continue

                distance = math.sqrt(distance_sq)
                if distance <= 1e-6:
                    continue

                falloff = (self._repulsion_threshold - distance) / self._repulsion_threshold
                force_magnitude = (self._repulsion_constant / distance_sq) * max(0.0, falloff)

                ux = dx / distance
                uy = dy / distance
                force_x = ux * force_magnitude
                force_y = uy * force_magnitude

                if not a_dragging:
                    current = force_map[node_a.node_id]
                    force_map[node_a.node_id] = QPointF(current.x() - force_x, current.y() - force_y)
                if not b_dragging:
                    current = force_map[node_b.node_id]
                    force_map[node_b.node_id] = QPointF(current.x() + force_x, current.y() + force_y)

        if self._active_drag_node is not None:
            drag_id = self._active_drag_node.node_id
            drag_pos = self._active_drag_node.scenePos()

            for node_id in self._active_drag_direct_ids:
                if node_id not in self._active_drag_component_ids or node_id in dragging_ids:
                    continue
                neighbor = self.node_items.get(node_id)
                if neighbor is None:
                    continue

                delta = drag_pos - neighbor.scenePos()
                distance = math.hypot(delta.x(), delta.y())
                if distance <= 1e-6:
                    continue

                rest_length = self._active_drag_direct_rest_lengths.get(node_id, distance)
                spring_force = self._direct_spring_stiffness * (distance - rest_length)
                force_x = (delta.x() / distance) * spring_force
                force_y = (delta.y() / distance) * spring_force

                current = force_map.get(node_id, QPointF(0.0, 0.0))
                force_map[node_id] = QPointF(current.x() + force_x, current.y() + force_y)

            for node_id in self._active_drag_second_degree_ids:
                if node_id not in self._active_drag_component_ids or node_id in dragging_ids:
                    continue
                neighbor = self.node_items.get(node_id)
                if neighbor is None:
                    continue

                delta = drag_pos - neighbor.scenePos()
                distance = math.hypot(delta.x(), delta.y())
                if distance <= 1e-6:
                    continue

                rest_length = self._active_drag_second_rest_lengths.get(node_id, distance)
                spring_force = self._second_spring_stiffness * (distance - rest_length)
                force_x = (delta.x() / distance) * spring_force
                force_y = (delta.y() / distance) * spring_force

                current = force_map.get(node_id, QPointF(0.0, 0.0))
                force_map[node_id] = QPointF(current.x() + force_x, current.y() + force_y)

        scene_rect = self.scene.sceneRect()
        moved_ids: set[str] = set()

        for node in nodes:
            if node.node_id not in simulation_scope_ids:
                node.velocity = QPointF(0.0, 0.0)
                continue

            if node.node_id in dragging_ids:
                node.velocity = QPointF(0.0, 0.0)
                continue

            force = force_map.get(node.node_id)
            if force is None:
                continue

            node_damping = self._damping
            if node.node_id in self._active_drag_second_degree_ids:
                node_damping *= self._second_degree_damping_scale

            velocity_x = (node.velocity.x() + force.x()) * node_damping
            velocity_y = (node.velocity.y() + force.y()) * node_damping

            speed = math.sqrt((velocity_x * velocity_x) + (velocity_y * velocity_y))
            if speed > self._max_speed and speed > 1e-6:
                scale = self._max_speed / speed
                velocity_x *= scale
                velocity_y *= scale

            if abs(velocity_x) < 1e-3 and abs(velocity_y) < 1e-3:
                node.velocity = QPointF(0.0, 0.0)
                continue

            node.velocity = QPointF(velocity_x, velocity_y)

            target_pos = node.scenePos() + node.velocity
            bounded_x = max(scene_rect.left() + node.current_radius, min(scene_rect.right() - node.current_radius, target_pos.x()))
            bounded_y = max(scene_rect.top() + node.current_radius, min(scene_rect.bottom() - node.current_radius, target_pos.y()))

            if abs(bounded_x - node.scenePos().x()) > 1e-6 or abs(bounded_y - node.scenePos().y()) > 1e-6:
                node.setPos(QPointF(bounded_x, bounded_y))
                moved_any = True
                moved_ids.add(node.node_id)

        if moved_any:
            self._update_edges_for_ids(moved_ids)

        if self.tooltip_visible_for is not None and self.tooltip_visible_for in self.node_items.values():
            self.show_tooltip_for_node(self.tooltip_visible_for)

    def show_tooltip_for_node(self, node: NoteNode) -> None:
        if self._tooltip_bg is None or self._tooltip_title is None or self._tooltip_meta is None:
            return

        self.tooltip_visible_for = node

        self._tooltip_title.setText(node.note_name)
        self._tooltip_meta.setText(f"{node.category} | {len(node.connected_edges)} connections")

        self._tooltip_title.setPos(10, 8)
        meta_y = self._tooltip_title.boundingRect().height() + 12
        self._tooltip_meta.setPos(10, meta_y)

        width = max(self._tooltip_title.boundingRect().width(), self._tooltip_meta.boundingRect().width()) + 20
        height = self._tooltip_title.boundingRect().height() + self._tooltip_meta.boundingRect().height() + 20
        self._tooltip_bg.setRect(0, 0, width, height)

        pos = node.scenePos() + QPointF(node.current_radius + 12, -node.current_radius - height)
        scene_rect = self.scene.sceneRect()
        x_pos = max(scene_rect.left(), min(pos.x(), scene_rect.right() - width))
        y_pos = max(scene_rect.top(), min(pos.y(), scene_rect.bottom() - height))
        self._tooltip_bg.setPos(x_pos, y_pos)
        self._tooltip_bg.show()

    def hide_tooltip(self) -> None:
        self.tooltip_visible_for = None
        if self._tooltip_bg is not None:
            self._tooltip_bg.hide()

    def mousePressEvent(self, event: Any) -> None:
        is_middle = event.button() == Qt.MouseButton.MiddleButton
        clicked_item = self.itemAt(event.position().toPoint())
        clicked_node = self._note_node_from_item(clicked_item)
        is_left_empty = event.button() == Qt.MouseButton.LeftButton and clicked_node is None

        if event.button() == Qt.MouseButton.LeftButton and clicked_node is not None:
            self._active_drag_node = clicked_node
            clicked_node.begin_manual_drag(self.mapToScene(event.position().toPoint()))
            clicked_node.grabMouse()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if is_middle or is_left_empty:
            self._panning = True
            self._pan_last_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        if self._active_drag_node is not None:
            self._active_drag_node.drag_manual_to(self.mapToScene(event.position().toPoint()))
            event.accept()
            return

        self.set_hover_node(self._note_node_from_item(self.itemAt(event.position().toPoint())))

        if self._panning:
            current_pos = event.position().toPoint()
            delta = current_pos - self._pan_last_pos
            self._pan_last_pos = current_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        if self._active_drag_node is not None and event.button() == Qt.MouseButton.LeftButton:
            drag_node = self._active_drag_node
            drag_node.end_manual_drag(self.mapToScene(event.position().toPoint()))
            drag_node.ungrabMouse()
            self._active_drag_node = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if self._panning and event.button() in {Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton}:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event: Any) -> None:
        super().enterEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self.set_hover_node(None)
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            if angle == 0:
                event.accept()
                return

            zoom_step = 1.15 if angle > 0 else (1.0 / 1.15)
            target_zoom = self._zoom * zoom_step
            target_zoom = max(self._min_zoom, min(self._max_zoom, target_zoom))
            if target_zoom == self._zoom:
                event.accept()
                return

            scale_factor = target_zoom / self._zoom
            self.scale(scale_factor, scale_factor)
            self._zoom = target_zoom
            event.accept()
            return

        super().wheelEvent(event)
