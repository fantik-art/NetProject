"""
Базовый класс для диалогов.

Обеспечивает:
  - Автоматическое ограничение размеров (не больше экрана)
  - Стандартные отступы и layout
  - Единый стиль
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox,
    QApplication, QWidget, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt

from config.constants import DIALOG_MAX_WIDTH, DIALOG_MAX_HEIGHT


class BaseDialog(QDialog):
    """Базовый диалог с ограничением размеров и стандартной версткой."""

    def __init__(self, title: str, parent=None,
                 width: int = 700, height: int = 500) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._init_size(width, height)
        self.setModal(True)

        # Основной layout
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setSpacing(12)
        self._main_layout.setContentsMargins(16, 16, 16, 16)

        # Контейнер для содержимого (наследники добавляют в него)
        self._content_layout = QVBoxLayout()
        self._content_layout.setSpacing(10)
        self._main_layout.addLayout(self._content_layout, 1)

        # Кнопки (наследники могут переопределить)
        self._button_box = None

    def _init_size(self, width: int, height: int) -> None:
        """Ограничивает размер диалога доступным экраном."""
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            max_w = min(DIALOG_MAX_WIDTH, int(available.width() * 0.9))
            max_h = min(DIALOG_MAX_HEIGHT, int(available.height() * 0.9))
            self.resize(min(width, max_w), min(height, max_h))
            self.setMinimumSize(
                min(500, max_w),
                min(400, max_h),
            )
        else:
            self.resize(width, height)

    def content_layout(self) -> QVBoxLayout:
        """Возвращает layout для добавления содержимого."""
        return self._content_layout

    def add_buttons(self, ok_text: str = "OK") -> QDialogButtonBox:
        """Добавляет стандартные кнопки OK/Cancel."""
        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = self._button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText(ok_text)
            ok_btn.setDefault(True)

        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)
        self._main_layout.addWidget(self._button_box)
        return self._button_box

    def make_scrollable(self, content: QWidget) -> QScrollArea:
        """Оборачивает виджет в прокручиваемую область."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setWidget(content)
        return scroll