"""
Network Visualizer v3.0 — точка входа приложения.

Запускает QApplication, применяет стили, открывает главное окно.
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from views.main_window import MainWindow
from config.constants import STYLE_PATH


def load_stylesheet(path: Path) -> str:
    """Загружает QSS-стили из файла."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def main() -> None:
    """Точка входа."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Загружаем стили
    style = load_stylesheet(STYLE_PATH)
    if style:
        app.setStyleSheet(style)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()