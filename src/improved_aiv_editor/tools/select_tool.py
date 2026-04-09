"""Select tool for clicking, rubber-band (marquee) selecting, and moving buildings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QPointF, Qt, QRectF
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QUndoStack, QPen, QBrush, QColor
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsView, QGraphicsItem

from improved_aiv_editor.tools.base_tool import BaseTool
from improved_aiv_editor.models.commands import (
    MoveBuildingsCommand, DeleteFramesCommand, DeletePositionsCommand,
    PlaceBuildingCommand,
)
from improved_aiv_editor.views.map_canvas import (
    BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem,
    TILE_SIZE, MapScene, MapCanvas,
)

if TYPE_CHECKING:
    from improved_aiv_editor.models.aiv_document import AivDocument
    from improved_aiv_editor.models.building_registry import BuildingRegistry


class SelectTool(BaseTool):
    def __init__(
        self,
        scene: MapScene,
        canvas: MapCanvas,
        document: "AivDocument",
        registry: "BuildingRegistry",
        undo_stack: QUndoStack,
    ) -> None:
        super().__init__(scene, canvas, document, registry, undo_stack)
        self._dragging = False
        self._drag_start: Optional[QPointF] = None
        self._drag_items: list[BuildingGraphicsItem | GatehouseGraphicsItem | WallSegmentItem | KeepGraphicsItem] = []
        self._drag_start_tile: Optional[tuple[int, int]] = None

        self._clone_drag: bool = False
        self._clone_ghosts: list[QGraphicsItem] = []

        self._rubber_origin: Optional[QPointF] = None
        self._rubber_additive: bool = False
        self._rubber_item: Optional[QGraphicsRectItem] = None

    def activate(self) -> None:
        self._canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._canvas.setCursor(Qt.CursorShape.ArrowCursor)

    def deactivate(self) -> None:
        super().deactivate()
        self._canvas.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._dragging = False
        self._clear_clone_ghosts()
        self._clear_rubber_band()

    def _create_clone_ghosts(self) -> None:
        """Create semi-transparent copies of drag items for visual clone feedback."""
        self._clear_clone_ghosts()
        for item in self._drag_items:
            rect = item.boundingRect()
            ghost = QGraphicsRectItem(rect)
            brush = item.brush()
            color = QColor(brush.color())
            color.setAlpha(100)
            ghost.setBrush(QBrush(color))
            ghost.setPen(QPen(color.darker(130), 1.0, Qt.PenStyle.DashLine))
            ghost.setPos(item.pos())
            ghost.setZValue(15000)
            self._scene.addItem(ghost)
            self._clone_ghosts.append(ghost)

    def _clear_clone_ghosts(self) -> None:
        for ghost in self._clone_ghosts:
            self._scene.removeItem(ghost)
        self._clone_ghosts.clear()

    def _clear_rubber_band(self) -> None:
        if self._rubber_item is not None:
            self._scene.removeItem(self._rubber_item)
            self._rubber_item = None
        self._rubber_origin = None

    def _update_rubber_band(self, scene_pos: QPointF) -> None:
        if self._rubber_origin is None:
            return
        rect = QRectF(self._rubber_origin, scene_pos).normalized()
        if self._rubber_item is None:
            self._rubber_item = QGraphicsRectItem(rect)
            self._rubber_item.setPen(
                QPen(QColor(40, 120, 255, 220), 1.0, Qt.PenStyle.DashLine)
            )
            self._rubber_item.setBrush(QBrush(QColor(40, 120, 255, 45)))
            self._rubber_item.setZValue(20000)
            self._scene.addItem(self._rubber_item)
        else:
            self._rubber_item.setRect(rect)

    def on_press(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        item = self._scene.get_building_at(scene_pos)
        if item is not None and isinstance(item, (BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem)):
            self._clear_rubber_band()

            if not item.isSelected():
                if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    self._scene.clearSelection()
                item.setSelected(True)

            self._dragging = True
            self._clone_drag = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            self._drag_start = scene_pos
            self._drag_start_tile = self._scene.scene_to_tile(scene_pos)
            self._drag_items = [
                i for i in self._scene.selectedItems()
                if isinstance(i, (BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem))
            ]
            if self._clone_drag:
                self._create_clone_ghosts()
        else:
            self._dragging = False
            self._rubber_additive = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            if not self._rubber_additive:
                self._scene.clearSelection()
            if self._rubber_item is not None:
                self._scene.removeItem(self._rubber_item)
                self._rubber_item = None
            self._rubber_origin = QPointF(scene_pos)
            self._update_rubber_band(scene_pos)

    def on_move(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if self._dragging and self._drag_start is not None:
            dx = scene_pos.x() - self._drag_start.x()
            dy = scene_pos.y() - self._drag_start.y()
            if self._clone_ghosts:
                for ghost, item in zip(self._clone_ghosts, self._drag_items):
                    ghost.setPos(
                        item.tile_x * TILE_SIZE + dx,
                        item.tile_y * TILE_SIZE + dy,
                    )
            else:
                for item in self._drag_items:
                    item.setPos(
                        item.tile_x * TILE_SIZE + dx,
                        item.tile_y * TILE_SIZE + dy,
                    )
            return

        if self._rubber_origin is not None:
            if not (event.buttons() & Qt.MouseButton.LeftButton):
                return
            self._update_rubber_band(scene_pos)

    def on_release(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._dragging and self._drag_start_tile is not None:
            end_tile = self._scene.scene_to_tile(scene_pos)
            dtx = end_tile[0] - self._drag_start_tile[0]
            dty = end_tile[1] - self._drag_start_tile[1]

            clone = self._clone_drag or bool(
                event.modifiers() & Qt.KeyboardModifier.AltModifier
            )

            if dtx != 0 or dty != 0:
                if clone:
                    self._finish_clone_drag(dtx, dty)
                else:
                    moves: list[tuple[int, int, int, int]] = []
                    for item in self._drag_items:
                        moves.append((item.frame_id, item.pos_index, dtx, dty))

                    if moves:
                        cmd = MoveBuildingsCommand(self._document, moves)
                        self._undo_stack.push(cmd)
                    else:
                        for item in self._drag_items:
                            item.setPos(item.tile_x * TILE_SIZE, item.tile_y * TILE_SIZE)
            else:
                for item in self._drag_items:
                    item.setPos(item.tile_x * TILE_SIZE, item.tile_y * TILE_SIZE)

            self._clear_clone_ghosts()
            self._dragging = False
            self._clone_drag = False
            self._drag_start = None
            self._drag_items = []
            self._drag_start_tile = None

        elif self._rubber_origin is not None:
            rect = QRectF(self._rubber_origin, scene_pos).normalized()
            self._scene.select_buildings_in_rect(rect, self._rubber_additive)
            self._clear_rubber_band()

    def _finish_clone_drag(self, dtx: int, dty: int) -> None:
        """Create duplicated frames at the offset position."""
        by_frame: dict[int, list[tuple[int, int]]] = {}
        for item in self._drag_items:
            if item.building_def.id == 61:
                continue
            by_frame.setdefault(item.frame_id, []).append(
                (item.tile_x + dtx, item.tile_y + dty)
            )

        if not by_frame:
            return

        self._undo_stack.beginMacro("Duplicate Buildings")
        for frame_id, new_positions in by_frame.items():
            frame = self._document.frame_by_id(frame_id)
            cmd = PlaceBuildingCommand(
                self._document, frame.item_type, new_positions,
                should_pause=frame.should_pause,
            )
            self._undo_stack.push(cmd)
        self._undo_stack.endMacro()

    def on_key(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected = self._scene.get_selected_buildings()
            if not selected:
                return
            items = [
                item for item in selected
                if isinstance(item, (BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem))
                and item.building_def.id != 61
            ]
            if not items:
                event.accept()
                return

            selected_by_frame: dict[int, set[int]] = {}
            for item in items:
                selected_by_frame.setdefault(item.frame_id, set()).add(item.pos_index)

            full_delete: list[int] = []
            partial_removals: dict[int, set[int]] = {}
            for fid, pos_indices in selected_by_frame.items():
                frame = self._document.frame_by_id(fid)
                if len(pos_indices) >= len(frame.positions):
                    full_delete.append(self._document.order_of(fid))
                else:
                    partial_removals[fid] = pos_indices

            if partial_removals and not full_delete:
                cmd = DeletePositionsCommand(self._document, partial_removals)
                self._undo_stack.push(cmd)
            elif full_delete and not partial_removals:
                cmd = DeleteFramesCommand(self._document, full_delete)
                self._undo_stack.push(cmd)
            elif full_delete or partial_removals:
                combined = dict(partial_removals)
                for order_idx in full_delete:
                    fid = self._document.frame_id_at(order_idx)
                    frame = self._document.frame_by_id(fid)
                    combined[fid] = set(range(len(frame.positions)))
                cmd = DeletePositionsCommand(self._document, combined)
                self._undo_stack.push(cmd)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self._clear_rubber_band()
            event.accept()

    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.ArrowCursor
