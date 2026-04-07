"""Undo/redo commands for all document mutations."""

from __future__ import annotations

from PyQt6.QtGui import QUndoCommand

from improved_aiv_editor.models.aiv_document import AivDocument, Frame


class PlaceBuildingCommand(QUndoCommand):
    def __init__(
        self,
        document: AivDocument,
        item_type: int,
        positions: list[tuple[int, int]],
        index: int | None = None,
        should_pause: bool = False,
    ) -> None:
        super().__init__("Place Building")
        self._doc = document
        self._frame = Frame(item_type, list(positions), should_pause)
        self._requested_index = index
        self._actual_index: int = -1

    def redo(self) -> None:
        self._actual_index = self._doc.add_frame(self._frame, self._requested_index)

    def undo(self) -> None:
        self._doc.remove_frame(self._actual_index)

    @property
    def frame_index(self) -> int:
        return self._actual_index


class DeleteFramesCommand(QUndoCommand):
    def __init__(self, document: AivDocument, indices: list[int]) -> None:
        super().__init__("Delete Frames")
        self._doc = document
        self._indices = sorted(indices)
        self._removed: list[tuple[int, Frame]] = []

    def redo(self) -> None:
        self._removed.clear()
        for i in reversed(self._indices):
            frame = self._doc.remove_frame(i)
            self._removed.append((i, frame))
        self._removed.reverse()

    def undo(self) -> None:
        for idx, frame in self._removed:
            self._doc.add_frame(frame, idx)


class DeletePositionsCommand(QUndoCommand):
    """Remove specific positions from frames (for partial wall/moat/pitch deletion)."""

    def __init__(
        self,
        document: AivDocument,
        removals: dict[int, set[int]],
    ) -> None:
        """removals: frame_index → set of pos_indices to remove."""
        super().__init__("Delete Positions")
        self._doc = document
        self._removals = {fi: set(pis) for fi, pis in removals.items()}
        self._snapshot_before: list[Frame] = []

    def redo(self) -> None:
        self._snapshot_before = [f.clone() for f in self._doc.frames]
        self._doc.remove_positions(self._removals)

    def undo(self) -> None:
        self._doc.restore_frames_snapshot(self._snapshot_before)


class MoveFrameCommand(QUndoCommand):
    def __init__(self, document: AivDocument, from_index: int, to_index: int) -> None:
        super().__init__("Move Frame")
        self._doc = document
        self._from = from_index
        self._to = to_index

    def redo(self) -> None:
        self._doc.move_frame(self._from, self._to)

    def undo(self) -> None:
        self._doc.move_frame(self._to, self._from)


class ReorderFramesCommand(QUndoCommand):
    def __init__(
        self, document: AivDocument, old_indices: list[int], new_start: int
    ) -> None:
        super().__init__("Reorder Frames")
        self._doc = document
        self._old_indices = list(old_indices)
        self._new_start = new_start
        self._snapshot_before: list[Frame] = []
        self._snapshot_after: list[Frame] = []

    def redo(self) -> None:
        self._snapshot_before = [f.clone() for f in self._doc.frames]
        self._doc.reorder_frames(self._old_indices, self._new_start)
        self._snapshot_after = [f.clone() for f in self._doc.frames]

    def undo(self) -> None:
        self._doc.restore_frames_snapshot(self._snapshot_before)


class MergeFramesCommand(QUndoCommand):
    def __init__(self, document: AivDocument, indices: list[int]) -> None:
        super().__init__("Merge Frames")
        self._doc = document
        self._indices = list(indices)
        self._snapshot_before: list[Frame] = []
        self._merged_index: int | None = None

    def redo(self) -> None:
        self._snapshot_before = [f.clone() for f in self._doc.frames]
        self._merged_index = self._doc.merge_frames(self._indices)

    def undo(self) -> None:
        self._doc.restore_frames_snapshot(self._snapshot_before)


class SplitFrameCommand(QUndoCommand):
    def __init__(self, document: AivDocument, index: int) -> None:
        super().__init__("Split Frame")
        self._doc = document
        self._index = index
        self._snapshot_before: list[Frame] = []

    def redo(self) -> None:
        self._snapshot_before = [f.clone() for f in self._doc.frames]
        self._doc.split_frame(self._index)

    def undo(self) -> None:
        self._doc.restore_frames_snapshot(self._snapshot_before)


class OffsetPositionsCommand(QUndoCommand):
    def __init__(
        self, document: AivDocument, frame_indices: list[int], dx: int, dy: int
    ) -> None:
        super().__init__("Offset Positions")
        self._doc = document
        self._frame_indices = list(frame_indices)
        self._dx = dx
        self._dy = dy

    def redo(self) -> None:
        self._doc.offset_positions(self._frame_indices, self._dx, self._dy)

    def undo(self) -> None:
        self._doc.offset_positions(self._frame_indices, -self._dx, -self._dy)


class SetShouldPauseCommand(QUndoCommand):
    def __init__(self, document: AivDocument, index: int, value: bool) -> None:
        super().__init__("Toggle Pause")
        self._doc = document
        self._index = index
        self._new_value = value
        self._old_value = document.frames[index].should_pause

    def redo(self) -> None:
        self._doc.set_should_pause(self._index, self._new_value)

    def undo(self) -> None:
        self._doc.set_should_pause(self._index, self._old_value)


class MoveBuildingsCommand(QUndoCommand):
    """Move specific position entries within frames by a delta."""

    def __init__(
        self,
        document: AivDocument,
        moves: list[tuple[int, int, int, int]],
    ) -> None:
        """moves: list of (frame_index, position_index_within_frame, dx, dy)"""
        super().__init__("Move Buildings")
        self._doc = document
        self._moves = list(moves)

    def redo(self) -> None:
        self._doc.apply_position_moves(self._moves)

    def undo(self) -> None:
        inv = [(fi, pi, -dx, -dy) for fi, pi, dx, dy in reversed(self._moves)]
        self._doc.apply_position_moves(inv)
