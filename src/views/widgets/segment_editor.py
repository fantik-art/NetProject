"""Виджет сегмента канала (соединение двух устройств)."""

from typing import Optional

from PyQt6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
)
from PyQt6.QtCore import Qt

from models.network import NetworkModel
from models.device import Device
from models.port import Port
from config.constants import (
    CABLE_TYPES, CABLE_COLORS, CONNECTOR_CABLE_COMPAT,
)
from .length_selector import LengthSelector


class SegmentEditorWidget(QGroupBox):
    """
    Один сегмент канала: соединение между двумя устройствами.
    Позволяет выбрать конкретные порты, тип кабеля и длину.
    """

    def __init__(self, model: NetworkModel,
                 device1: Device, device2: Device,
                 index: int, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self.device1 = device1
        self.device2 = device2
        self.index = index

        self.setTitle(
            f"Сегмент {index}: {device1.name}  →  {device2.name}"
        )
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(12, 16, 12, 12)

        # Выходной порт
        layout.addLayout(self._make_row(
            "Выходной порт:", self._make_out_port_combo()
        ))

        # Входной порт
        layout.addLayout(self._make_row(
            "Входной порт:", self._make_in_port_combo()
        ))

        # Кабель и длина
        cable_row = QHBoxLayout()
        cable_row.setSpacing(8)
        cable_row.addWidget(QLabel("Кабель:"))

        self._cable_combo = QComboBox()
        self._cable_combo.addItems(CABLE_TYPES)
        self._cable_combo.setMinimumWidth(140)
        self._cable_combo.currentTextChanged.connect(self._on_cable_changed)
        cable_row.addWidget(self._cable_combo)

        cable_row.addWidget(QLabel("Длина:"))
        self._length_selector = LengthSelector()
        cable_row.addWidget(self._length_selector)

        cable_row.addStretch()
        layout.addLayout(cable_row)

        # Статус
        self._status = QLabel()
        self._status.setWordWrap(True)
        self._status.setStyleSheet("font-size: 11px; padding: 4px;")
        layout.addWidget(self._status)

        # Первичная проверка
        self._update_status()

    def _make_row(self, label_text: str, widget: QComboBox) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setMinimumWidth(110)
        row.addWidget(label)
        row.addWidget(widget, 1)
        return row

    def _make_out_port_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumWidth(260)
        for port in self.device1.output_ports:
            is_busy = self.model.is_port_connected(port)
            prefix = "❌ " if is_busy else "✅ "
            text = f"{prefix}{port.name}  ·  {port.connector} · {port.speed}"
            combo.addItem(text, port)
            if is_busy:
                self._disable_item(combo, combo.count() - 1)
        self._auto_select(combo)
        combo.currentIndexChanged.connect(self._on_port_changed)
        self._out_combo = combo
        return combo

    def _make_in_port_combo(self) -> QComboBox:
        combo = QComboBox()
        combo.setMinimumWidth(260)
        for port in self.device2.input_ports:
            is_busy = self.model.is_port_connected(port)
            prefix = "❌ " if is_busy else "✅ "
            text = f"{prefix}{port.name}  ·  {port.connector} · {port.speed}"
            combo.addItem(text, port)
            if is_busy:
                self._disable_item(combo, combo.count() - 1)
        self._auto_select(combo)
        combo.currentIndexChanged.connect(self._on_port_changed)
        self._in_combo = combo
        return combo

    @staticmethod
    def _disable_item(combo: QComboBox, index: int) -> None:
        item = combo.model().item(index)
        if item:
            item.setEnabled(False)

    @staticmethod
    def _auto_select(combo: QComboBox) -> None:
        for i in range(combo.count()):
            item = combo.model().item(i)
            if item and item.isEnabled():
                combo.setCurrentIndex(i)
                return

    def _on_port_changed(self) -> None:
        """При смене порта подбирает совместимый кабель."""
        out_port: Port = self._out_combo.currentData()
        if out_port:
            compat = CONNECTOR_CABLE_COMPAT.get(out_port.connector, [])
            if compat:
                self._cable_combo.blockSignals(True)
                current = self._cable_combo.currentText()
                if current not in compat:
                    self._cable_combo.setCurrentText(compat[0])
                self._cable_combo.blockSignals(False)
                self._on_cable_changed(self._cable_combo.currentText())
        self._update_status()

    def _on_cable_changed(self, cable_type: str) -> None:
        color = CABLE_COLORS.get(cable_type, "#4b5563")
        self._cable_combo.setStyleSheet(
            f"color: {color}; font-weight: 600;"
        )
        self._update_status()

    def _update_status(self) -> None:
        out_port: Port = self._out_combo.currentData()
        in_port: Port = self._in_combo.currentData()

        if not out_port or not in_port:
            self._set_status("⚠️ Выберите порты", "#b45309")
            return

        ok, error = self.model.can_connect(out_port, in_port)
        if ok:
            self._set_status("✅ Соединение возможно", "#047857")
        else:
            self._set_status(f"❌ {error}", "#b91c1c")

    def _set_status(self, text: str, color: str) -> None:
        self._status.setText(text)
        self._status.setStyleSheet(
            f"color: {color}; font-size: 11px; padding: 4px;"
        )

    def get_connection_data(self) -> Optional[dict]:
        out_port: Port = self._out_combo.currentData()
        in_port: Port = self._in_combo.currentData()
        if not out_port or not in_port:
            return None
        return {
            "out_port": out_port,
            "in_port": in_port,
            "cable_type": self._cable_combo.currentText(),
            "length": self._length_selector.get_length(),
        }

    def is_valid(self) -> tuple:
        data = self.get_connection_data()
        if not data:
            return False, "Не выбраны порты"
        ok, error = self.model.can_connect(data["out_port"], data["in_port"])
        if not ok:
            return False, error
        return True, ""