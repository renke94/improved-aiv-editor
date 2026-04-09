"""Document model for .aivjson files.

Represents the full state of an AIV castle definition: ordered frames
(building placement steps) and miscellaneous items (units).

Frames are stored in an ID-keyed pool with a separate order list so that
reordering is cheap (just rearranging ints) and the spatial TileGrid
never needs rebuilding on pure reorder operations.
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
    id: int
    item_type: int
    positions: list[tuple[int, int]]
    should_pause: bool = False

    def encoded_positions(self) -> list[int]:
        return [encode_position(x, y) for x, y in self.positions]

    def clone(self) -> Frame:
        return Frame(
            id=self.id,
            item_type=self.item_type,
            positions=list(self.positions),
            should_pause=self.should_pause,
        )


@dataclass
class MiscItem:
    item_type: int
    position: tuple[int, int]


@dataclass
class FramesSnapshot:
    """Complete snapshot of frame state for undo of destructive operations."""
    pool: dict[int, Frame]
    order: list[int]
    next_id: int


class AivDocument(QObject):
    """Observable model for an .aivjson file."""

    frames_changed = pyqtSignal()
    frame_inserting = pyqtSignal(int)   # frame_id
    frame_added = pyqtSignal(int)       # frame_id
    frame_removing = pyqtSignal(int)    # frame_id
    frame_removed = pyqtSignal(int)     # frame_id
    frames_reordered = pyqtSignal()
    frame_positions_changed = pyqtSignal(list)  # list of frame_ids
    misc_items_changed = pyqtSignal()
    document_modified = pyqtSignal()
    document_saved = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._frame_pool: dict[int, Frame] = {}
        self._frame_order: list[int] = []
        self._order_of: dict[int, int] = {}
        self._next_frame_id: int = 0
        self._misc_items: list[MiscItem] = []
        self._pause_delay_amount: int = 100
        self._file_path: Optional[Path] = None
        self._modified: bool = False
        self._registry: Optional["BuildingRegistry"] = None
        self.tile_grid = TileGrid()

    # --- ID helpers ---

    def _alloc_frame_id(self) -> int:
        fid = self._next_frame_id
        self._next_frame_id += 1
        return fid

    def _rebuild_order_lookup(self) -> None:
        self._order_of = {fid: idx for idx, fid in enumerate(self._frame_order)}

    def _register_frame(self, frame: Frame) -> None:
        """Add a frame to the pool and order list (at end). Caller must rebuild lookup."""
        self._frame_pool[frame.id] = frame
        self._frame_order.append(frame.id)

    # --- Public accessors ---

    def frame_by_id(self, frame_id: int) -> Frame:
        return self._frame_pool[frame_id]

    def frame_at(self, index: int) -> Frame:
        return self._frame_pool[self._frame_order[index]]

    def frame_id_at(self, index: int) -> int:
        return self._frame_order[index]

    def order_of(self, frame_id: int) -> int:
        return self._order_of[frame_id]

    @property
    def frame_order(self) -> list[int]:
        """Current build order as a list of frame IDs (read-only snapshot)."""
        return list(self._frame_order)

    @property
    def order_lookup(self) -> dict[int, int]:
        return self._order_of

    @property
    def frames(self) -> list[Frame]:
        """Ordered frame list (for backward compat, saving, and iteration)."""
        return [self._frame_pool[fid] for fid in self._frame_order]

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

    def frame_count(self) -> int:
        return len(self._frame_order)

    # --- Registry ---

    def set_registry(self, registry: "BuildingRegistry") -> None:
        """Attach building registry and rebuild the spatial index (call after load/new)."""
        self._registry = registry
        self.tile_grid.rebuild(self._frame_pool, self._frame_order, registry)

    def _require_registry(self) -> "BuildingRegistry":
        if self._registry is None:
            raise RuntimeError("AivDocument has no registry; call set_registry first")
        return self._registry

    # --- Snapshots (undo support) ---

    def take_snapshot(self) -> FramesSnapshot:
        return FramesSnapshot(
            pool={fid: f.clone() for fid, f in self._frame_pool.items()},
            order=list(self._frame_order),
            next_id=self._next_frame_id,
        )

    def restore_snapshot(self, snapshot: FramesSnapshot) -> None:
        """Restore full frame state (pool + order). Rebuilds grid."""
        self._frame_pool = {fid: f.clone() for fid, f in snapshot.pool.items()}
        self._frame_order = list(snapshot.order)
        self._next_frame_id = snapshot.next_id
        self._rebuild_order_lookup()
        reg = self._registry
        if reg is not None:
            self.tile_grid.rebuild(self._frame_pool, self._frame_order, reg)
        self.frames_reordered.emit()
        self._emit_frames_changed()

    def restore_frame_order(self, order: list[int]) -> None:
        """Restore just the order list (for reorder undo). No grid rebuild needed."""
        self._frame_order = list(order)
        self._rebuild_order_lookup()
        self.frames_reordered.emit()
        self._emit_frames_changed()

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
            fid = doc._alloc_frame_id()
            frame = Frame(fid, item_type, positions, should_pause)
            doc._frame_pool[fid] = frame
            doc._frame_order.append(fid)

        for misc_data in data.get("miscItems", []):
            item_type = misc_data["itemType"]
            pos = decode_position(misc_data.get("positionOfset", 0))
            doc._misc_items.append(MiscItem(item_type, pos))

        doc._rebuild_order_lookup()
        doc._modified = False
        return doc

    def save(self, path: Optional[Path] = None) -> None:
        save_path = path or self._file_path
        if save_path is None:
            raise ValueError("No file path specified for save")

        data: dict = {
            "pauseDelayAmount": self._pause_delay_amount,
            "frames": [],
            "miscItems": [],
        }

        for fid in self._frame_order:
            frame = self._frame_pool[fid]
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
        """Insert a frame at *index* (order position). Returns the frame's stable ID."""
        if frame.id < 0:
            frame.id = self._alloc_frame_id()
        if index is None:
            index = len(self._frame_order)
        self._frame_pool[frame.id] = frame
        self._frame_order.insert(index, frame.id)
        self._rebuild_order_lookup()
        self.frame_inserting.emit(frame.id)
        reg = self._registry
        if reg is not None:
            self.tile_grid.insert_frame(frame.id, frame, reg)
        self.frame_added.emit(frame.id)
        self._emit_frames_changed()
        return frame.id

    def remove_frame(self, index: int) -> Frame:
        """Remove the frame at order *index*. Returns the removed Frame."""
        fid = self._frame_order[index]
        frame = self._frame_pool[fid]
        self.frame_removing.emit(fid)
        reg = self._registry
        if reg is not None:
            self.tile_grid.remove_frame(fid, frame, reg)
        self._frame_order.pop(index)
        del self._frame_pool[fid]
        self._rebuild_order_lookup()
        self.frame_removed.emit(fid)
        self._emit_frames_changed()
        return frame

    def move_frame(self, from_index: int, to_index: int) -> None:
        if from_index == to_index:
            return
        fid = self._frame_order.pop(from_index)
        self._frame_order.insert(to_index, fid)
        self._rebuild_order_lookup()
        self.frames_reordered.emit()
        self._emit_frames_changed()

    def reorder_frames(self, old_indices: list[int], new_start: int) -> None:
        """Move a block of frames (given by order indices) to start at new_start."""
        old_indices_sorted = sorted(old_indices)
        extracted = [self._frame_order[i] for i in old_indices_sorted]
        idx_set = set(old_indices_sorted)
        remaining = [fid for i, fid in enumerate(self._frame_order) if i not in idx_set]
        insert_at = min(new_start, len(remaining))
        self._frame_order = remaining[:insert_at] + extracted + remaining[insert_at:]
        self._rebuild_order_lookup()
        self.frames_reordered.emit()
        self._emit_frames_changed()

    def merge_frames(self, indices: list[int]) -> Optional[int]:
        """Merge frames at given order indices (must share the same itemType).
        Returns the order index of the merged frame, or None if types differ."""
        if not indices:
            return None
        sorted_idx = sorted(indices)
        types = {self.frame_at(i).item_type for i in sorted_idx}
        if len(types) != 1:
            return None
        item_type = types.pop()
        merged_positions: list[tuple[int, int]] = []
        should_pause = False
        fids_to_remove: list[int] = []
        for i in sorted_idx:
            f = self.frame_at(i)
            merged_positions.extend(f.positions)
            should_pause = should_pause or f.should_pause
            fids_to_remove.append(self._frame_order[i])

        reg = self._registry
        for fid in fids_to_remove:
            frame = self._frame_pool[fid]
            if reg is not None:
                self.tile_grid.remove_frame(fid, frame, reg)
            del self._frame_pool[fid]
        self._frame_order = [fid for fid in self._frame_order if fid not in set(fids_to_remove)]

        new_fid = self._alloc_frame_id()
        merged = Frame(new_fid, item_type, merged_positions, should_pause)
        self._frame_pool[new_fid] = merged
        insert_at = min(sorted_idx[0], len(self._frame_order))
        self._frame_order.insert(insert_at, new_fid)
        self._rebuild_order_lookup()
        if reg is not None:
            self.tile_grid.insert_frame(new_fid, merged, reg)
        self.frames_reordered.emit()
        self._emit_frames_changed()
        return insert_at

    def split_frame(self, index: int) -> list[int]:
        """Split a multi-position frame into individual frames. Returns new order indices."""
        fid = self._frame_order[index]
        frame = self._frame_pool[fid]
        if len(frame.positions) <= 1:
            return [index]

        reg = self._registry
        if reg is not None:
            self.tile_grid.remove_frame(fid, frame, reg)
        self._frame_order.pop(index)
        del self._frame_pool[fid]

        new_indices: list[int] = []
        for i, pos in enumerate(frame.positions):
            new_fid = self._alloc_frame_id()
            new_frame = Frame(new_fid, frame.item_type, [pos], frame.should_pause)
            self._frame_pool[new_fid] = new_frame
            insert_at = index + i
            self._frame_order.insert(insert_at, new_fid)
            if reg is not None:
                self.tile_grid.insert_frame(new_fid, new_frame, reg)
            new_indices.append(insert_at)

        self._rebuild_order_lookup()
        self.frames_reordered.emit()
        self._emit_frames_changed()
        return new_indices

    def apply_position_moves(
        self,
        moves: list[tuple[int, int, int, int]],
    ) -> None:
        """Apply (frame_id, pos_index, dx, dy) moves; updates tile grid."""
        reg = self._require_registry()
        affected: list[int] = []
        for frame_id, pos_idx, dx, dy in moves:
            frame = self._frame_pool[frame_id]
            old = frame.clone()
            x, y = frame.positions[pos_idx]
            frame.positions[pos_idx] = (x + dx, y + dy)
            self.tile_grid.update_frame_positions(frame_id, old, frame, reg)
            affected.append(frame_id)
        self.frame_positions_changed.emit(affected)
        self._emit_frames_changed()

    def offset_positions(self, frame_indices: list[int], dx: int, dy: int) -> None:
        """Shift all positions in the given frames (by order index) by (dx, dy)."""
        reg = self._require_registry()
        changed: list[int] = []
        for idx in frame_indices:
            fid = self._frame_order[idx]
            frame = self._frame_pool[fid]
            old = frame.clone()
            frame.positions = [(x + dx, y + dy) for x, y in frame.positions]
            self.tile_grid.update_frame_positions(fid, old, frame, reg)
            changed.append(fid)
        self.frame_positions_changed.emit(changed)
        self._emit_frames_changed()

    def remove_positions(self, removals: dict[int, set[int]]) -> None:
        """Remove specific positions from frames. Frames left empty are deleted.

        *removals* maps frame_id -> set of pos_indices to remove.
        """
        reg = self._require_registry()
        frames_to_delete: list[int] = []
        changed: list[int] = []

        for fid in sorted(removals):
            pos_indices = removals[fid]
            frame = self._frame_pool[fid]
            old = frame.clone()
            frame.positions = [
                p for i, p in enumerate(frame.positions) if i not in pos_indices
            ]
            if not frame.positions:
                frames_to_delete.append(fid)
            else:
                self.tile_grid.update_frame_positions(fid, old, frame, reg)
                changed.append(fid)

        for fid in reversed(frames_to_delete):
            order_idx = self._order_of[fid]
            self.remove_frame(order_idx)

        if changed:
            self.frame_positions_changed.emit(changed)
            self._emit_frames_changed()

    def set_should_pause(self, index: int, value: bool) -> None:
        self.frame_at(index).should_pause = value
        self._emit_frames_changed()

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
        fid = doc._alloc_frame_id()
        keep_frame = Frame(id=fid, item_type=61, positions=[(43, 43)])
        doc._frame_pool[fid] = keep_frame
        doc._frame_order.append(fid)
        doc._rebuild_order_lookup()
        doc._modified = False
        return doc
