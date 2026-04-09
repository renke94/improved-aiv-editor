"""Ellipse/circle drawing tool for walls and moat."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QUndoStack, QPen, QBrush, QColor
from PyQt6.QtWidgets import QGraphicsEllipseItem

from improved_aiv_editor.tools.base_tool import BaseTool
from improved_aiv_editor.models.commands import PlaceBuildingCommand
from improved_aiv_editor.utils.tile_line import midpoint_ellipse
from improved_aiv_editor.views.map_canvas import TILE_SIZE, MAP_SIZE, MapScene, MapCanvas

if TYPE_CHECKING:
    from improved_aiv_editor.models.aiv_document import AivDocument
    from improved_aiv_editor.models.building_registry import BuildingRegistry, BuildingDef


class EllipseTool(BaseTool):
    """Draw walls or moat in an ellipse/circle.

    Click one corner and drag to the opposite corner to define the
    bounding rectangle.  The ellipse is inscribed in that rectangle.
    Hold Shift while dragging to constrain to a circle.
    """

    def __init__(
        self,
        scene: MapScene,
        canvas: MapCanvas,
        document: "AivDocument",
        registry: "BuildingRegistry",
        undo_stack: QUndoStack,
    ) -> None:
        super().__init__(scene, canvas, document, registry, undo_stack)
        self._building_def: Optional["BuildingDef"] = None
        self._start_tile: Optional[tuple[int, int]] = None
        self._preview: Optional[QGraphicsEllipseItem] = None

    def set_building(self, building_id: int) -> None:
        self._building_def = self._registry.get_by_id(building_id)

    @property
    def building_def(self) -> Optional["BuildingDef"]:
        return self._building_def

    def activate(self) -> None:
        self._canvas.setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self) -> None:
        super().deactivate()
        self._canvas.setCursor(Qt.CursorShape.ArrowCursor)
        self._clear_preview()

    # ------------------------------------------------------------------ events

    def on_press(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._building_def is None:
            return
        self._start_tile = self._scene.scene_to_tile(scene_pos)
        self._clear_preview()
        sx, sy = self._start_tile
        ellipse = QGraphicsEllipseItem(sx * TILE_SIZE, sy * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        ellipse.setPen(QPen(QColor(140, 140, 140, 180), 2.0, Qt.PenStyle.DashLine))
        ellipse.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        ellipse.setZValue(10000)
        self._scene.addItem(ellipse)
        self._preview = ellipse

    def on_move(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if self._start_tile is None or self._preview is None:
            return
        end = self._scene.scene_to_tile(scene_pos)
        cx, cy, rx, ry = self._ellipse_params(end, event)
        self._update_preview(cx, cy, rx, ry)

    def on_release(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._start_tile is None or self._building_def is None:
            self._clear_preview()
            return

        end = self._scene.scene_to_tile(scene_pos)
        cx, cy, rx, ry = self._ellipse_params(end, event)
        self._clear_preview()
        self._start_tile = None

        if rx == 0 and ry == 0:
            return

        raw = midpoint_ellipse(cx, cy, rx, ry)
        ft = self._building_def.file_item_type()
        positions = [
            (px, py) for px, py in raw
            if 1 <= px <= MAP_SIZE and 1 <= py <= MAP_SIZE
            and self._scene.is_placement_valid(ft, px, py)
        ]
        if not positions:
            return
        cmd = PlaceBuildingCommand(self._document, ft, positions)
        self._undo_stack.push(cmd)

    def on_key(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._start_tile = None
            self._clear_preview()
            event.accept()

    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor

    # ---------------------------------------------------------------- helpers

    def _ellipse_params(
        self, end_tile: tuple[int, int], event: QMouseEvent,
    ) -> tuple[int, int, int, int]:
        """Derive (cx, cy, rx, ry) from the bounding rectangle."""
        sx, sy = self._start_tile  # type: ignore[misc]
        ex, ey = end_tile
        dx = ex - sx
        dy = ey - sy
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            side = max(abs(dx), abs(dy))
            dx = side if dx >= 0 else -side
            dy = side if dy >= 0 else -side
        x0 = min(sx, sx + dx)
        y0 = min(sy, sy + dy)
        rx = abs(dx) // 2
        ry = abs(dy) // 2
        cx = x0 + rx
        cy = y0 + ry
        return cx, cy, rx, ry

    def _update_preview(self, cx: int, cy: int, rx: int, ry: int) -> None:
        if self._preview is None:
            return
        self._preview.setRect(
            (cx - rx) * TILE_SIZE,
            (cy - ry) * TILE_SIZE,
            (2 * rx + 1) * TILE_SIZE,
            (2 * ry + 1) * TILE_SIZE,
        )

    def _clear_preview(self) -> None:
        if self._preview is not None:
            self._scene.removeItem(self._preview)
            self._preview = None
