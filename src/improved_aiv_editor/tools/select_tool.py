"""Select tool for clicking, rubber-band (marquee) selecting, and moving buildings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QPointF, Qt, QRectF
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QUndoStack, QPen, QBrush, QColor
from PyQt6.QtWidgets import QGraphicsRectItem, QGraphicsView

from improved_aiv_editor.tools.base_tool import BaseTool
from improved_aiv_editor.models.commands import MoveBuildingsCommand, DeleteFramesCommand, DeletePositionsCommand
from improved_aiv_editor.views.map_canvas import (
    BuildingGraphicsItem, WallSegmentItem, KeepGraphicsItem,
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
        self._drag_items: list[BuildingGraphicsItem | WallSegmentItem | KeepGraphicsItem] = []
        self._drag_start_tile: Optional[tuple[int, int]] = None

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
        self._clear_rubber_band()

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
        if item is not None and isinstance(item, (BuildingGraphicsItem, WallSegmentItem, KeepGraphicsItem)):
            self._clear_rubber_band()

            if not item.isSelected():
                if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    self._scene.clearSelection()
                item.setSelected(True)

            self._dragging = True
            self._drag_start = scene_pos
            self._drag_start_tile = self._scene.scene_to_tile(scene_pos)
            self._drag_items = [
                i for i in self._scene.selectedItems()
                if isinstance(i, (BuildingGraphicsItem, WallSegmentItem, KeepGraphicsItem))
            ]
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

            if dtx != 0 or dty != 0:
                moves: list[tuple[int, int, int, int]] = []
                for item in self._drag_items:
                    moves.append((item.frame_index, item.pos_index, dtx, dty))

                if moves:
                    cmd = MoveBuildingsCommand(self._document, moves)
                    self._undo_stack.push(cmd)
                else:
                    for item in self._drag_items:
                        item.setPos(item.tile_x * TILE_SIZE, item.tile_y * TILE_SIZE)
            else:
                for item in self._drag_items:
                    item.setPos(item.tile_x * TILE_SIZE, item.tile_y * TILE_SIZE)

            self._dragging = False
            self._drag_start = None
            self._drag_items = []
            self._drag_start_tile = None

        elif self._rubber_origin is not None:
            rect = QRectF(self._rubber_origin, scene_pos).normalized()
            self._scene.select_buildings_in_rect(rect, self._rubber_additive)
            self._clear_rubber_band()

    def on_key(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected = self._scene.get_selected_buildings()
            if not selected:
                return
            items = [
                item for item in selected
                if isinstance(item, (BuildingGraphicsItem, WallSegmentItem, KeepGraphicsItem))
                and item.building_def.id != 61
            ]
            if not items:
                event.accept()
                return

            selected_by_frame: dict[int, set[int]] = {}
            for item in items:
                selected_by_frame.setdefault(item.frame_index, set()).add(item.pos_index)

            full_delete: list[int] = []
            partial_removals: dict[int, set[int]] = {}
            for fi, pos_indices in selected_by_frame.items():
                frame = self._document.frames[fi]
                if len(pos_indices) >= len(frame.positions):
                    full_delete.append(fi)
                else:
                    partial_removals[fi] = pos_indices

            if partial_removals and not full_delete:
                cmd = DeletePositionsCommand(self._document, partial_removals)
                self._undo_stack.push(cmd)
            elif full_delete and not partial_removals:
                cmd = DeleteFramesCommand(self._document, full_delete)
                self._undo_stack.push(cmd)
            elif full_delete or partial_removals:
                combined = dict(partial_removals)
                for fi in full_delete:
                    frame = self._document.frames[fi]
                    combined[fi] = set(range(len(frame.positions)))
                cmd = DeletePositionsCommand(self._document, combined)
                self._undo_stack.push(cmd)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self._clear_rubber_band()
            event.accept()

    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.ArrowCursor
