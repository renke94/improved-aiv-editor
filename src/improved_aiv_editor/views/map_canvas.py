"""Interactive 98x98 map canvas built on QGraphicsScene/QGraphicsView."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF, QSignalBlocker
from PyQt6.QtGui import (
    QPen, QBrush, QColor, QPainter, QPainterPath,
    QFont, QWheelEvent, QMouseEvent, QKeyEvent,
)
from PyQt6.QtWidgets import (
    QGraphicsScene, QGraphicsView, QGraphicsItem,
    QGraphicsRectItem, QGraphicsPathItem, QGraphicsSimpleTextItem,
)

from improved_aiv_editor.i18n import tr

if TYPE_CHECKING:
    from improved_aiv_editor.models.aiv_document import AivDocument, Frame
    from improved_aiv_editor.models.building_registry import BuildingRegistry, BuildingDef

MAP_SIZE = 98
TILE_SIZE = 10.0

CATEGORY_COLORS: dict[str, QColor] = {
    "castle":     QColor(100, 80, 60, 160),
    "wall":       QColor(140, 140, 140, 180),
    "gatehouses": QColor(120, 100, 80, 160),
    "weapons":    QColor(180, 80, 80, 140),
    "industry":   QColor(180, 160, 100, 140),
    "food":       QColor(100, 170, 80, 140),
    "town":       QColor(160, 140, 120, 140),
    "good_stuff": QColor(100, 180, 100, 140),
    "bad_stuff":  QColor(180, 60, 60, 140),
    "moats":      QColor(60, 120, 200, 140),
    "units":      QColor(200, 160, 60, 140),
}

SELECTION_COLOR = QColor(40, 120, 255, 100)
SELECTION_BORDER = QColor(40, 120, 255, 220)

_DEFAULT_COLOR = QColor(150, 150, 150, 140)


def _resolve_building_color(building_def: "BuildingDef") -> QColor:
    """Return per-building color if set, otherwise fall back to category color."""
    if building_def.color:
        return QColor(building_def.color)
    return CATEGORY_COLORS.get(building_def.category, _DEFAULT_COLOR)


class BuildingGraphicsItem(QGraphicsRectItem):
    """A building placed on the map, linked to a specific frame and position index."""

    def __init__(
        self,
        frame_index: int,
        pos_index: int,
        building_def: "BuildingDef",
        tile_x: int,
        tile_y: int,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        w = building_def.width * TILE_SIZE
        h = building_def.height * TILE_SIZE
        super().__init__(0, 0, w, h, parent)

        self.frame_index = frame_index
        self.pos_index = pos_index
        self.building_def = building_def
        self.tile_x = tile_x
        self.tile_y = tile_y

        color = _resolve_building_color(building_def)
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(150), 1.0))

        self.setPos(tile_x * TILE_SIZE, tile_y * TILE_SIZE)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(frame_index)

        self._label = QGraphicsSimpleTextItem(building_def.display_name(), self)
        font = QFont("Helvetica", 6)
        self._label.setFont(font)
        self._label.setBrush(QBrush(QColor(0, 0, 0, 200)))
        label_rect = self._label.boundingRect()
        if label_rect.width() > w:
            self._label.setVisible(False)
        else:
            self._label.setPos(
                (w - label_rect.width()) / 2,
                (h - label_rect.height()) / 2,
            )

    def paint(self, painter: QPainter, option: object, widget: object = None) -> None:  # type: ignore[override]
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QPen(SELECTION_BORDER, 2.0))
            painter.setBrush(QBrush(SELECTION_COLOR))
            painter.drawRect(self.rect())


class GatehouseGraphicsItem(QGraphicsRectItem):
    """A gatehouse on the map with an orientation indicator (NS or EW arrow)."""

    _ARROW_COLOR = QColor(255, 255, 255, 200)
    _ARROW_PEN_WIDTH = 1.8
    _ARROWHEAD_SIZE = 3.0

    def __init__(
        self,
        frame_index: int,
        pos_index: int,
        building_def: "BuildingDef",
        tile_x: int,
        tile_y: int,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        w = building_def.width * TILE_SIZE
        h = building_def.height * TILE_SIZE
        super().__init__(0, 0, w, h, parent)

        self.frame_index = frame_index
        self.pos_index = pos_index
        self.building_def = building_def
        self.tile_x = tile_x
        self.tile_y = tile_y
        self._is_ns = building_def.kind == "gatehouse-ns"

        color = _resolve_building_color(building_def)
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(150), 1.0))

        self.setPos(tile_x * TILE_SIZE, tile_y * TILE_SIZE)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(frame_index)

        self._label = QGraphicsSimpleTextItem(building_def.display_name(), self)
        font = QFont("Helvetica", 6)
        self._label.setFont(font)
        self._label.setBrush(QBrush(QColor(0, 0, 0, 200)))
        label_rect = self._label.boundingRect()
        if label_rect.width() > w:
            self._label.setVisible(False)
        else:
            self._label.setPos(
                (w - label_rect.width()) / 2,
                (h - label_rect.height()) / 2 - 5,
            )

    def paint(self, painter: QPainter, option: object, widget: object = None) -> None:  # type: ignore[override]
        super().paint(painter, option, widget)

        r = self.rect()
        cx = r.center().x()
        cy = r.center().y()
        margin = TILE_SIZE * 0.8
        a = self._ARROWHEAD_SIZE

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self._ARROW_COLOR, self._ARROW_PEN_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(QBrush(self._ARROW_COLOR))

        if self._is_ns:
            y1 = r.top() + margin
            y2 = r.bottom() - margin
            painter.drawLine(QPointF(cx, y1), QPointF(cx, y2))
            head_n = QPainterPath()
            head_n.moveTo(cx, y1)
            head_n.lineTo(cx - a, y1 + a * 1.5)
            head_n.lineTo(cx + a, y1 + a * 1.5)
            head_n.closeSubpath()
            painter.drawPath(head_n)
            head_s = QPainterPath()
            head_s.moveTo(cx, y2)
            head_s.lineTo(cx - a, y2 - a * 1.5)
            head_s.lineTo(cx + a, y2 - a * 1.5)
            head_s.closeSubpath()
            painter.drawPath(head_s)
        else:
            x1 = r.left() + margin
            x2 = r.right() - margin
            painter.drawLine(QPointF(x1, cy), QPointF(x2, cy))
            head_w = QPainterPath()
            head_w.moveTo(x1, cy)
            head_w.lineTo(x1 + a * 1.5, cy - a)
            head_w.lineTo(x1 + a * 1.5, cy + a)
            head_w.closeSubpath()
            painter.drawPath(head_w)
            head_e = QPainterPath()
            head_e.moveTo(x2, cy)
            head_e.lineTo(x2 - a * 1.5, cy - a)
            head_e.lineTo(x2 - a * 1.5, cy + a)
            head_e.closeSubpath()
            painter.drawPath(head_e)

        if self.isSelected():
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            painter.setPen(QPen(SELECTION_BORDER, 2.0))
            painter.setBrush(QBrush(SELECTION_COLOR))
            painter.drawRect(self.rect())


class KeepGraphicsItem(QGraphicsPathItem):
    """Special non-rectangular Keep shape with colored sections for
    Castle (top-left 7x7), Stockpile (right 5x5), and Fireplace (bottom 7x7)."""

    _CASTLE_COLOR = QColor(130, 100, 70, 190)
    _STOCKPILE_COLOR = QColor(190, 170, 90, 190)
    _FIREPLACE_COLOR = QColor(190, 110, 70, 190)
    _CORRIDOR_COLOR = QColor(160, 140, 110, 150)
    _OUTLINE_COLOR = QColor(60, 50, 40)
    _LABEL_COLOR = QColor(255, 255, 255, 220)

    def __init__(
        self,
        frame_index: int,
        pos_index: int,
        building_def: "BuildingDef",
        tile_x: int,
        tile_y: int,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(parent)
        self.frame_index = frame_index
        self.pos_index = pos_index
        self.building_def = building_def
        self.tile_x = tile_x
        self.tile_y = tile_y

        self._build_path()
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setPos(tile_x * TILE_SIZE, tile_y * TILE_SIZE)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(frame_index)

    def _build_path(self) -> None:
        t = TILE_SIZE
        path = QPainterPath()
        path.moveTo(0, 0)
        path.lineTo(7 * t, 0)
        path.lineTo(7 * t, 2 * t)
        path.lineTo(12 * t, 2 * t)
        path.lineTo(12 * t, 7 * t)
        path.lineTo(5 * t, 7 * t)
        path.lineTo(5 * t, 8 * t)
        path.lineTo(7 * t, 8 * t)
        path.lineTo(7 * t, 15 * t)
        path.lineTo(0, 15 * t)
        path.lineTo(0, 8 * t)
        path.lineTo(2 * t, 8 * t)
        path.lineTo(2 * t, 7 * t)
        path.lineTo(0, 7 * t)
        path.closeSubpath()
        self.setPath(path)

    def paint(self, painter: QPainter, option: object, widget: object = None) -> None:  # type: ignore[override]
        t = TILE_SIZE
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        no_pen = QPen(Qt.PenStyle.NoPen)
        painter.setPen(no_pen)

        painter.setBrush(QBrush(self._CASTLE_COLOR))
        painter.drawRect(QRectF(0, 0, 7 * t, 7 * t))

        painter.setBrush(QBrush(self._STOCKPILE_COLOR))
        painter.drawRect(QRectF(7 * t, 2 * t, 5 * t, 5 * t))

        painter.setBrush(QBrush(self._FIREPLACE_COLOR))
        painter.drawRect(QRectF(0, 8 * t, 7 * t, 7 * t))

        painter.setBrush(QBrush(self._CORRIDOR_COLOR))
        painter.drawRect(QRectF(0, 7 * t, 2 * t, t))
        painter.drawRect(QRectF(5 * t, 7 * t, 2 * t, t))

        painter.setPen(QPen(self._OUTLINE_COLOR, 1.5))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawPath(self.path())

        font = QFont("Helvetica", 7)
        painter.setFont(font)
        painter.setPen(QPen(self._LABEL_COLOR))

        keep_rect = QRectF(0, 0, 7 * t, 7 * t)
        painter.drawText(keep_rect, Qt.AlignmentFlag.AlignCenter, tr("Keep"))

        stock_rect = QRectF(7 * t, 2 * t, 5 * t, 5 * t)
        painter.drawText(stock_rect, Qt.AlignmentFlag.AlignCenter, tr("Stockpile"))

        fire_rect = QRectF(0, 8 * t, 7 * t, 7 * t)
        painter.drawText(fire_rect, Qt.AlignmentFlag.AlignCenter, tr("Fireplace"))

        if self.isSelected():
            painter.setPen(QPen(SELECTION_BORDER, 2.0))
            painter.setBrush(QBrush(SELECTION_COLOR))
            painter.drawPath(self.path())


class WallSegmentItem(QGraphicsRectItem):
    """A 1x1 wall tile on the map."""

    def __init__(
        self,
        frame_index: int,
        pos_index: int,
        building_def: "BuildingDef",
        tile_x: int,
        tile_y: int,
        parent: Optional[QGraphicsItem] = None,
    ) -> None:
        super().__init__(0, 0, TILE_SIZE, TILE_SIZE, parent)
        self.frame_index = frame_index
        self.pos_index = pos_index
        self.building_def = building_def
        self.tile_x = tile_x
        self.tile_y = tile_y

        color = _resolve_building_color(building_def)
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(150), 0.5))
        self.setPos(tile_x * TILE_SIZE, tile_y * TILE_SIZE)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(frame_index)

    def paint(self, painter: QPainter, option: object, widget: object = None) -> None:  # type: ignore[override]
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QPen(SELECTION_BORDER, 1.5))
            painter.setBrush(QBrush(SELECTION_COLOR))
            painter.drawRect(self.rect())


class MapScene(QGraphicsScene):
    """The 98x98 tile-based scene with grid and building items."""

    building_selected = pyqtSignal(int, int)
    building_deselected = pyqtSignal()
    position_hovered = pyqtSignal(int, int)

    def __init__(self, registry: "BuildingRegistry", parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._registry = registry
        self._document: Optional["AivDocument"] = None
        self._building_items: list[QGraphicsItem] = []
        self._item_map: dict[tuple[int, int], QGraphicsItem] = {}
        self._ghost_item: Optional[QGraphicsItem] = None

        scene_w = MAP_SIZE * TILE_SIZE
        scene_h = MAP_SIZE * TILE_SIZE
        padding = scene_w * 0.5
        self.setSceneRect(-padding, -padding, scene_w + 2 * padding, scene_h + 2 * padding)
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)

        self._draw_grid()

    def _draw_grid(self) -> None:
        scene_w = MAP_SIZE * TILE_SIZE
        scene_h = MAP_SIZE * TILE_SIZE

        map_bg = QGraphicsRectItem(0, 0, scene_w, scene_h)
        map_bg.setBrush(QBrush(QColor(230, 225, 215)))
        map_bg.setPen(QPen(Qt.PenStyle.NoPen))
        map_bg.setZValue(-2)
        self.addItem(map_bg)

        light_pen = QPen(QColor(180, 180, 180, 100), 0.5)
        dark_pen = QPen(QColor(140, 140, 140, 150), 0.8)

        for i in range(MAP_SIZE + 1):
            pen = dark_pen if i % 10 == 0 else light_pen
            x = i * TILE_SIZE
            line_v = self.addLine(x, 0, x, scene_h, pen)
            line_v.setZValue(-1)
            line_h = self.addLine(0, x, scene_w, x, pen)
            line_h.setZValue(-1)

    def set_document(self, document: Optional["AivDocument"]) -> None:
        if self._document is not None:
            self._document.frame_inserting.disconnect(self._on_frame_inserting)
            self._document.frame_added.disconnect(self._on_frame_added)
            self._document.frame_removed.disconnect(self._on_frame_removed)
            self._document.frames_reordered.disconnect(self.rebuild_buildings)
            self._document.frame_positions_changed.disconnect(
                self._on_frame_positions_changed
            )
            self._document.frames_changed.disconnect(self._on_document_frames_changed)
        self._document = document
        if document is not None:
            document.frame_inserting.connect(self._on_frame_inserting)
            document.frame_added.connect(self._on_frame_added)
            document.frame_removed.connect(self._on_frame_removed)
            document.frames_reordered.connect(self.rebuild_buildings)
            document.frame_positions_changed.connect(self._on_frame_positions_changed)
            document.frames_changed.connect(self._on_document_frames_changed)
        self.rebuild_buildings()

    def _on_document_frames_changed(self) -> None:
        """Pause / metadata-only changes; building geometry is handled elsewhere."""

    def _make_building_item(
        self,
        frame_idx: int,
        pos_idx: int,
        bdef: "BuildingDef",
        tx: int,
        ty: int,
    ) -> QGraphicsItem:
        if bdef.id == 61:
            return KeepGraphicsItem(frame_idx, pos_idx, bdef, tx, ty)
        if bdef.kind == "wall":
            return WallSegmentItem(frame_idx, pos_idx, bdef, tx, ty)
        if bdef.kind in ("gatehouse-ns", "gatehouse-ew"):
            return GatehouseGraphicsItem(frame_idx, pos_idx, bdef, tx, ty)
        return BuildingGraphicsItem(frame_idx, pos_idx, bdef, tx, ty)

    def _add_items_for_frame(self, frame_idx: int, frame: "Frame") -> None:
        bdef = self._registry.get_by_id(frame.item_type)
        if bdef is None:
            return
        for pos_idx, (tx, ty) in enumerate(frame.positions):
            item = self._make_building_item(frame_idx, pos_idx, bdef, tx, ty)
            self.addItem(item)
            self._building_items.append(item)
            self._item_map[(frame_idx, pos_idx)] = item

    def _remove_frame_items(self, frame_index: int) -> None:
        keys = [k for k in self._item_map if k[0] == frame_index]
        for k in keys:
            item = self._item_map.pop(k)
            self.removeItem(item)
            self._building_items.remove(item)

    def _set_item_frame_index(self, item: QGraphicsItem, fi: int) -> None:
        if isinstance(item, (BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem)):
            item.frame_index = fi
        item.setZValue(fi)

    def _shift_item_frame_indices_ge(self, from_index: int, delta: int) -> None:
        new_map: dict[tuple[int, int], QGraphicsItem] = {}
        for (fi, pi), item in list(self._item_map.items()):
            if fi >= from_index:
                fi2 = fi + delta
                self._set_item_frame_index(item, fi2)
                new_map[(fi2, pi)] = item
            else:
                new_map[(fi, pi)] = item
        self._item_map = new_map

    def _shift_item_frame_indices_gt(self, after_index: int, delta: int) -> None:
        new_map: dict[tuple[int, int], QGraphicsItem] = {}
        for (fi, pi), item in list(self._item_map.items()):
            if fi > after_index:
                fi2 = fi + delta
                self._set_item_frame_index(item, fi2)
                new_map[(fi2, pi)] = item
            else:
                new_map[(fi, pi)] = item
        self._item_map = new_map

    def _on_frame_inserting(self, index: int) -> None:
        if self._document is None:
            return
        self._shift_item_frame_indices_ge(index, +1)

    def _on_frame_added(self, index: int) -> None:
        if self._document is None:
            return
        frame = self._document.frames[index]
        self._add_items_for_frame(index, frame)

    def _on_frame_removed(self, index: int) -> None:
        self._remove_frame_items(index)
        self._shift_item_frame_indices_gt(index, -1)

    def _on_frame_positions_changed(self, frame_indices: list) -> None:
        if self._document is None:
            return
        for idx in frame_indices:
            self._remove_frame_items(int(idx))
            frame = self._document.frames[int(idx)]
            self._add_items_for_frame(int(idx), frame)

    def rebuild_buildings(self) -> None:
        for item in self._building_items:
            self.removeItem(item)
        self._building_items.clear()
        self._item_map.clear()

        if self._document is None:
            return

        for frame_idx, frame in enumerate(self._document.frames):
            self._add_items_for_frame(frame_idx, frame)

    def get_building_at(self, scene_pos: QPointF) -> Optional[QGraphicsItem]:
        """Hit-test using item geometry. Tile grid only stores frame origins for many buildings,
        so grid-based lookup would miss clicks on non-origin footprint tiles."""
        for item in self.items(scene_pos):
            cur: Optional[QGraphicsItem] = item
            while cur is not None:
                if isinstance(cur, (BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem)):
                    return cur
                cur = cur.parentItem()
        return None

    def get_selected_buildings(self) -> list[QGraphicsItem]:
        return [
            item for item in self.selectedItems()
            if isinstance(item, (BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem))
        ]

    def select_buildings_in_rect(self, rect: QRectF, additive: bool) -> None:
        """Select all building/wall/keep items whose scene bounds intersect rect (normalized)."""
        r = rect.normalized()
        if r.width() <= 0.0 and r.height() <= 0.0:
            return
        with QSignalBlocker(self):
            if not additive:
                self.clearSelection()
            for item in self._building_items:
                if not isinstance(
                    item, (BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem)
                ):
                    continue
                if item.sceneBoundingRect().intersects(r):
                    item.setSelected(True)

    def get_occupied_origins(self) -> set[tuple[int, int]]:
        """Return every tile occupied by a non-unit building (for placement checks)."""
        if self._document is None:
            return set()
        return self._document.tile_grid.nonunit_occupied_tiles()

    def has_keep(self) -> bool:
        """Return True if the document already contains a Keep (item_type 61)."""
        if self._document is None:
            return False
        return self._document.tile_grid.has_keep()

    def is_placement_valid(self, item_type: int, tx: int, ty: int) -> bool:
        """Check whether origin (tx, ty) is free. Units skip the check entirely.
        Only one keep (item_type 61) is allowed at a time."""
        bdef = self._registry.get_by_id(item_type)
        if bdef is None:
            return False
        if item_type == 61 and self.has_keep():
            return False
        if bdef.kind == "unit":
            return True
        if self._document is None:
            return False
        return not self._document.tile_grid.is_origin_occupied(tx, ty, exclude_units=True)

    def can_place_building(self, bdef: "BuildingDef", tx: int, ty: int) -> bool:
        """Full footprint check: every tile the building covers must be free."""
        item_type = bdef.file_item_type()
        for dx, dy in bdef.footprint_offsets():
            nx, ny = tx + dx, ty + dy
            if nx < 1 or nx > MAP_SIZE or ny < 1 or ny > MAP_SIZE:
                return False
            if not self.is_placement_valid(item_type, nx, ny):
                return False
        return True

    def set_ghost(self, building_def: Optional["BuildingDef"], tile_x: int = 0, tile_y: int = 0) -> None:
        if self._ghost_item is not None:
            self.removeItem(self._ghost_item)
            self._ghost_item = None

        if building_def is None:
            return

        w = building_def.width * TILE_SIZE
        h = building_def.height * TILE_SIZE
        ghost = QGraphicsRectItem(0, 0, w, h)
        ghost.setBrush(QBrush(QColor(100, 200, 100, 80)))
        ghost.setPen(QPen(QColor(100, 200, 100, 180), 1.0, Qt.PenStyle.DashLine))
        ghost.setPos(tile_x * TILE_SIZE, tile_y * TILE_SIZE)
        ghost.setZValue(10000)
        self.addItem(ghost)
        self._ghost_item = ghost
        self._ghost_building_def = building_def

    def update_ghost_position(self, tile_x: int, tile_y: int) -> None:
        if self._ghost_item is None:
            return
        self._ghost_item.setPos(tile_x * TILE_SIZE, tile_y * TILE_SIZE)
        bdef = getattr(self, "_ghost_building_def", None)
        if bdef is not None:
            valid = self.can_place_building(bdef, tile_x, tile_y)
            if valid:
                self._ghost_item.setBrush(QBrush(QColor(100, 200, 100, 80)))
                self._ghost_item.setPen(QPen(QColor(100, 200, 100, 180), 1.0, Qt.PenStyle.DashLine))
            else:
                self._ghost_item.setBrush(QBrush(QColor(220, 60, 60, 80)))
                self._ghost_item.setPen(QPen(QColor(220, 60, 60, 180), 1.0, Qt.PenStyle.DashLine))

    def clear_ghost(self) -> None:
        self.set_ghost(None)
        self._ghost_building_def = None

    def scene_to_tile(self, scene_pos: QPointF) -> tuple[int, int]:
        tx = int(scene_pos.x() / TILE_SIZE)
        ty = int(scene_pos.y() / TILE_SIZE)
        return max(1, min(MAP_SIZE, tx)), max(1, min(MAP_SIZE, ty))


class MapCanvas(QGraphicsView):
    """Interactive view wrapping MapScene with zoom, pan, and tool delegation."""

    position_changed = pyqtSignal(int, int)
    zoom_changed = pyqtSignal(float)
    switch_to_select_requested = pyqtSignal()

    def __init__(self, scene: MapScene, parent: object = None) -> None:
        super().__init__(scene, parent)  # type: ignore[arg-type]
        self._map_scene = scene
        self._zoom_level: float = 1.0
        self._panning: bool = False
        self._pan_start: QPointF = QPointF()
        self._active_tool: object | None = None

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setBackgroundBrush(QBrush(QColor(30, 30, 30)))

        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_tool(self, tool: object | None) -> None:
        self._active_tool = tool

    _MIN_ZOOM = 0.2
    _MAX_ZOOM = 20.0

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        cursor_vp = event.position().toPoint()
        old_scene_pos = self.mapToScene(cursor_vp)
        factor = 1.05
        if event.angleDelta().y() > 0:
            new_zoom = self._zoom_level * factor
            if new_zoom > self._MAX_ZOOM:
                return
            self.scale(factor, factor)
            self._zoom_level = new_zoom
        else:
            new_zoom = self._zoom_level / factor
            if new_zoom < self._MIN_ZOOM:
                return
            self.scale(1 / factor, 1 / factor)
            self._zoom_level = new_zoom
        new_vp_pos = self.mapFromScene(old_scene_pos)
        scroll_delta = new_vp_pos - cursor_vp
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() + scroll_delta.x()
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() + scroll_delta.y()
        )
        self.zoom_changed.emit(self._zoom_level)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.switch_to_select_requested.emit()
            event.accept()
            return

        tool = self._active_tool
        if tool is not None and hasattr(tool, "on_press"):
            scene_pos = self.mapToScene(event.pos())
            tool.on_press(scene_pos, event)
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return

        scene_pos = self.mapToScene(event.pos())
        tx, ty = self._map_scene.scene_to_tile(scene_pos)
        self.position_changed.emit(tx, ty)

        tool = self._active_tool
        if tool is not None and hasattr(tool, "on_move"):
            tool.on_move(scene_pos, event)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        tool = self._active_tool
        if tool is not None and hasattr(tool, "on_release"):
            scene_pos = self.mapToScene(event.pos())
            tool.on_release(scene_pos, event)
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        tool = self._active_tool
        if tool is not None and hasattr(tool, "on_key"):
            event.ignore()
            tool.on_key(event)
            if event.isAccepted():
                return
        super().keyPressEvent(event)

    def zoom_to_fit(self) -> None:
        self.fitInView(self._map_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_level = 1.0
        self.zoom_changed.emit(self._zoom_level)

    def set_zoom(self, factor: float) -> None:
        self.resetTransform()
        self.scale(factor, factor)
        self._zoom_level = factor
        self.zoom_changed.emit(self._zoom_level)
