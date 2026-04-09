"""98x98 spatial index for frame positions (O(1) tile lookups).

Uses stable frame IDs rather than positional indices, so reordering
the frame list never invalidates grid data.
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
    frame_id: int
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

    def rebuild(
        self,
        frame_pool: dict[int, "Frame"],
        frame_order: list[int],
        registry: "BuildingRegistry",
    ) -> None:
        self.clear()
        for fid in frame_order:
            frame = frame_pool[fid]
            self._add_frame_tiles(fid, frame, registry)

    def _add_frame_tiles(self, frame_id: int, frame: "Frame", registry: "BuildingRegistry") -> None:
        bdef = registry.get_by_id(frame.item_type)
        if bdef is None:
            return
        if frame.item_type == 61:
            self._keep_frame_count += 1
        kind = bdef.kind
        offsets = bdef.footprint_offsets()
        for pos_idx, (tx, ty) in enumerate(frame.positions):
            occ = TileOccupant(frame_id, pos_idx, kind, frame.item_type)
            for dx, dy in offsets:
                nx, ny = tx + dx, ty + dy
                if 1 <= nx <= MAP_SIZE and 1 <= ny <= MAP_SIZE:
                    self._cells[ny - 1][nx - 1].append(occ)

    def _remove_frame_tiles(self, frame_id: int, frame: "Frame", registry: "BuildingRegistry") -> None:
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
                        if not (o.frame_id == frame_id and o.pos_index == pos_idx)
                    ]

    def insert_frame(self, frame_id: int, frame: "Frame", registry: "BuildingRegistry") -> None:
        """Add tiles for a new frame (stable ID, no index shifting needed)."""
        self._add_frame_tiles(frame_id, frame, registry)

    def remove_frame(self, frame_id: int, frame: "Frame", registry: "BuildingRegistry") -> None:
        """Remove tiles for a frame (stable ID, no index shifting needed)."""
        self._remove_frame_tiles(frame_id, frame, registry)

    def update_frame_positions(
        self,
        frame_id: int,
        old_frame: "Frame",
        new_frame: "Frame",
        registry: "BuildingRegistry",
    ) -> None:
        """After mutating positions in-place (e.g. offset)."""
        self._remove_frame_tiles(frame_id, old_frame, registry)
        self._add_frame_tiles(frame_id, new_frame, registry)

    def has_keep(self) -> bool:
        return self._keep_frame_count > 0

    def is_origin_occupied(
        self,
        tx: int,
        ty: int,
        exclude_units: bool = True,
        overridable_kinds: frozenset[str] | None = None,
    ) -> bool:
        if not (1 <= tx <= MAP_SIZE and 1 <= ty <= MAP_SIZE):
            return True
        for o in self._cells[ty - 1][tx - 1]:
            if exclude_units and o.kind == "unit":
                continue
            if overridable_kinds and o.kind in overridable_kinds:
                continue
            return True
        return False

    def is_occupied_excluding(
        self,
        tx: int,
        ty: int,
        exclude_fids: frozenset[int],
    ) -> bool:
        """True if tile is occupied by a non-unit building not in *exclude_fids*."""
        if not (1 <= tx <= MAP_SIZE and 1 <= ty <= MAP_SIZE):
            return True
        for o in self._cells[ty - 1][tx - 1]:
            if o.kind == "unit":
                continue
            if o.frame_id in exclude_fids:
                continue
            return True
        return False

    def find_overlapping_positions(
        self,
        tiles: list[tuple[int, int]],
        target_kinds: frozenset[str],
    ) -> dict[int, set[int]]:
        """Collect positions of *target_kinds* occupants that overlap *tiles*.

        Returns a mapping of frame_id -> set of pos_indices suitable for
        ``AivDocument.remove_positions``.
        """
        result: dict[int, set[int]] = {}
        for tx, ty in tiles:
            if not (1 <= tx <= MAP_SIZE and 1 <= ty <= MAP_SIZE):
                continue
            for occ in self._cells[ty - 1][tx - 1]:
                if occ.kind in target_kinds:
                    result.setdefault(occ.frame_id, set()).add(occ.pos_index)
        return result

    def top_occupant_at(
        self, tx: int, ty: int, order_of: dict[int, int],
    ) -> Optional[TileOccupant]:
        """Topmost occupant by build order for hit-testing."""
        if not (1 <= tx <= MAP_SIZE and 1 <= ty <= MAP_SIZE):
            return None
        cell = self._cells[ty - 1][tx - 1]
        if not cell:
            return None
        return max(cell, key=lambda o: order_of.get(o.frame_id, 0))

    def frame_ids_in_scene_rect(
        self,
        scene_left: float,
        scene_top: float,
        scene_right: float,
        scene_bottom: float,
        tile_size: float,
    ) -> set[int]:
        """Tile range from scene rect (inclusive), collect unique frame IDs."""
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
                    out.add(o.frame_id)
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
