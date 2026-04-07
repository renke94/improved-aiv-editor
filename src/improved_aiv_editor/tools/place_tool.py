"""Place tool for adding new buildings to the map."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QUndoStack

from improved_aiv_editor.tools.base_tool import BaseTool
from improved_aiv_editor.models.commands import PlaceBuildingCommand
from improved_aiv_editor.views.map_canvas import TILE_SIZE, MapScene, MapCanvas

if TYPE_CHECKING:
    from improved_aiv_editor.models.aiv_document import AivDocument
    from improved_aiv_editor.models.building_registry import BuildingRegistry, BuildingDef


class PlaceTool(BaseTool):
    """Tool for placing buildings on the map with ghost preview."""

    def __init__(
        self,
        scene: MapScene,
        canvas: MapCanvas,
        document: "AivDocument",
        registry: "BuildingRegistry",
        undo_stack: QUndoStack,
    ) -> None:
        super().__init__(scene, canvas, document, registry, undo_stack)
        self._active_building_id: Optional[int] = None
        self._active_building: Optional["BuildingDef"] = None

    def set_building(self, building_id: int) -> None:
        self._active_building_id = building_id
        self._active_building = self._registry.get_by_id(building_id)
        if self._active_building:
            self._scene.set_ghost(self._active_building)

    def activate(self) -> None:
        self._canvas.setCursor(Qt.CursorShape.CrossCursor)
        if self._active_building:
            self._scene.set_ghost(self._active_building)

    def deactivate(self) -> None:
        super().deactivate()
        self._canvas.setCursor(Qt.CursorShape.ArrowCursor)

    def on_press(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._active_building is None:
            return
        if self._active_building.fixed_position:
            return

        tx, ty = self._scene.scene_to_tile(scene_pos)
        bdef = self._active_building
        if not self._scene.can_place_building(bdef, tx, ty):
            return
        ft = bdef.file_item_type()
        if bdef.kind == "moat":
            positions = [
                (tx + dx, ty + dy)
                for dy in range(bdef.height)
                for dx in range(bdef.width)
            ]
        else:
            positions = [(tx, ty)]
        cmd = PlaceBuildingCommand(self._document, ft, positions)
        self._undo_stack.push(cmd)

    def on_move(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if self._active_building is None:
            return
        tx, ty = self._scene.scene_to_tile(scene_pos)
        self._scene.update_ghost_position(tx, ty)

    def on_release(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        pass

    def on_key(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._active_building = None
            self._active_building_id = None
            self._scene.clear_ghost()
            event.accept()

    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.CrossCursor
