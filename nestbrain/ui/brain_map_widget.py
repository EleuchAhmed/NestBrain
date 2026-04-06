from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

import networkx as nx
from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
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

        self._base_pen = QPen(QColor("#3a3a3a"), 1.0)
        self._base_pen.setCosmetic(True)

        self._highlight_pen = QPen(QColor("#666666"), 1.0)
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

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
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
        self.label_item.setBrush(QColor("#cccccc"))
        self.label_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)

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
        self.label_item.setPos(-rect.width() / 2.0, self.current_radius + 5)

    def set_connected_edges_hover(self, hovered: bool) -> None:
        for edge in self.connected_edges:
            edge.set_highlighted(hovered)

    def hoverEnterEvent(self, event: Any) -> None:
        self._apply_geometry(self.hover_radius)
        self.setBrush(self.hover_fill_color)
        self.label_item.setBrush(QColor("#ffffff"))
        self.set_connected_edges_hover(True)
        self.view.show_tooltip_for_node(self)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: Any) -> None:
        self._apply_geometry(self.base_radius)
        self.setBrush(self.base_fill_color)
        self.label_item.setBrush(QColor("#cccccc"))
        self.set_connected_edges_hover(False)
        self.view.hide_tooltip()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
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

        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 3.0

        self._panning = False
        self._pan_last_pos = QPoint()
        self.tooltip_visible_for: NoteNode | None = None

        self._tooltip_bg: RoundedRectItem | None = None
        self._tooltip_title: QGraphicsSimpleTextItem | None = None
        self._tooltip_meta: QGraphicsSimpleTextItem | None = None
        self._empty_label: QGraphicsSimpleTextItem | None = None
        self._legend_bg: RoundedRectItem | None = None

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
        is_left_empty = event.button() == Qt.MouseButton.LeftButton and self.itemAt(event.position().toPoint()) is None
        if is_middle or is_left_empty:
            self._panning = True
            self._pan_last_pos = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
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
        if self._panning and event.button() in {Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton}:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

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
