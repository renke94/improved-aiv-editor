"""Main application window with dock panels, menus, toolbar, and status bar."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QAction, QKeySequence, QUndoStack, QIcon, QActionGroup
from PyQt6.QtWidgets import (
    QMainWindow, QDockWidget, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QLabel, QComboBox,
    QApplication, QUndoView, QSpinBox,
)

from improved_aiv_editor.i18n import tr, get_language, set_language
from improved_aiv_editor.models.aiv_document import AivDocument
from improved_aiv_editor.models.building_registry import BuildingRegistry
from improved_aiv_editor.views.map_canvas import MapScene, MapCanvas
from improved_aiv_editor.views.timeline_panel import TimelinePanel
from improved_aiv_editor.views.building_palette import BuildingPalette
from improved_aiv_editor.views.properties_panel import PropertiesPanel
from improved_aiv_editor.tools.select_tool import SelectTool
from improved_aiv_editor.tools.place_tool import PlaceTool
from improved_aiv_editor.tools.wall_tool import WallTool
from improved_aiv_editor.tools.moat_pitch_brush_tool import MoatPitchBrushTool
from improved_aiv_editor.tools.ellipse_tool import EllipseTool
from improved_aiv_editor.tools.base_tool import BaseTool


ASSETS_DIR = Path(__file__).parent.parent / "assets"
DATA_PATH = Path(__file__).parent.parent / "building_data.json"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AIV Editor")
        self.resize(1400, 900)

        settings = QSettings("AIVEditor", "AIVEditor")
        saved_lang = settings.value("language", "en")
        set_language(saved_lang if isinstance(saved_lang, str) else "en")

        self._registry = BuildingRegistry(DATA_PATH, ASSETS_DIR)
        self._undo_stack = QUndoStack(self)
        self._document: Optional[AivDocument] = None
        self._current_tool: Optional[BaseTool] = None
        self._tools: dict[str, BaseTool] = {}
        self._syncing_from_timeline: bool = False
        self._syncing_from_scene: bool = False

        self._setup_scene()
        self._setup_panels()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()

        self._new_document()

    # ------------------------------------------------------------------ setup

    def _setup_scene(self) -> None:
        self._scene = MapScene(self._registry)
        self._canvas = MapCanvas(self._scene)
        self.setCentralWidget(self._canvas)

    def _setup_panels(self) -> None:
        self._palette = BuildingPalette(self._registry)
        palette_dock = QDockWidget(tr("Buildings"), self)
        palette_dock.setWidget(self._palette)
        palette_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, palette_dock)

        self._timeline = TimelinePanel(self._registry, self._undo_stack)
        timeline_dock = QDockWidget(tr("Timeline"), self)
        timeline_dock.setWidget(self._timeline)
        timeline_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, timeline_dock)

        self._properties = PropertiesPanel(self._registry, self._undo_stack)
        props_dock = QDockWidget(tr("Properties"), self)
        props_dock.setWidget(self._properties)
        props_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
            | Qt.DockWidgetArea.BottomDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, props_dock)

        undo_view = QUndoView(self._undo_stack)
        undo_dock = QDockWidget(tr("Undo History"), self)
        undo_dock.setWidget(undo_view)
        undo_dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, undo_dock)

        self._dock_palette = palette_dock
        self._dock_timeline = timeline_dock
        self._dock_properties = props_dock
        self._dock_undo = undo_dock

    def _setup_menus(self) -> None:
        menubar = self.menuBar()
        menubar.clear()

        file_menu = menubar.addMenu(tr("&File"))

        new_action = QAction(tr("&New"), self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_document)
        file_menu.addAction(new_action)

        open_action = QAction(tr("&Open..."), self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction(tr("&Save"), self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_file)
        file_menu.addAction(save_action)

        save_as_action = QAction(tr("Save &As..."), self)
        save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_action.triggered.connect(self._save_file_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        quit_action = QAction(tr("&Quit"), self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = menubar.addMenu(tr("&Edit"))

        if hasattr(self, "_undo_action") and self._undo_action is not None:
            self.removeAction(self._undo_action)
        if hasattr(self, "_redo_action") and self._redo_action is not None:
            self.removeAction(self._redo_action)

        self._undo_action = self._undo_stack.createUndoAction(self, tr("&Undo"))
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(self._undo_action)
        self.addAction(self._undo_action)

        self._redo_action = self._undo_stack.createRedoAction(self, tr("&Redo"))
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(self._redo_action)
        self.addAction(self._redo_action)

        edit_menu.addSeparator()

        select_all_action = QAction(tr("Select &All"), self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self._select_all)
        edit_menu.addAction(select_all_action)

        view_menu = menubar.addMenu(tr("&View"))

        zoom_fit_action = QAction(tr("Zoom to &Fit"), self)
        zoom_fit_action.setShortcut(QKeySequence("Ctrl+0"))
        zoom_fit_action.triggered.connect(self._canvas.zoom_to_fit)
        view_menu.addAction(zoom_fit_action)

        view_menu.addSeparator()

        view_menu.addAction(self._dock_palette.toggleViewAction())
        view_menu.addAction(self._dock_timeline.toggleViewAction())
        view_menu.addAction(self._dock_properties.toggleViewAction())
        view_menu.addAction(self._dock_undo.toggleViewAction())

        tools_menu = menubar.addMenu(tr("&Tools"))

        self._act_select_tool = QAction(tr("&Select"), self)
        self._act_select_tool.setShortcut(QKeySequence("S"))
        self._act_select_tool.setCheckable(True)
        self._act_select_tool.triggered.connect(lambda: self._activate_tool("select"))
        tools_menu.addAction(self._act_select_tool)

        self._act_place_tool = QAction(tr("&Place"), self)
        self._act_place_tool.setShortcut(QKeySequence("P"))
        self._act_place_tool.setCheckable(True)
        self._act_place_tool.triggered.connect(lambda: self._activate_tool("place"))
        tools_menu.addAction(self._act_place_tool)

        self._act_wall_tool = QAction(tr("&Line"), self)
        self._act_wall_tool.setShortcut(QKeySequence("L"))
        self._act_wall_tool.setCheckable(True)
        self._act_wall_tool.triggered.connect(lambda: self._activate_tool("wall"))
        tools_menu.addAction(self._act_wall_tool)

        self._act_ellipse_tool = QAction(tr("&Ellipse / Circle"), self)
        self._act_ellipse_tool.setShortcut(QKeySequence("E"))
        self._act_ellipse_tool.setCheckable(True)
        self._act_ellipse_tool.triggered.connect(lambda: self._activate_tool("ellipse"))
        tools_menu.addAction(self._act_ellipse_tool)

        self._tool_actions = {
            "select": self._act_select_tool,
            "place": self._act_place_tool,
            "wall": self._act_wall_tool,
            "ellipse": self._act_ellipse_tool,
        }

        lang_menu = menubar.addMenu(tr("Language"))
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)

        en_action = QAction("English", self)
        en_action.setCheckable(True)
        en_action.setChecked(get_language() == "en")
        en_action.triggered.connect(lambda: self._switch_language("en"))
        lang_group.addAction(en_action)
        lang_menu.addAction(en_action)

        de_action = QAction("Deutsch", self)
        de_action.setCheckable(True)
        de_action.setChecked(get_language() == "de")
        de_action.triggered.connect(lambda: self._switch_language("de"))
        lang_group.addAction(de_action)
        lang_menu.addAction(de_action)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar(tr("Tools"))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        self._main_toolbar = toolbar

        toolbar.addAction(self._act_select_tool)
        toolbar.addAction(self._act_place_tool)
        toolbar.addAction(self._act_wall_tool)
        toolbar.addAction(self._act_ellipse_tool)

        toolbar.addSeparator()

        self._wall_type_combo = QComboBox()
        wall_types = [
            (25, "Stone Wall", "Steinmauer"),
            (26, "Crenulated Wall", "Zinnenhohe Mauer"),
            (35, "Low Crenulated Wall", "Zinnenflache Mauer"),
            (46, "Low Wall", "Flache Mauer"),
        ]
        for wid, wname_en, wname_de in wall_types:
            display = wname_de if get_language() == "de" else wname_en
            self._wall_type_combo.addItem(display, wid)
        self._wall_type_combo.currentIndexChanged.connect(self._on_wall_type_changed)
        self._wall_label = QLabel(tr(" Type: "))
        toolbar.addWidget(self._wall_label)
        toolbar.addWidget(self._wall_type_combo)

        toolbar.addSeparator()

        self._thickness_label = QLabel(tr(" Thickness: "))
        toolbar.addWidget(self._thickness_label)
        self._thickness_spin = QSpinBox()
        self._thickness_spin.setRange(1, 10)
        self._thickness_spin.setValue(1)
        self._thickness_spin.setToolTip(tr("Line / outline thickness in tiles"))
        self._thickness_spin.valueChanged.connect(self._on_thickness_changed)
        toolbar.addWidget(self._thickness_spin)

    def _setup_statusbar(self) -> None:
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._pos_label = QLabel(tr("Position: (-, -)"))
        self._statusbar.addWidget(self._pos_label)
        self._zoom_label = QLabel(tr("Zoom: 100%"))
        self._statusbar.addPermanentWidget(self._zoom_label)
        self._frame_count_label = QLabel(tr("Frames: 0"))
        self._statusbar.addPermanentWidget(self._frame_count_label)
        self._pop_label = QLabel(f"{tr('Workers')}: 0 / 0 {tr('Seats')}")
        self._statusbar.addPermanentWidget(self._pop_label)

    def _connect_signals(self) -> None:
        self._canvas.position_changed.connect(self._on_position_changed)
        self._canvas.zoom_changed.connect(self._on_zoom_changed)
        self._canvas.switch_to_select_requested.connect(
            lambda: self._activate_tool("select")
        )
        self._palette.building_selected.connect(self._on_palette_building_selected)
        self._timeline.frame_selection_changed.connect(self._on_timeline_selection_changed)
        self._timeline.playback_frame.connect(self._on_playback_frame)
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)

    # ----------------------------------------------------------- language

    def _switch_language(self, lang: str) -> None:
        if lang == get_language():
            return
        set_language(lang)
        settings = QSettings("AIVEditor", "AIVEditor")
        settings.setValue("language", lang)
        self._refresh_language()

    def _refresh_language(self) -> None:
        self._dock_palette.setWindowTitle(tr("Buildings"))
        self._dock_timeline.setWindowTitle(tr("Timeline"))
        self._dock_properties.setWindowTitle(tr("Properties"))
        self._dock_undo.setWindowTitle(tr("Undo History"))

        self.removeToolBar(self._main_toolbar)
        self._setup_menus()
        self._setup_toolbar()

        if self._current_tool:
            tool_name = next(
                (k for k, v in self._tools.items() if v is self._current_tool), "select"
            )
            if tool_name in self._tool_actions:
                for key, action in self._tool_actions.items():
                    action.setChecked(key == tool_name)
            else:
                for action in self._tool_actions.values():
                    action.setChecked(False)

        self._palette.refresh_language()
        self._timeline.refresh_language()
        self._properties.refresh_language()

        self._update_frame_count()
        self._update_population()
        self._update_title()

        if self._document:
            self._scene.rebuild_buildings()

    # -------------------------------------------------------------- documents

    def _new_document(self) -> None:
        if not self._check_save():
            return
        self._undo_stack.clear()
        doc = AivDocument.new_empty(self)
        self._set_document(doc)

    def _open_file(self) -> None:
        if not self._check_save():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Open AIV File"),
            "",
            tr("AIV JSON Files (*.aivjson);;All Files (*)"),
        )
        if not path:
            return
        try:
            doc = AivDocument.from_file(Path(path), self)
            self._undo_stack.clear()
            self._set_document(doc)
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), f"{tr('Failed to open file:\n{e}').replace('{e}', str(e))}")

    def _save_file(self) -> None:
        if self._document is None:
            return
        if self._document.file_path is None:
            self._save_file_as()
            return
        try:
            self._document.save()
            self._update_title()
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), f"{tr('Failed to save file:\n{e}').replace('{e}', str(e))}")

    def _save_file_as(self) -> None:
        if self._document is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save AIV File"),
            "",
            tr("AIV JSON Files (*.aivjson);;All Files (*)"),
        )
        if not path:
            return
        try:
            self._document.save(Path(path))
            self._update_title()
        except Exception as e:
            QMessageBox.critical(self, tr("Error"), f"{tr('Failed to save file:\n{e}').replace('{e}', str(e))}")

    def _set_document(self, doc: AivDocument) -> None:
        if self._document is not None:
            try:
                self._document.frames_changed.disconnect(self._update_frame_count)
                self._document.frames_changed.disconnect(self._update_population)
                self._document.document_modified.disconnect(self._update_title)
                self._document.document_saved.disconnect(self._update_title)
            except TypeError:
                pass
        self._document = doc
        doc.set_registry(self._registry)
        self._scene.set_document(doc)
        self._timeline.set_document(doc)
        self._properties.set_document(doc)
        self._rebuild_tools()
        self._activate_tool("select")
        self._update_title()
        self._update_frame_count()
        self._update_population()
        doc.frames_changed.connect(self._update_frame_count)
        doc.frames_changed.connect(self._update_population)
        doc.document_modified.connect(self._update_title)
        doc.document_saved.connect(self._update_title)

    def _check_save(self) -> bool:
        if self._document is None or not self._document.is_modified:
            return True
        reply = QMessageBox.question(
            self,
            tr("Unsaved Changes"),
            tr("Save changes before continuing?"),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            self._save_file()
            return not self._document.is_modified
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        return True

    def _update_title(self) -> None:
        title = "AIV Editor"
        if self._document and self._document.file_path:
            title += f" - {self._document.file_path.name}"
        if self._document and self._document.is_modified:
            title += " *"
        self.setWindowTitle(title)

    def _update_frame_count(self) -> None:
        count = self._document.frame_count() if self._document else 0
        self._frame_count_label.setText(f"Frames: {count}")

    def _update_population(self) -> None:
        if not self._document:
            self._pop_label.setText(f"{tr('Workers')}: 0 / 0 {tr('Seats')}")
            self._pop_label.setStyleSheet("")
            return
        total_workers = 0
        total_housing = 0
        for frame in self._document.frames:
            bdef = self._registry.get_by_id(frame.item_type)
            if bdef:
                count = len(frame.positions)
                total_workers += bdef.workers * count
                total_housing += bdef.housing * count
        self._pop_label.setText(
            f"{tr('Workers')}: {total_workers} / {total_housing} {tr('Seats')}"
        )
        if total_workers > total_housing:
            self._pop_label.setStyleSheet("color: red;")
        else:
            self._pop_label.setStyleSheet("")

    # ------------------------------------------------------------------ tools

    def _rebuild_tools(self) -> None:
        if self._document is None:
            return
        self._tools = {
            "select": SelectTool(
                self._scene, self._canvas, self._document,
                self._registry, self._undo_stack,
            ),
            "place": PlaceTool(
                self._scene, self._canvas, self._document,
                self._registry, self._undo_stack,
            ),
            "wall": WallTool(
                self._scene, self._canvas, self._document,
                self._registry, self._undo_stack,
            ),
            "moat_brush": MoatPitchBrushTool(
                self._scene, self._canvas, self._document,
                self._registry, self._undo_stack,
            ),
            "ellipse": EllipseTool(
                self._scene, self._canvas, self._document,
                self._registry, self._undo_stack,
            ),
        }

    def _activate_tool(self, name: str) -> None:
        if self._current_tool is not None:
            self._current_tool.deactivate()

        if name in self._tool_actions:
            for key, action in self._tool_actions.items():
                action.setChecked(key == name)
        else:
            for action in self._tool_actions.values():
                action.setChecked(False)

        tool = self._tools.get(name)
        if tool is not None:
            tool.activate()
            self._canvas.set_tool(tool)
            self._current_tool = tool

    # -------------------------------------------------------------- callbacks

    def _on_position_changed(self, x: int, y: int) -> None:
        map_y = 99 - y
        self._pos_label.setText(f"Position: ({x}, {map_y})")

    def _on_zoom_changed(self, level: float) -> None:
        self._zoom_label.setText(f"Zoom: {int(level * 100)}%")

    def _on_palette_building_selected(self, building_id: int) -> None:
        bdef = self._registry.get_by_id(building_id)
        if bdef is None:
            return

        ellipse_active = isinstance(self._current_tool, EllipseTool)
        line_active = isinstance(self._current_tool, WallTool)

        if bdef.kind == "wall":
            if ellipse_active:
                self._current_tool.set_building(building_id)  # type: ignore[union-attr]
            elif line_active:
                self._current_tool.set_building(building_id)  # type: ignore[union-attr]
            else:
                self._activate_tool("wall")
                wall_tool = self._tools.get("wall")
                if isinstance(wall_tool, WallTool):
                    wall_tool.set_building(building_id)
            ellipse = self._tools.get("ellipse")
            if isinstance(ellipse, EllipseTool):
                ellipse.set_building(building_id)
            line = self._tools.get("wall")
            if isinstance(line, WallTool):
                line.set_building(building_id)
            return

        if bdef.kind == "moat":
            if ellipse_active:
                self._current_tool.set_building(building_id)  # type: ignore[union-attr]
            elif line_active:
                self._current_tool.set_building(building_id)  # type: ignore[union-attr]
            else:
                self._activate_tool("moat_brush")
                brush = self._tools.get("moat_brush")
                if isinstance(brush, MoatPitchBrushTool):
                    brush.set_building(building_id)
            ellipse = self._tools.get("ellipse")
            if isinstance(ellipse, EllipseTool):
                ellipse.set_building(building_id)
            line = self._tools.get("wall")
            if isinstance(line, WallTool):
                line.set_building(building_id)
            return

        self._activate_tool("place")
        place_tool = self._tools.get("place")
        if isinstance(place_tool, PlaceTool):
            place_tool.set_building(building_id)

    def _on_timeline_selection_changed(self, indices: list[int]) -> None:
        if self._syncing_from_scene:
            return
        self._syncing_from_timeline = True
        try:
            self._properties.set_selection(indices)
            self._scene.clearSelection()
            if self._document is None:
                return
            selected_fids = {self._document.frame_id_at(i) for i in indices if i < self._document.frame_count()}
            from improved_aiv_editor.views.map_canvas import BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem
            for item in self._scene._building_items:
                if isinstance(item, (BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem, KeepGraphicsItem)):
                    if item.frame_id in selected_fids:
                        item.setSelected(True)
        finally:
            self._syncing_from_timeline = False

    def _on_scene_selection_changed(self) -> None:
        if self._syncing_from_timeline:
            return
        if self._document is None:
            return
        order_of = self._document.order_lookup
        indices = sorted({
            order_of[item.frame_id]
            for item in self._scene.get_selected_buildings()
            if item.frame_id in order_of
        })
        self._syncing_from_scene = True
        try:
            self._timeline.select_frames(indices)
            self._properties.set_selection(indices)
        finally:
            self._syncing_from_scene = False

    def _on_playback_frame(self, frame_index: int) -> None:
        if self._document is None:
            return
        order_of = self._document.order_lookup
        for item in self._scene._building_items:
            from improved_aiv_editor.views.map_canvas import BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem
            if isinstance(item, (BuildingGraphicsItem, GatehouseGraphicsItem, WallSegmentItem)):
                item_order = order_of.get(item.frame_id, 0)
                item.setVisible(item_order <= frame_index)

    def _on_wall_type_changed(self, index: int) -> None:
        wall_id = self._wall_type_combo.currentData()
        if wall_id is not None:
            wall_tool = self._tools.get("wall")
            if isinstance(wall_tool, WallTool):
                wall_tool.set_building(wall_id)
            ellipse = self._tools.get("ellipse")
            if isinstance(ellipse, EllipseTool):
                ellipse.set_building(wall_id)

    def _on_thickness_changed(self, value: int) -> None:
        wall_tool = self._tools.get("wall")
        if isinstance(wall_tool, WallTool):
            wall_tool.set_thickness(value)
        ellipse = self._tools.get("ellipse")
        if isinstance(ellipse, EllipseTool):
            ellipse.set_thickness(value)

    def _select_all(self) -> None:
        for item in self._scene._building_items:
            item.setSelected(True)

    def closeEvent(self, event: object) -> None:  # type: ignore[override]
        if self._check_save():
            event.accept()  # type: ignore[union-attr]
        else:
            event.ignore()  # type: ignore[union-attr]
