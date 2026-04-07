"""Building palette with categorized thumbnails and search."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QAbstractItemView,
)

from improved_aiv_editor.i18n import tr

if TYPE_CHECKING:
    from improved_aiv_editor.models.building_registry import BuildingRegistry, BuildingDef


class BuildingPalette(QWidget):
    """Sidebar showing buildings grouped by category with search."""

    building_selected = pyqtSignal(int)

    def __init__(
        self,
        registry: "BuildingRegistry",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._registry = registry
        self._all_items: list[tuple[QTreeWidgetItem, "BuildingDef"]] = []

        self._setup_ui()
        self._populate()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("Search buildings..."))
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_search)
        layout.addWidget(self._search)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.setIndentation(16)
        self._tree.setIconSize(QSize(40, 40))
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.setDragEnabled(True)
        layout.addWidget(self._tree)

    def _populate(self) -> None:
        self._tree.clear()
        self._all_items.clear()

        for cat_key in self._registry.get_category_order():
            cat_def = self._registry.get_category(cat_key)
            buildings = self._registry.get_by_category(cat_key)
            if not buildings:
                continue

            cat_name = cat_def.display_name() if cat_def else cat_key
            cat_item = QTreeWidgetItem(self._tree, [cat_name])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)

            if cat_def and cat_def.icon:
                icon_path = self._registry.assets_dir / cat_def.icon
                if icon_path.exists():
                    cat_item.setIcon(0, QIcon(str(icon_path)))

            for bdef in buildings:
                label = f"{bdef.display_name()} ({bdef.width}x{bdef.height})"
                child = QTreeWidgetItem(cat_item, [label])
                child.setData(0, Qt.ItemDataRole.UserRole, bdef.id)
                child.setToolTip(0, f"{bdef.name} / {bdef.name_de} (ID: {bdef.id})")

                pixmap = bdef.get_pixmap(self._registry.assets_dir)
                if pixmap is not None:
                    child.setIcon(0, QIcon(pixmap.scaled(
                        40, 40, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )))

                self._all_items.append((child, bdef))

            cat_item.setExpanded(False)

    def _on_search(self, text: str) -> None:
        search_lower = text.lower().strip()
        for child_item, bdef in self._all_items:
            if not search_lower:
                child_item.setHidden(False)
            else:
                match = (
                    search_lower in bdef.name.lower()
                    or search_lower in bdef.name_de.lower()
                    or search_lower in str(bdef.id)
                )
                child_item.setHidden(not match)

        for i in range(self._tree.topLevelItemCount()):
            cat_item = self._tree.topLevelItem(i)
            if cat_item is None:
                continue
            has_visible = False
            for j in range(cat_item.childCount()):
                if not cat_item.child(j).isHidden():
                    has_visible = True
                    break
            cat_item.setHidden(not has_visible)
            if search_lower and has_visible:
                cat_item.setExpanded(True)

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        building_id = item.data(0, Qt.ItemDataRole.UserRole)
        if building_id is not None:
            self.building_selected.emit(building_id)

    def refresh_language(self) -> None:
        self._search.setPlaceholderText(tr("Search buildings..."))
        self._populate()

    def get_selected_building_id(self) -> Optional[int]:
        items = self._tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.ItemDataRole.UserRole)
