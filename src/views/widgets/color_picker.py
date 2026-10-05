"""Виджет выбора цвета из палитры."""

from functools import partial

from PyQt6.QtWidgets import QWidget, QGridLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

from config.constants import GROUP_PALETTE


class ColorPickerWidget(QWidget):
    """
    Сетка цветных кнопок для выбора цвета.
    Не испускает сигнал при инициализации.
    """

    color_changed = pyqtSignal(str)

    def __init__(self, initial: str = None, parent=None) -> None:
        super().__init__(parent)
        self._selected = initial or GROUP_PALETTE[0]
        self._buttons = []
        self._initialized = False

        self._build()
        self._initialized = True

    def _build(self) -> None:
        layout = QGridLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        cols = 8
        for i, color in enumerate(GROUP_PALETTE):
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(color)
            btn.setProperty("hex_color", color)
            btn.clicked.connect(partial(self._on_click, color))
            layout.addWidget(btn, i // cols, i % cols)
            self._buttons.append(btn)

        self._refresh_styles()

    def _on_click(self, color: str) -> None:
        if not self._initialized or color == self._selected:
            return
        self._selected = color
        self._refresh_styles()
        self.color_changed.emit(color)

    def _refresh_styles(self) -> None:
        for btn in self._buttons:
            color = btn.property("hex_color")
            is_sel = color == self._selected
            border = "#1f2937" if is_sel else "transparent"
            width = 3 if is_sel else 0
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: {width}px solid {border};
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    border: 2px solid #6b7280;
                }}
            """)

    def get_color(self) -> str:
        return self._selected

    def set_color(self, color: str) -> None:
        self._selected = color
        self._refresh_styles()