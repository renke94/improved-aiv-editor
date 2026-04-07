"""98x98 spatial index for frame positions (O(1) tile lookups).

Mirrors the ordered frame list in AivDocument; file I/O remains frame-based.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from improved_aiv_editor.models.aiv_document import Frame
    from improved_aiv_editor.models.building_registry import BuildingRegistry


MAP_SIZE = 98


@dataclass(frozen=True, slots=True)
class TileOccupant:
    frame_index: int
    pos_index: int
    kind: str
    item_type: int


class TileGrid:
    """Each cell (1..MAP_SIZE) holds occupants for that tile (units can stack)."""

    __slots__ = ("_cells", "_keep_frame_count")

    def __init__(self) -> None:
        self._cells: list[list[list[TileOccupant]]] = [
            [[] for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)
        ]
        self._keep_frame_count = 0

    def clear(self) -> None:
        for row in self._cells:
            for c in row:
                c.clear()
        self._keep_frame_count = 0

    def rebuild(self, frames: list["Frame"], registry: "BuildingRegistry") -> None:
        self.clear()
        for fi, frame in enumerate(frames):
            self._add_frame_tiles(fi, frame, registry)

    def _add_frame_tiles(self, frame_index: int, frame: "Frame", registry: "BuildingRegistry") -> None:
        bdef = registry.get_by_id(frame.item_type)
        if bdef is None:
            return
        if frame.item_type == 61:
            self._keep_frame_count += 1
        kind = bdef.kind
        offsets = bdef.footprint_offsets()
        for pos_idx, (tx, ty) in enumerate(frame.positions):
            occ = TileOccupant(frame_index, pos_idx, kind, frame.item_type)
            for dx, dy in offsets:
                nx, ny = tx + dx, ty + dy
                if 1 <= nx <= MAP_SIZE and 1 <= ny <= MAP_SIZE:
                    self._cells[ny - 1][nx - 1].append(occ)

    def _remove_frame_tiles(self, frame_index: int, frame: "Frame", registry: "BuildingRegistry") -> None:
        bdef = registry.get_by_id(frame.item_type)
        if bdef is None:
            return
        if frame.item_type == 61:
            self._keep_frame_count = max(0, self._keep_frame_count - 1)
        offsets = bdef.footprint_offsets()
        for pos_idx, (tx, ty) in enumerate(frame.positions):
            for dx, dy in offsets:
                nx, ny = tx + dx, ty + dy
                if 1 <= nx <= MAP_SIZE and 1 <= ny <= MAP_SIZE:
                    cell = self._cells[ny - 1][nx - 1]
                    cell[:] = [
                        o for o in cell
                        if not (o.frame_index == frame_index and o.pos_index == pos_idx)
                    ]

    def _shift_frame_indices_ge(self, from_index: int, delta: int) -> None:
        """Adjust frame_index for all occupants with frame_index >= from_index."""
        for row in self._cells:
            for cell in row:
                new_cell: list[TileOccupant] = []
                for o in cell:
                    if o.frame_index >= from_index:
                        new_cell.append(
                            TileOccupant(
                                o.frame_index + delta,
                                o.pos_index,
                                o.kind,
                                o.item_type,
                            )
                        )
                    else:
                        new_cell.append(o)
                cell[:] = new_cell

    def _shift_frame_indices_gt(self, after_index: int, delta: int) -> None:
        """Adjust frame_index for occupants with frame_index > after_index."""
        for row in self._cells:
            for cell in row:
                new_cell: list[TileOccupant] = []
                for o in cell:
                    if o.frame_index > after_index:
                        new_cell.append(
                            TileOccupant(
                                o.frame_index + delta,
                                o.pos_index,
                                o.kind,
                                o.item_type,
                            )
                        )
                    else:
                        new_cell.append(o)
                cell[:] = new_cell

    def insert_frame(self, index: int, frame: "Frame", registry: "BuildingRegistry") -> None:
        """Insert a new frame at index (frames list already includes it at index)."""
        self._shift_frame_indices_ge(index, +1)
        self._add_frame_tiles(index, frame, registry)

    def remove_frame_at(self, index: int, frame: "Frame", registry: "BuildingRegistry") -> None:
        """Remove tiles for frame at index, then shift indices down."""
        self._remove_frame_tiles(index, frame, registry)
        self._shift_frame_indices_gt(index, -1)

    def update_frame_positions(
        self,
        frame_index: int,
        old_frame: "Frame",
        new_frame: "Frame",
        registry: "BuildingRegistry",
    ) -> None:
        """After mutating positions in-place (e.g. offset)."""
        self._remove_frame_tiles(frame_index, old_frame, registry)
        self._add_frame_tiles(frame_index, new_frame, registry)

    def has_keep(self) -> bool:
        return self._keep_frame_count > 0

    def is_origin_occupied(self, tx: int, ty: int, exclude_units: bool = True) -> bool:
        if not (1 <= tx <= MAP_SIZE and 1 <= ty <= MAP_SIZE):
            return True
        for o in self._cells[ty - 1][tx - 1]:
            if exclude_units and o.kind == "unit":
                continue
            return True
        return False

    def top_occupant_at(self, tx: int, ty: int) -> Optional[TileOccupant]:
        """Topmost by frame_index for hit-testing."""
        if not (1 <= tx <= MAP_SIZE and 1 <= ty <= MAP_SIZE):
            return None
        cell = self._cells[ty - 1][tx - 1]
        if not cell:
            return None
        return max(cell, key=lambda o: o.frame_index)

    def frame_indices_intersecting_scene_rect(
        self,
        scene_left: float,
        scene_top: float,
        scene_right: float,
        scene_bottom: float,
        tile_size: float,
    ) -> set[int]:
        """Tile range from scene rect (inclusive), collect unique frame indices."""
        x1 = max(1, min(MAP_SIZE, int(scene_left / tile_size) + 1))
        x2 = max(1, min(MAP_SIZE, int(scene_right / tile_size) + 1))
        y1 = max(1, min(MAP_SIZE, int(scene_top / tile_size) + 1))
        y2 = max(1, min(MAP_SIZE, int(scene_bottom / tile_size) + 1))
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        out: set[int] = set()
        for ty in range(y1, y2 + 1):
            for tx in range(x1, x2 + 1):
                for o in self._cells[ty - 1][tx - 1]:
                    out.add(o.frame_index)
        return out

    def nonunit_occupied_tiles(self) -> set[tuple[int, int]]:
        """All (tx, ty) tiles occupied by at least one non-unit occupant."""
        out: set[tuple[int, int]] = set()
        for ty in range(1, MAP_SIZE + 1):
            for tx in range(1, MAP_SIZE + 1):
                for o in self._cells[ty - 1][tx - 1]:
                    if o.kind != "unit":
                        out.add((tx, ty))
                        break
        return out
