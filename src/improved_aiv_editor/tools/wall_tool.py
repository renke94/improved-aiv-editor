"""Line drawing tool for placing walls or moat along a straight line."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QUndoStack, QPen, QColor
from PyQt6.QtWidgets import QGraphicsLineItem

from improved_aiv_editor.tools.base_tool import BaseTool
from improved_aiv_editor.models.commands import PlaceBuildingCommand
from improved_aiv_editor.utils.tile_line import bresenham_line, thicken_points
from improved_aiv_editor.views.map_canvas import TILE_SIZE, MAP_SIZE, MapScene, MapCanvas

if TYPE_CHECKING:
    from improved_aiv_editor.models.aiv_document import AivDocument
    from improved_aiv_editor.models.building_registry import BuildingRegistry


class WallTool(BaseTool):
    """Draw walls or moat in a straight line: click start, drag to end."""

    def __init__(
        self,
        scene: MapScene,
        canvas: MapCanvas,
        document: "AivDocument",
        registry: "BuildingRegistry",
        undo_stack: QUndoStack,
    ) -> None:
        super().__init__(scene, canvas, document, registry, undo_stack)
        self._building_id: int = 25
        self._thickness: int = 1
        self._start_tile: Optional[tuple[int, int]] = None
        self._preview_line: Optional[QGraphicsLineItem] = None

    def set_wall_type(self, wall_type_id: int) -> None:
        self._building_id = wall_type_id

    def set_building(self, building_id: int) -> None:
        self._building_id = building_id

    def set_thickness(self, thickness: int) -> None:
        self._thickness = max(1, thickness)

    def activate(self) -> None:
        self._canvas.setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self) -> None:
        super().deactivate()
        self._canvas.setCursor(Qt.CursorShape.ArrowCursor)
        self._clear_preview()

    def on_press(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._start_tile = self._scene.scene_to_tile(scene_pos)
        self._clear_preview()
        sx, sy = self._start_tile
        start_x = (sx + 0.5) * TILE_SIZE
        start_y = (sy + 0.5) * TILE_SIZE
        pen_width = max(2.0, self._thickness * TILE_SIZE * 0.8)
        self._preview_line = QGraphicsLineItem(start_x, start_y, start_x, start_y)
        self._preview_line.setPen(QPen(QColor(140, 140, 140, 180), pen_width, Qt.PenStyle.DashLine))
        self._preview_line.setZValue(10000)
        self._scene.addItem(self._preview_line)

    def on_move(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if self._start_tile is None or self._preview_line is None:
            return
        sx, sy = self._start_tile
        ex, ey = self._scene.scene_to_tile(scene_pos)
        self._preview_line.setLine(
            (sx + 0.5) * TILE_SIZE,
            (sy + 0.5) * TILE_SIZE,
            (ex + 0.5) * TILE_SIZE,
            (ey + 0.5) * TILE_SIZE,
        )

    def on_release(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._start_tile is None:
            return

        end_tile = self._scene.scene_to_tile(scene_pos)
        center_line = bresenham_line(
            self._start_tile[0], self._start_tile[1],
            end_tile[0], end_tile[1],
        )
        positions = thicken_points(center_line, self._thickness)

        bdef = self._registry.get_by_id(self._building_id)
        ft = bdef.file_item_type() if bdef else self._building_id
        positions = [
            (px, py) for px, py in positions
            if 1 <= px <= MAP_SIZE and 1 <= py <= MAP_SIZE
            and self._scene.is_placement_valid(ft, px, py)
        ]

        if positions:
            cmd = PlaceBuildingCommand(self._document, ft, positions)
            self._undo_stack.push(cmd)

        self._start_tile = None
        self._clear_preview()

    def on_key(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._start_tile = None
            self._clear_preview()
            event.accept()

    def _clear_preview(self) -> None:
        if self._preview_line is not None:
            self._scene.removeItem(self._preview_line)
            self._preview_line = None

    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor
