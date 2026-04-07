"""Properties panel showing details of selected frames/buildings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QUndoStack
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QCheckBox,
    QSpinBox, QGroupBox, QScrollArea, QFrame,
)

from improved_aiv_editor.i18n import tr

if TYPE_CHECKING:
    from improved_aiv_editor.models.aiv_document import AivDocument, Frame
    from improved_aiv_editor.models.building_registry import BuildingRegistry, BuildingDef

from improved_aiv_editor.models.commands import SetShouldPauseCommand, OffsetPositionsCommand


class PropertiesPanel(QWidget):
    """Panel showing properties of the current selection."""

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
        self._selected_indices: list[int] = []
        self._updating = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(4, 4, 4, 4)

        self._info_group = QGroupBox(tr("Selection"))
        info_layout = QFormLayout()
        self._lbl_count = QLabel("-")
        self._row_frames = QLabel(tr("Frames:"))
        info_layout.addRow(self._row_frames, self._lbl_count)
        self._lbl_type = QLabel("-")
        self._row_type = QLabel(tr("Type:"))
        info_layout.addRow(self._row_type, self._lbl_type)
        self._lbl_category = QLabel("-")
        self._row_category = QLabel(tr("Category:"))
        info_layout.addRow(self._row_category, self._lbl_category)
        self._lbl_dimensions = QLabel("-")
        self._row_size = QLabel(tr("Size:"))
        info_layout.addRow(self._row_size, self._lbl_dimensions)
        self._lbl_positions = QLabel("-")
        self._row_positions = QLabel(tr("Positions:"))
        info_layout.addRow(self._row_positions, self._lbl_positions)
        self._info_group.setLayout(info_layout)
        self._layout.addWidget(self._info_group)

        self._frame_group = QGroupBox(tr("Frame Properties"))
        frame_layout = QFormLayout()
        self._lbl_frame_index = QLabel("-")
        self._row_index = QLabel(tr("Index:"))
        frame_layout.addRow(self._row_index, self._lbl_frame_index)
        self._chk_pause = QCheckBox()
        self._chk_pause.stateChanged.connect(self._on_pause_changed)
        self._row_pause = QLabel(tr("Should Pause:"))
        frame_layout.addRow(self._row_pause, self._chk_pause)
        self._frame_group.setLayout(frame_layout)
        self._layout.addWidget(self._frame_group)

        self._pos_group = QGroupBox(tr("Position Details"))
        self._pos_layout = QVBoxLayout()
        self._lbl_pos_list = QLabel("-")
        self._lbl_pos_list.setWordWrap(True)
        self._pos_layout.addWidget(self._lbl_pos_list)
        self._pos_group.setLayout(self._pos_layout)
        self._layout.addWidget(self._pos_group)

        self._layout.addStretch()

        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def set_document(self, document: Optional["AivDocument"]) -> None:
        self._document = document
        self._selected_indices = []
        self._update_display()

    def set_selection(self, frame_indices: list[int]) -> None:
        self._selected_indices = list(frame_indices)
        self._update_display()

    def refresh_language(self) -> None:
        self._info_group.setTitle(tr("Selection"))
        self._row_frames.setText(tr("Frames:"))
        self._row_type.setText(tr("Type:"))
        self._row_category.setText(tr("Category:"))
        self._row_size.setText(tr("Size:"))
        self._row_positions.setText(tr("Positions:"))
        self._frame_group.setTitle(tr("Frame Properties"))
        self._row_index.setText(tr("Index:"))
        self._row_pause.setText(tr("Should Pause:"))
        self._pos_group.setTitle(tr("Position Details"))
        self._update_display()

    def _update_display(self) -> None:
        self._updating = True
        try:
            if not self._document or not self._selected_indices:
                self._lbl_count.setText("-")
                self._lbl_type.setText("-")
                self._lbl_category.setText("-")
                self._lbl_dimensions.setText("-")
                self._lbl_positions.setText("-")
                self._lbl_frame_index.setText("-")
                self._chk_pause.setChecked(False)
                self._chk_pause.setEnabled(False)
                self._lbl_pos_list.setText("-")
                return

            count = len(self._selected_indices)
            self._lbl_count.setText(str(count))

            frames = [self._document.frames[i] for i in self._selected_indices if i < self._document.frame_count()]
            if not frames:
                return

            types = {f.item_type for f in frames}
            if len(types) == 1:
                item_type = types.pop()
                bdef = self._registry.get_by_id(item_type)
                if bdef:
                    self._lbl_type.setText(f"{bdef.display_name()} (ID: {bdef.id})")
                    cat = self._registry.get_category(bdef.category)
                    self._lbl_category.setText(cat.display_name() if cat else bdef.category)
                    self._lbl_dimensions.setText(f"{bdef.width} x {bdef.height}")
                else:
                    self._lbl_type.setText(f"Unknown (ID: {item_type})")
                    self._lbl_category.setText("-")
                    self._lbl_dimensions.setText("-")
            else:
                self._lbl_type.setText(f"Mixed ({len(types)} types)")
                self._lbl_category.setText("-")
                self._lbl_dimensions.setText("-")

            total_pos = sum(len(f.positions) for f in frames)
            self._lbl_positions.setText(str(total_pos))

            if count == 1:
                frame = frames[0]
                idx = self._selected_indices[0]
                self._lbl_frame_index.setText(f"#{idx}")
                self._chk_pause.setEnabled(True)
                self._chk_pause.setChecked(frame.should_pause)

                pos_strs = [f"({x}, {y})" for x, y in frame.positions[:20]]
                if len(frame.positions) > 20:
                    pos_strs.append(f"... +{len(frame.positions) - 20} more")
                self._lbl_pos_list.setText("\n".join(pos_strs))
                self._frame_group.setVisible(True)
                self._pos_group.setVisible(True)
            else:
                self._lbl_frame_index.setText(", ".join(f"#{i}" for i in self._selected_indices[:10]))
                self._chk_pause.setEnabled(False)
                self._lbl_pos_list.setText(f"{total_pos} positions across {count} frames")
                self._frame_group.setVisible(True)
                self._pos_group.setVisible(True)
        finally:
            self._updating = False

    def _on_pause_changed(self, state: int) -> None:
        if self._updating:
            return
        if not self._document or len(self._selected_indices) != 1:
            return
        idx = self._selected_indices[0]
        value = state == Qt.CheckState.Checked.value
        cmd = SetShouldPauseCommand(self._document, idx, value)
        self._undo_stack.push(cmd)
