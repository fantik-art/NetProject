"""Виджет строки редактирования порта."""

from functools import partial

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QComboBox, QPushButton,
)
from PyQt6.QtCore import pyqtSignal

from models.port import Port
from config.constants import CONNECTORS, SPEEDS, CONNECTOR_COLORS


class PortRowWidget(QWidget):
    """
    Строка редактирования одного порта:
    имя | разъём | скорость | удалить
    """

    changed = pyqtSignal()
    remove_requested = pyqtSignal(object)  # self

    def __init__(self, port: Port, is_input: bool, parent=None) -> None:
        super().__init__(parent)
        self.port = port
        self.is_input = is_input
        self._build()
        self._load_values()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        # Имя порта
        self._name_edit = QLineEdit()
        self._name_edit.setMaximumWidth(120)
        self._name_edit.textChanged.connect(self._on_changed)
        layout.addWidget(self._name_edit)

        # Разъём
        self._connector_combo = QComboBox()
        self._connector_combo.addItems(CONNECTORS)
        self._connector_combo.setMinimumWidth(110)
        self._connector_combo.currentTextChanged.connect(self._on_changed)
        layout.addWidget(self._connector_combo)

        # Скорость
        self._speed_combo = QComboBox()
        self._speed_combo.addItems(SPEEDS)
        self._speed_combo.setMaximumWidth(90)
        self._speed_combo.currentTextChanged.connect(self._on_changed)
        layout.addWidget(self._speed_combo)

        layout.addStretch()

        # Удалить
        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(30)
        del_btn.setProperty("class", "danger")
        del_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        layout.addWidget(del_btn)

    def _load_values(self) -> None:
        self._name_edit.blockSignals(True)
        self._connector_combo.blockSignals(True)
        self._speed_combo.blockSignals(True)

        self._name_edit.setText(self.port.name)
        if self.port.connector in CONNECTORS:
            self._connector_combo.setCurrentText(self.port.connector)
        if self.port.speed in SPEEDS:
            self._speed_combo.setCurrentText(self.port.speed)

        self._name_edit.blockSignals(False)
        self._connector_combo.blockSignals(False)
        self._speed_combo.blockSignals(False)

        self._update_style()

    def _on_changed(self) -> None:
        self.port.name = self._name_edit.text()
        self.port.connector = self._connector_combo.currentText()
        self.port.speed = self._speed_combo.currentText()
        self._update_style()
        self.changed.emit()

    def _update_style(self) -> None:
        """Красит имя порта цветом разъёма для наглядности."""
        color = CONNECTOR_COLORS.get(self.port.connector, "#4b5563")
        self._name_edit.setStyleSheet(
            f"color: {color}; font-weight: 600;"
        )