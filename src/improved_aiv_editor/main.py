"""Entry point for the AIV Editor application."""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from improved_aiv_editor.views.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("AIV Editor")
    app.setOrganizationName("AIVEditor")

    window = MainWindow()
    window.show()

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
        if file_path.exists() and file_path.suffix == ".aivjson":
            from improved_aiv_editor.models.aiv_document import AivDocument
            try:
                doc = AivDocument.from_file(file_path, window)
                window._set_document(doc)
            except Exception as e:
                print(f"Error loading file: {e}", file=sys.stderr)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
