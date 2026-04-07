"""Document model for .aivjson files.

Represents the full state of an AIV castle definition: ordered frames
(building placement steps) and miscellaneous items (units).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from improved_aiv_editor.utils.coordinates import decode_position, encode_position
from improved_aiv_editor.models.tile_grid import TileGrid

if TYPE_CHECKING:
    from improved_aiv_editor.models.building_registry import BuildingRegistry


@dataclass
class Frame:
    item_type: int
    positions: list[tuple[int, int]]
    should_pause: bool = False

    def encoded_positions(self) -> list[int]:
        return [encode_position(x, y) for x, y in self.positions]

    def clone(self) -> Frame:
        return Frame(
            item_type=self.item_type,
            positions=list(self.positions),
            should_pause=self.should_pause,
        )


@dataclass
class MiscItem:
    item_type: int
    position: tuple[int, int]


class AivDocument(QObject):
    """Observable model for an .aivjson file."""

    frames_changed = pyqtSignal()
    frame_inserting = pyqtSignal(int)
    frame_added = pyqtSignal(int)
    frame_removing = pyqtSignal(int)
    frame_removed = pyqtSignal(int)
    frames_reordered = pyqtSignal()
    frame_positions_changed = pyqtSignal(list)
    misc_items_changed = pyqtSignal()
    document_modified = pyqtSignal()
    document_saved = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._frames: list[Frame] = []
        self._misc_items: list[MiscItem] = []
        self._pause_delay_amount: int = 100
        self._file_path: Optional[Path] = None
        self._modified: bool = False
        self._registry: Optional["BuildingRegistry"] = None
        self.tile_grid = TileGrid()

    def set_registry(self, registry: "BuildingRegistry") -> None:
        """Attach building registry and rebuild the spatial index (call after load/new)."""
        self._registry = registry
        self.tile_grid.rebuild(self._frames, registry)

    def _require_registry(self) -> "BuildingRegistry":
        if self._registry is None:
            raise RuntimeError("AivDocument has no registry; call set_registry first")
        return self._registry

    def restore_frames_snapshot(self, frames: list[Frame]) -> None:
        """Replace all frames (e.g. undo); rebuilds tile grid and notifies listeners."""
        self._frames = [f.clone() for f in frames]
        reg = self._registry
        if reg is not None:
            self.tile_grid.rebuild(self._frames, reg)
        self.frames_reordered.emit()
        self._emit_frames_changed()

    def apply_position_moves(
        self,
        moves: list[tuple[int, int, int, int]],
    ) -> None:
        """Apply (frame_index, pos_index, dx, dy) moves; updates tile grid."""
        reg = self._require_registry()
        affected: set[int] = set()
        for frame_idx, pos_idx, dx, dy in moves:
            frame = self._frames[frame_idx]
            old = frame.clone()
            x, y = frame.positions[pos_idx]
            frame.positions[pos_idx] = (x + dx, y + dy)
            self.tile_grid.update_frame_positions(frame_idx, old, frame, reg)
            affected.add(frame_idx)
        self.frame_positions_changed.emit(sorted(affected))
        self._emit_frames_changed()

    # --- Properties ---

    @property
    def frames(self) -> list[Frame]:
        return self._frames

    @property
    def misc_items(self) -> list[MiscItem]:
        return self._misc_items

    @property
    def pause_delay_amount(self) -> int:
        return self._pause_delay_amount

    @pause_delay_amount.setter
    def pause_delay_amount(self, value: int) -> None:
        self._pause_delay_amount = value
        self._mark_modified()

    @property
    def file_path(self) -> Optional[Path]:
        return self._file_path

    @property
    def is_modified(self) -> bool:
        return self._modified

    # --- File I/O ---

    @classmethod
    def from_file(cls, path: Path, parent: Optional[QObject] = None) -> AivDocument:
        doc = cls(parent)
        doc._file_path = path
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        doc._pause_delay_amount = data.get("pauseDelayAmount", 100)

        for frame_data in data.get("frames", []):
            item_type = frame_data["itemType"]
            positions = [
                decode_position(p)
                for p in frame_data.get("tilePositionOfsets", [])
            ]
            should_pause = frame_data.get("shouldPause", False)
            doc._frames.append(Frame(item_type, positions, should_pause))

        for misc_data in data.get("miscItems", []):
            item_type = misc_data["itemType"]
            pos = decode_position(misc_data.get("positionOfset", 0))
            doc._misc_items.append(MiscItem(item_type, pos))

        doc._modified = False
        return doc

    def save(self, path: Optional[Path] = None) -> None:
        save_path = path or self._file_path
        if save_path is None:
            raise ValueError("No file path specified for save")

        data = {
            "pauseDelayAmount": self._pause_delay_amount,
            "frames": [],
            "miscItems": [],
        }

        for frame in self._frames:
            data["frames"].append({
                "itemType": frame.item_type,
                "tilePositionOfsets": frame.encoded_positions(),
                "shouldPause": frame.should_pause,
            })

        for misc in self._misc_items:
            data["miscItems"].append({
                "itemType": misc.item_type,
                "positionOfset": encode_position(*misc.position),
            })

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self._file_path = save_path
        self._modified = False
        self.document_saved.emit()

    # --- Frame manipulation ---

    def add_frame(self, frame: Frame, index: Optional[int] = None) -> int:
        if index is None:
            index = len(self._frames)
        self.frame_inserting.emit(index)
        self._frames.insert(index, frame)
        reg = self._registry
        if reg is not None:
            self.tile_grid.insert_frame(index, frame, reg)
        self.frame_added.emit(index)
        self._emit_frames_changed()
        return index

    def remove_frame(self, index: int) -> Frame:
        frame = self._frames[index]
        self.frame_removing.emit(index)
        reg = self._registry
        if reg is not None:
            self.tile_grid.remove_frame_at(index, frame, reg)
        self._frames.pop(index)
        self.frame_removed.emit(index)
        self._emit_frames_changed()
        return frame

    def move_frame(self, from_index: int, to_index: int) -> None:
        if from_index == to_index:
            return
        frame = self._frames.pop(from_index)
        self._frames.insert(to_index, frame)
        reg = self._registry
        if reg is not None:
            self.tile_grid.rebuild(self._frames, reg)
        self.frames_reordered.emit()
        self._emit_frames_changed()

    def reorder_frames(self, old_indices: list[int], new_start: int) -> None:
        """Move a block of frames (given by old_indices) to start at new_start."""
        old_indices_sorted = sorted(old_indices)
        extracted = [self._frames[i] for i in old_indices_sorted]
        remaining = [f for i, f in enumerate(self._frames) if i not in set(old_indices_sorted)]
        insert_at = min(new_start, len(remaining))
        self._frames = remaining[:insert_at] + extracted + remaining[insert_at:]
        reg = self._registry
        if reg is not None:
            self.tile_grid.rebuild(self._frames, reg)
        self.frames_reordered.emit()
        self._emit_frames_changed()

    def merge_frames(self, indices: list[int]) -> Optional[int]:
        """Merge frames at given indices (must share the same itemType).
        Returns the index of the merged frame, or None if types differ."""
        if not indices:
            return None
        sorted_idx = sorted(indices)
        types = {self._frames[i].item_type for i in sorted_idx}
        if len(types) != 1:
            return None
        item_type = types.pop()
        merged_positions: list[tuple[int, int]] = []
        should_pause = False
        for i in sorted_idx:
            merged_positions.extend(self._frames[i].positions)
            should_pause = should_pause or self._frames[i].should_pause

        for i in reversed(sorted_idx):
            self._frames.pop(i)

        merged = Frame(item_type, merged_positions, should_pause)
        insert_at = min(sorted_idx[0], len(self._frames))
        self._frames.insert(insert_at, merged)
        reg = self._registry
        if reg is not None:
            self.tile_grid.rebuild(self._frames, reg)
        self.frames_reordered.emit()
        self._emit_frames_changed()
        return insert_at

    def split_frame(self, index: int) -> list[int]:
        """Split a multi-position frame into individual frames. Returns new indices."""
        frame = self._frames[index]
        if len(frame.positions) <= 1:
            return [index]
        self._frames.pop(index)
        new_indices = []
        for i, pos in enumerate(frame.positions):
            new_frame = Frame(frame.item_type, [pos], frame.should_pause)
            insert_at = index + i
            self._frames.insert(insert_at, new_frame)
            new_indices.append(insert_at)
        reg = self._registry
        if reg is not None:
            self.tile_grid.rebuild(self._frames, reg)
        self.frames_reordered.emit()
        self._emit_frames_changed()
        return new_indices

    def offset_positions(self, frame_indices: list[int], dx: int, dy: int) -> None:
        """Shift all positions in the given frames by (dx, dy)."""
        reg = self._require_registry()
        changed: list[int] = []
        for idx in frame_indices:
            old = self._frames[idx].clone()
            frame = self._frames[idx]
            frame.positions = [(x + dx, y + dy) for x, y in frame.positions]
            self.tile_grid.update_frame_positions(idx, old, frame, reg)
            changed.append(idx)
        self.frame_positions_changed.emit(changed)
        self._emit_frames_changed()

    def remove_positions(self, removals: dict[int, set[int]]) -> None:
        """Remove specific positions from frames. Frames left empty are deleted.

        removals maps frame_index → set of pos_indices to remove.
        """
        reg = self._require_registry()
        frames_to_delete: list[int] = []
        changed: list[int] = []

        for fi in sorted(removals):
            pos_indices = removals[fi]
            frame = self._frames[fi]
            old = frame.clone()
            frame.positions = [
                p for i, p in enumerate(frame.positions) if i not in pos_indices
            ]
            if not frame.positions:
                frames_to_delete.append(fi)
            else:
                self.tile_grid.update_frame_positions(fi, old, frame, reg)
                changed.append(fi)

        for fi in reversed(frames_to_delete):
            self.remove_frame(fi)

        if changed:
            self.frame_positions_changed.emit(changed)
            self._emit_frames_changed()

    def set_should_pause(self, index: int, value: bool) -> None:
        self._frames[index].should_pause = value
        self._emit_frames_changed()

    def frame_count(self) -> int:
        return len(self._frames)

    # --- Misc items ---

    def add_misc_item(self, item: MiscItem) -> None:
        self._misc_items.append(item)
        self._mark_modified()
        self.misc_items_changed.emit()

    def remove_misc_item(self, index: int) -> MiscItem:
        item = self._misc_items.pop(index)
        self._mark_modified()
        self.misc_items_changed.emit()
        return item

    # --- Internal ---

    def _mark_modified(self) -> None:
        if not self._modified:
            self._modified = True
            self.document_modified.emit()

    def _emit_frames_changed(self) -> None:
        self._mark_modified()
        self.frames_changed.emit()

    @staticmethod
    def new_empty(parent: Optional[QObject] = None) -> AivDocument:
        """Create a new empty document with just the Keep at center."""
        doc = AivDocument(parent)
        keep_frame = Frame(item_type=61, positions=[(43, 43)])
        doc._frames.append(keep_frame)
        doc._modified = False
        return doc
