"""Abstract base class for map editing tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QCursor

if TYPE_CHECKING:
    from improved_aiv_editor.views.map_canvas import MapScene, MapCanvas
    from improved_aiv_editor.models.aiv_document import AivDocument
    from improved_aiv_editor.models.building_registry import BuildingRegistry
    from PyQt6.QtGui import QUndoStack


class BaseTool(ABC):
    """Interface that all map editing tools implement."""

    def __init__(
        self,
        scene: "MapScene",
        canvas: "MapCanvas",
        document: "AivDocument",
        registry: "BuildingRegistry",
        undo_stack: "QUndoStack",
    ) -> None:
        self._scene = scene
        self._canvas = canvas
        self._document = document
        self._registry = registry
        self._undo_stack = undo_stack

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def activate(self) -> None:
        """Called when this tool becomes active."""
        pass

    def deactivate(self) -> None:
        """Called when switching away from this tool."""
        self._scene.clear_ghost()

    @abstractmethod
    def on_press(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        ...

    @abstractmethod
    def on_move(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        ...

    @abstractmethod
    def on_release(self, scene_pos: QPointF, event: QMouseEvent) -> None:
        ...

    def on_key(self, event: QKeyEvent) -> None:
        pass

    def cursor(self) -> Qt.CursorShape:
        return Qt.CursorShape.ArrowCursor
