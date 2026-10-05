"""Виджет выбора стандартной длины кабеля."""

from PyQt6.QtWidgets import QComboBox
from PyQt6.QtCore import pyqtSignal

from config.constants import STANDARD_LENGTHS, DEFAULT_LENGTH


class LengthSelector(QComboBox):
    """Выпадающий список стандартных длин кабеля."""

    length_changed = pyqtSignal(float)

    def __init__(self, initial: float = DEFAULT_LENGTH, parent=None) -> None:
        super().__init__(parent)
        for length in STANDARD_LENGTHS:
            self.addItem(self._format(length), length)
        self.setCurrentIndex(self._find_index(initial))
        self.currentIndexChanged.connect(self._on_change)

    @staticmethod
    def _format(length: float) -> str:
        if length == int(length):
            return f"{int(length)} м"
        return f"{length} м"

    def _find_index(self, value: float) -> int:
        for i in range(self.count()):
            if self.itemData(i) == value:
                return i
        return 0

    def _on_change(self) -> None:
        self.length_changed.emit(self.currentData())

    def get_length(self) -> float:
        return self.currentData()