"""Timeline panel for managing frame build order.

Supports drag-drop reorder, multi-select, merge, split, group, and playback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import (
    Qt, QAbstractListModel, QModelIndex, QMimeData, QByteArray, QEvent,
    pyqtSignal, QTimer, QItemSelection, QItemSelectionModel,
)
from PyQt6.QtGui import QIcon, QPixmap, QColor, QAction, QUndoStack, QKeyEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListView, QPushButton,
    QLabel, QMenu, QAbstractItemView, QStyledItemDelegate,
    QStyleOptionViewItem, QInputDialog, QToolBar, QCheckBox,
)

if TYPE_CHECKING:
    from improved_aiv_editor.models.aiv_document import AivDocument
    from improved_aiv_editor.models.building_registry import BuildingRegistry

from improved_aiv_editor.i18n import tr
from improved_aiv_editor.models.commands import (
    MergeFramesCommand, SplitFrameCommand, ReorderFramesCommand,
    DeleteFramesCommand, OffsetPositionsCommand, SetShouldPauseCommand,
)
from improved_aiv_editor.views.map_canvas import CATEGORY_COLORS


class FrameListModel(QAbstractListModel):
    """Model exposing document frames to QListView with drag-drop support."""

    def __init__(
        self,
        document: "AivDocument",
        registry: "BuildingRegistry",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._doc = document
        self._registry = registry
        document.frame_inserting.connect(self._on_frame_inserting)
        document.frame_added.connect(self._on_frame_inserted)
        document.frame_removing.connect(self._on_frame_removing)
        document.frame_removed.connect(self._on_frame_removed)
        document.frames_reordered.connect(self._on_frames_reordered)
        document.frames_changed.connect(self._on_frames_changed)

    def _on_frame_inserting(self, index: int) -> None:
        self.beginInsertRows(QModelIndex(), index, index)

    def _on_frame_inserted(self, index: int) -> None:
        self.endInsertRows()

    def _on_frame_removing(self, index: int) -> None:
        self.beginRemoveRows(QModelIndex(), index, index)

    def _on_frame_removed(self, index: int) -> None:
        self.endRemoveRows()

    def _on_frames_reordered(self) -> None:
        self.beginResetModel()
        self.endResetModel()

    def _on_frames_changed(self) -> None:
        if self.rowCount() == 0:
            return
        top = QModelIndex()
        self.dataChanged.emit(
            self.index(0, 0, top),
            self.index(self.rowCount() - 1, 0, top),
            [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole],
        )

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return self._doc.frame_count()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        frame = self._doc.frames[index.row()]
        bdef = self._registry.get_by_id(frame.item_type)
        name = bdef.display_name() if bdef else f"Unknown ({frame.item_type})"

        if role == Qt.ItemDataRole.DisplayRole:
            pos_count = len(frame.positions)
            pause_marker = " [P]" if frame.should_pause else ""
            return f"#{index.row()} {name} ({pos_count}){pause_marker}"

        if role == Qt.ItemDataRole.ToolTipRole:
            if bdef:
                return f"{bdef.name_de} (ID: {bdef.id}, {bdef.width}x{bdef.height})"
            return f"ID: {frame.item_type}"

        if role == Qt.ItemDataRole.DecorationRole:
            if bdef:
                pixmap = bdef.get_pixmap(self._registry.assets_dir)
                if pixmap is not None:
                    return QIcon(pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio))
            return None

        if role == Qt.ItemDataRole.BackgroundRole:
            if bdef:
                color = CATEGORY_COLORS.get(bdef.category)
                if color:
                    bg = QColor(color)
                    bg.setAlpha(60)
                    return bg
            return None

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        default = super().flags(index)
        if index.isValid():
            return default | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled
        return default | Qt.ItemFlag.ItemIsDropEnabled

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:
        return ["application/x-aiv-frame-indices"]

    def mimeData(self, indexes: list[QModelIndex]) -> QMimeData:
        data = QMimeData()
        indices_str = ",".join(str(idx.row()) for idx in indexes if idx.isValid())
        data.setData("application/x-aiv-frame-indices", QByteArray(indices_str.encode()))
        return data

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        if action != Qt.DropAction.MoveAction:
            return False
        raw = data.data("application/x-aiv-frame-indices").data().decode()
        if not raw:
            return False
        indices = [int(x) for x in raw.split(",")]
        target = row if row >= 0 else self.rowCount()
        self._doc.reorder_frames(indices, target)
        return True


class TimelinePanel(QWidget):
    """Timeline panel widget with frame list and control buttons."""

    frame_selection_changed = pyqtSignal(list)
    playback_frame = pyqtSignal(int)

    def __init__(
        self,
        registry: "BuildingRegistry",
        undo_stack: QUndoStack,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self._undo_stack = undo_stack
        self._document: Optional["AivDocument"] = None
        self._model: Optional[FrameListModel] = None
        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(300)
        self._playback_timer.timeout.connect(self._playback_step)
        self._playback_index = 0
        self._playing = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._stats_label = QLabel(tr("No document loaded"))
        layout.addWidget(self._stats_label)

        toolbar = QToolBar()
        toolbar.setIconSize(toolbar.iconSize())

        self._btn_merge = QAction(tr("Merge"), self)
        self._btn_merge.setToolTip(tr("Merge selected frames of same type"))
        self._btn_merge.triggered.connect(self._on_merge)
        toolbar.addAction(self._btn_merge)

        self._btn_split = QAction(tr("Split"), self)
        self._btn_split.setToolTip(tr("Split selected frame into individual positions"))
        self._btn_split.triggered.connect(self._on_split)
        toolbar.addAction(self._btn_split)

        self._btn_delete = QAction(tr("Delete"), self)
        self._btn_delete.setToolTip(tr("Delete selected frames"))
        self._btn_delete.triggered.connect(self._on_delete)
        toolbar.addAction(self._btn_delete)

        toolbar.addSeparator()

        self._btn_offset = QAction(tr("Offset"), self)
        self._btn_offset.setToolTip(tr("Shift positions of selected frames"))
        self._btn_offset.triggered.connect(self._on_offset)
        toolbar.addAction(self._btn_offset)

        toolbar.addSeparator()

        self._btn_play = QAction(tr("Play"), self)
        self._btn_play.setToolTip(tr("Step through build order"))
        self._btn_play.triggered.connect(self._toggle_playback)
        toolbar.addAction(self._btn_play)

        layout.addWidget(toolbar)

        self._list_view = QListView()
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list_view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list_view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._on_context_menu)
        self._list_view.installEventFilter(self)
        layout.addWidget(self._list_view)

    def set_document(self, document: Optional["AivDocument"]) -> None:
        self._document = document
        if document is not None:
            self._model = FrameListModel(document, self._registry, self)
            self._list_view.setModel(self._model)
            sel_model = self._list_view.selectionModel()
            if sel_model:
                sel_model.selectionChanged.connect(self._on_selection_changed)
            self._update_stats()
            document.frames_changed.connect(self._update_stats)
        else:
            self._list_view.setModel(None)
            self._model = None
            self._stats_label.setText(tr("No document loaded"))

    def _update_stats(self) -> None:
        if self._document:
            count = self._document.frame_count()
            self._stats_label.setText(f"{count} frames")

    def _selected_indices(self) -> list[int]:
        sel = self._list_view.selectionModel()
        if sel is None:
            return []
        return sorted(idx.row() for idx in sel.selectedIndexes())

    def _on_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        indices = self._selected_indices()
        self.frame_selection_changed.emit(indices)

    def select_frames(self, indices: list[int]) -> None:
        """Programmatically select frames (e.g. from map selection)."""
        sel_model = self._list_view.selectionModel()
        if sel_model is None or self._model is None:
            return
        sel_model.clearSelection()
        for idx in indices:
            model_idx = self._model.index(idx, 0)
            sel_model.select(model_idx, QItemSelectionModel.SelectionFlag.Select)

    def _on_merge(self) -> None:
        if not self._document:
            return
        indices = self._selected_indices()
        if len(indices) < 2:
            return
        cmd = MergeFramesCommand(self._document, indices)
        self._undo_stack.push(cmd)

    def _on_split(self) -> None:
        if not self._document:
            return
        indices = self._selected_indices()
        if len(indices) != 1:
            return
        cmd = SplitFrameCommand(self._document, indices[0])
        self._undo_stack.push(cmd)

    def _on_delete(self) -> None:
        if not self._document:
            return
        indices = self._selected_indices()
        if not indices:
            return
        keep_indices = [i for i in indices if self._document.frames[i].item_type == 61]
        if keep_indices:
            indices = [i for i in indices if i not in keep_indices]
        if not indices:
            return
        cmd = DeleteFramesCommand(self._document, indices)
        self._undo_stack.push(cmd)

    def _on_offset(self) -> None:
        if not self._document:
            return
        indices = self._selected_indices()
        if not indices:
            return
        dx, ok1 = QInputDialog.getInt(self, tr("Offset X"), tr("Delta X:"), 0, -97, 97)
        if not ok1:
            return
        dy, ok2 = QInputDialog.getInt(self, tr("Offset Y"), tr("Delta Y:"), 0, -97, 97)
        if not ok2:
            return
        if dx == 0 and dy == 0:
            return
        cmd = OffsetPositionsCommand(self._document, indices, dx, dy)
        self._undo_stack.push(cmd)

    def _toggle_playback(self) -> None:
        if self._playing:
            self._playback_timer.stop()
            self._playing = False
            self._btn_play.setText(tr("Play"))
        else:
            self._playback_index = 0
            self._playing = True
            self._btn_play.setText(tr("Stop"))
            self._playback_timer.start()

    def _playback_step(self) -> None:
        if not self._document:
            self._toggle_playback()
            return
        count = self._document.frame_count()
        if self._playback_index >= count:
            self._toggle_playback()
            return
        self.playback_frame.emit(self._playback_index)
        sel_model = self._list_view.selectionModel()
        if sel_model and self._model:
            sel_model.clearSelection()
            model_idx = self._model.index(self._playback_index, 0)
            sel_model.select(model_idx, QItemSelectionModel.SelectionFlag.Select)
            self._list_view.scrollTo(model_idx)
        self._playback_index += 1

    def _on_context_menu(self, pos: object) -> None:
        indices = self._selected_indices()
        menu = QMenu(self)

        if len(indices) >= 2:
            types = {self._document.frames[i].item_type for i in indices} if self._document else set()
            if len(types) == 1:
                merge_action = menu.addAction(tr("Merge Frames"))
                merge_action.triggered.connect(self._on_merge)

        if len(indices) == 1 and self._document:
            frame = self._document.frames[indices[0]]
            if len(frame.positions) > 1:
                split_action = menu.addAction(tr("Split Frame"))
                split_action.triggered.connect(self._on_split)

        if indices:
            menu.addSeparator()
            offset_action = menu.addAction(tr("Offset Positions..."))
            offset_action.triggered.connect(self._on_offset)

            pause_action = menu.addAction(tr("Toggle Pause"))
            pause_action.triggered.connect(self._on_toggle_pause)

            menu.addSeparator()
            del_action = menu.addAction(tr("Delete"))
            del_action.triggered.connect(self._on_delete)

        if menu.actions():
            menu.exec(self._list_view.mapToGlobal(pos))  # type: ignore[arg-type]

    def _on_toggle_pause(self) -> None:
        if not self._document:
            return
        indices = self._selected_indices()
        for idx in indices:
            new_val = not self._document.frames[idx].should_pause
            cmd = SetShouldPauseCommand(self._document, idx, new_val)
            self._undo_stack.push(cmd)

    def refresh_language(self) -> None:
        self._btn_merge.setText(tr("Merge"))
        self._btn_merge.setToolTip(tr("Merge selected frames of same type"))
        self._btn_split.setText(tr("Split"))
        self._btn_split.setToolTip(tr("Split selected frame into individual positions"))
        self._btn_delete.setText(tr("Delete"))
        self._btn_delete.setToolTip(tr("Delete selected frames"))
        self._btn_offset.setText(tr("Offset"))
        self._btn_offset.setToolTip(tr("Shift positions of selected frames"))
        self._btn_play.setText(tr("Stop") if self._playing else tr("Play"))
        self._btn_play.setToolTip(tr("Step through build order"))
        self._update_stats()
        if self._model:
            self._model.beginResetModel()
            self._model.endResetModel()

    # ---------------------------------------------------------- keyboard shortcuts

    def eventFilter(self, obj: object, event: QEvent) -> bool:
        if obj is self._list_view and event.type() == QEvent.Type.KeyPress:
            key_event = event  # type: QKeyEvent
            alt = bool(key_event.modifiers() & Qt.KeyboardModifier.AltModifier)

            if key_event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and not alt:
                self._on_delete()
                return True

            if alt and key_event.key() == Qt.Key.Key_Up:
                self._on_move_up()
                return True

            if alt and key_event.key() == Qt.Key.Key_Down:
                self._on_move_down()
                return True

        return super().eventFilter(obj, event)

    def _on_move_up(self) -> None:
        if not self._document:
            return
        indices = self._selected_indices()
        if not indices or min(indices) <= 0:
            return
        new_start = min(indices) - 1
        cmd = ReorderFramesCommand(self._document, indices, new_start)
        self._undo_stack.push(cmd)
        new_positions = list(range(new_start, new_start + len(indices)))
        self.select_frames(new_positions)

    def _on_move_down(self) -> None:
        if not self._document:
            return
        indices = self._selected_indices()
        total = self._document.frame_count()
        if not indices or max(indices) >= total - 1:
            return
        new_start = min(indices) + 1
        cmd = ReorderFramesCommand(self._document, indices, new_start)
        self._undo_stack.push(cmd)
        new_positions = list(range(new_start, new_start + len(indices)))
        self.select_frames(new_positions)
