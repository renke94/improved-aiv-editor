"""Registry of all building types, loaded from building_data.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QPixmap

from improved_aiv_editor.i18n import get_language


@dataclass
class SpecialShapeRect:
    x: int
    y: int
    w: int
    h: int


@dataclass
class BuildingDef:
    id: int
    name: str
    name_de: str
    category: str
    kind: str
    width: int
    height: int
    thumbnail: Optional[str]
    workers: int = 0
    housing: int = 0
    fixed_position: bool = False
    special_shape: list[SpecialShapeRect] = field(default_factory=list)
    game_item_type: Optional[int] = None  # if set, file itemType (e.g. moat variants → 106)

    _pixmap_cache: Optional[QPixmap] = field(default=None, repr=False, compare=False)

    def file_item_type(self) -> int:
        """itemType written to files and used for merged frames."""
        return self.game_item_type if self.game_item_type is not None else self.id

    def footprint_offsets(self) -> list[tuple[int, int]]:
        """All (dx, dy) offsets occupied by this building relative to its origin.

        Uses special_shape rects when present, otherwise width x height.
        """
        if self.special_shape:
            offsets: set[tuple[int, int]] = set()
            for rect in self.special_shape:
                for dy in range(rect.h):
                    for dx in range(rect.w):
                        offsets.add((rect.x + dx, rect.y + dy))
            return sorted(offsets)
        return [(dx, dy) for dy in range(self.height) for dx in range(self.width)]

    def display_name(self) -> str:
        return self.name_de if get_language() == "de" else self.name

    def get_pixmap(self, assets_dir: Path) -> Optional[QPixmap]:
        if self._pixmap_cache is not None:
            return self._pixmap_cache
        if self.thumbnail is None:
            return None
        path = assets_dir / self.thumbnail
        if path.exists():
            self._pixmap_cache = QPixmap(str(path))
            return self._pixmap_cache
        return None


@dataclass
class CategoryDef:
    key: str
    name: str
    name_de: str
    icon: Optional[str]

    def display_name(self) -> str:
        return self.name_de if get_language() == "de" else self.name


class BuildingRegistry:
    def __init__(self, data_path: Path, assets_dir: Path) -> None:
        self._assets_dir = assets_dir
        self._by_id: dict[int, BuildingDef] = {}
        self._by_category: dict[str, list[BuildingDef]] = {}
        self._categories: dict[str, CategoryDef] = {}
        self._all: list[BuildingDef] = []
        self._load(data_path)

    def _load(self, data_path: Path) -> None:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for entry in data["buildings"]:
            special = []
            for rect in entry.get("special_shape", []):
                special.append(SpecialShapeRect(
                    x=rect["x"], y=rect["y"], w=rect["w"], h=rect["h"]
                ))

            bdef = BuildingDef(
                id=entry["id"],
                name=entry["name"],
                name_de=entry.get("name_de", entry["name"]),
                category=entry["category"],
                kind=entry["kind"],
                width=entry["width"],
                height=entry["height"],
                thumbnail=entry.get("thumbnail"),
                workers=entry.get("workers", 0),
                housing=entry.get("housing", 0),
                fixed_position=entry.get("fixed_position", False),
                special_shape=special,
                game_item_type=entry.get("game_item_type"),
            )
            self._by_id[bdef.id] = bdef
            self._all.append(bdef)
            self._by_category.setdefault(bdef.category, []).append(bdef)

        for key, cat_data in data.get("categories", {}).items():
            self._categories[key] = CategoryDef(
                key=key,
                name=cat_data["name"],
                name_de=cat_data.get("name_de", cat_data["name"]),
                icon=cat_data.get("icon"),
            )

    def get_by_id(self, building_id: int) -> Optional[BuildingDef]:
        return self._by_id.get(building_id)

    def get_by_category(self, category: str) -> list[BuildingDef]:
        return self._by_category.get(category, [])

    def get_all(self) -> list[BuildingDef]:
        return list(self._all)

    def get_categories(self) -> list[CategoryDef]:
        return list(self._categories.values())

    def get_category(self, key: str) -> Optional[CategoryDef]:
        return self._categories.get(key)

    def get_category_order(self) -> list[str]:
        return [
            "castle", "wall", "gatehouses", "weapons", "industry",
            "food", "town", "good_stuff", "bad_stuff", "moats", "units",
        ]

    @property
    def assets_dir(self) -> Path:
        return self._assets_dir
