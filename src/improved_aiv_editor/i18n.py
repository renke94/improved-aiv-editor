"""Internationalization module for EN/DE language support."""

from __future__ import annotations

_current_language: str = "en"

_TRANSLATIONS: dict[str, str] = {
    # Menu bar
    "&File": "&Datei",
    "&Edit": "&Bearbeiten",
    "&View": "&Ansicht",
    "&Tools": "&Werkzeuge",
    # File menu
    "&New": "&Neu",
    "&Open...": "&Öffnen...",
    "&Save": "&Speichern",
    "Save &As...": "Speichern &unter...",
    "&Quit": "&Beenden",
    # Edit menu
    "&Undo": "&Rückgängig",
    "&Redo": "&Wiederherstellen",
    "Select &All": "Alles &auswählen",
    # View menu
    "Zoom to &Fit": "Zoom &anpassen",
    # Tools menu
    "&Select": "&Auswählen",
    "&Place": "&Platzieren",
    "&Wall": "&Mauer",
    # Dock panel titles
    "Buildings": "Gebäude",
    "Timeline": "Zeitverlauf",
    "Properties": "Eigenschaften",
    "Undo History": "Verlauf",
    # Toolbar
    "Tools": "Werkzeuge",
    " Wall: ": " Mauer: ",
    "Stone Wall": "Steinmauer",
    "Crenulated Wall": "Zinnenhohe Mauer",
    "Low Crenulated Wall": "Zinnenflache Mauer",
    "Low Wall": "Flache Mauer",
    # Status bar
    "Position: (-, -)": "Position: (-, -)",
    "Zoom: 100%": "Zoom: 100%",
    "Frames: 0": "Frames: 0",
    # Timeline panel
    "No document loaded": "Kein Dokument geladen",
    "Merge": "Zusammenführen",
    "Merge selected frames of same type": "Ausgewählte Frames gleichen Typs zusammenführen",
    "Split": "Aufteilen",
    "Split selected frame into individual positions": "Ausgewählten Frame in einzelne Positionen aufteilen",
    "Delete": "Löschen",
    "Delete selected frames": "Ausgewählte Frames löschen",
    "Offset": "Verschieben",
    "Shift positions of selected frames": "Positionen der ausgewählten Frames verschieben",
    "Play": "Abspielen",
    "Stop": "Stopp",
    "Step through build order": "Bauabfolge durchlaufen",
    # Timeline context menu
    "Merge Frames": "Frames zusammenführen",
    "Split Frame": "Frame aufteilen",
    "Offset Positions...": "Positionen verschieben...",
    "Toggle Pause": "Pause umschalten",
    # Timeline stats
    "{count} frames": "{count} Frames",
    # Properties panel
    "Selection": "Auswahl",
    "Frames:": "Frames:",
    "Type:": "Typ:",
    "Category:": "Kategorie:",
    "Size:": "Größe:",
    "Positions:": "Positionen:",
    "Frame Properties": "Frame-Eigenschaften",
    "Index:": "Index:",
    "Should Pause:": "Pausieren:",
    "Position Details": "Positionsdetails",
    # Map labels
    "Keep": "Bergfried",
    "Stockpile": "Vorratslager",
    "Fireplace": "Feuerstelle",
    # Dialogs
    "Open AIV File": "AIV-Datei öffnen",
    "Save AIV File": "AIV-Datei speichern",
    "AIV JSON Files (*.aivjson);;All Files (*)": "AIV-JSON-Dateien (*.aivjson);;Alle Dateien (*)",
    "Error": "Fehler",
    "Failed to open file:\n{e}": "Datei konnte nicht geöffnet werden:\n{e}",
    "Failed to save file:\n{e}": "Datei konnte nicht gespeichert werden:\n{e}",
    "Unsaved Changes": "Ungespeicherte Änderungen",
    "Save changes before continuing?": "Änderungen speichern bevor fortgefahren wird?",
    "Offset X": "Verschiebung X",
    "Delta X:": "Delta X:",
    "Offset Y": "Verschiebung Y",
    "Delta Y:": "Delta Y:",
    # Building palette
    "Search buildings...": "Gebäude suchen...",
    # Language menu
    "Language": "Sprache",
    "English": "English",
    "Deutsch": "Deutsch",
    # Population indicator
    "Workers": "Arbeiter",
    "Seats": "Plätze",
}


def get_language() -> str:
    return _current_language


def set_language(lang: str) -> None:
    global _current_language
    _current_language = lang


def tr(text: str) -> str:
    """Translate a UI string. Returns the German translation when language
    is 'de', or the original English string otherwise."""
    if _current_language == "de" and text in _TRANSLATIONS:
        return _TRANSLATIONS[text]
    return text
