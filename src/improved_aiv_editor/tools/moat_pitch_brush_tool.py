"""Drag-to-paint moat and pitch ditch (any footprint) with live preview."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QUndoStack, QPen, QColor
from PyQt6.QtWidgets import QGraphicsRectItem

from improved_aiv_editor.tools.base_tool import BaseTool
from improved_aiv_editor.models.commands import PlaceBuildingCommand
from improved_aiv_editor.utils.tile_line import bresenham_line
from improved_aiv_editor.views.map_canvas import TILE_SIZE, MAP_SIZE, MapScene, MapCanvas

if TYPE_CHECKING:
    from improved_aiv_editor.models.aiv_document import AivDocument
    from improved_aiv_editor.models.building_registry import BuildingRegistry, BuildingDef


class MoatPitchBrushTool(BaseTool):
    """Stamp moat footprints along a stroke (Bresenham between drag samples)."""

    def __init__(
        self,
        scene: MapScene,
        canvas: MapCanvas,
        document: "AivDocument",
        registry: "BuildingRegistry",
        undo_stack: QUndoStack,
    ) -> None:
        super().__init__(scene, canvas, document, registry, undo_stack)
        self._active_building: Optional["BuildingDef"] = None
        self._last_tile: Optional[tuple[int, int]] = None
        self._stroke_cells: set[tuple[int, int]] = set()
        self._preview_items: list[QGraphicsRectItem] = []

    def set_building(self, building_id: int) -> None:
        self._active_building = self._registry.get_by_id(building_id)

    def activate(self) -> None:
        self._canvas.setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self) -> None:
        super().deactivate()
        self._canvas.setCursor(Qt.CursorShape.ArrowCursor)
        self._cancel_stroke()

    def _cancel_stroke(self) -> None:
        self._last_tile = None
        self._stroke_cells.clear()
        for p in self._preview_items:
            self._scene.removeItem(p)
        self._preview_items.clear()

    @staticmethod
    def _footprint_tiles(ox: int, oy: int, bdef: "BuildingDef") -> list[tuple[int, int]]:
        return [
            (ox + dx, oy + dy)
            for dy in range(bdef.height)
            for dx in range(bdef.width)
        ]

    def _try_stamp(self, ox: int, oy: int) -> bool:
        """Paint individual cells within the brush footprint around (ox, oy).

        Each cell is tested independently so the brush fills in new pixels
        continuously as the cursor moves, like a drawing application.
        """
        bdef = self._active_building
        if bdef is None:
            return False
        cells = self._footprint_tiles(ox, oy, bdef)
        painted_any = False
        ft = bdef.file_item_type()
        for px, py in cells:
            if (px, py) in self._stroke_cells:
                continue
            if px < 1 or px > MAP_SIZE or py < 1 or py > MAP_SIZE:
                continue
            if not self._scene.is_placement_valid(ft, px, py):
                continue
            self._stroke_cells.add((px, py))
            self._add_preview_tile(px, py)
            painted_any = True
        return painted_any

    def _add_preview_tile(self, tx: int, ty: int) -> None:
        r = QGraphicsRectItem(0, 0, TILE_SIZE, TILE_SIZE)
        r.setPos(tx * TILE_SIZE, ty * TILE_SIZE)
        r.setZValue(10001)
        r.setBrush(QColor(60, 180, 255, 90))
        r.setPen(QPen(QColor(40, 120, 255, 200), 1.0, Qt.PenStyle.DashLine))
        self._scene.addItem(r)
        self._preview_items.append(r)

    def on_press(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._active_building is None:
            return
        self._cancel_stroke()
        tx, ty = self._scene.scene_to_tile(scene_pos)
        self._last_tile = (tx, ty)
        self._try_stamp(tx, ty)

    def on_move(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if self._last_tile is None or self._active_building is None:
            return
        tx, ty = self._scene.scene_to_tile(scene_pos)
        if (tx, ty) == self._last_tile:
            return
        lx, ly = self._last_tile
        line = bresenham_line(lx, ly, tx, ty)
        self._last_tile = (tx, ty)
        for ptx, pty in line[1:]:
            self._try_stamp(ptx, pty)

    def on_release(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._active_building is None:
            return
        self._last_tile = None
        cells = list(self._stroke_cells)
        self._cancel_stroke()
        if not cells:
            return
        cells.sort(key=lambda p: (p[1], p[0]))
        ft = self._active_building.file_item_type()
        cmd = PlaceBuildingCommand(self._document, ft, cells)
        self._undo_stack.push(cmd)

    def on_key(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_stroke()
            event.accept()

    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor
