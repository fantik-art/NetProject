"""Диалоги выбора (устройства и порты)."""

from typing import List, Optional, Tuple

from PyQt6.QtWidgets import (
    QLineEdit, QListWidget, QListWidgetItem, QLabel,
    QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from .base_dialog import BaseDialog
from models.device import Device
from models.port import Port
from config.constants import DIALOG_SELECTOR


class DeviceSelectorDialog(BaseDialog):
    """Диалог выбора устройства из списка с поиском."""

    def __init__(self, devices: List[Device], parent=None) -> None:
        super().__init__("Выбор устройства", parent,
                         **DIALOG_SELECTOR)
        self._devices = devices
        self._result: Optional[Device] = None
        self._build()

    def _build(self) -> None:
        layout = self.content_layout()

        layout.addWidget(QLabel("Найдите устройство:"))

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍 Поиск по имени или типу...")
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _: self.accept())
        layout.addWidget(self._list, 1)

        self._populate()
        self.add_buttons("Выбрать")

    def _populate(self) -> None:
        self._list.clear()
        for dev in self._devices:
            item = QListWidgetItem(
                f"{dev.name}  ({dev.device_type})  "
                f"[{len(dev.ports)} портов]"
            )
            item.setData(Qt.ItemDataRole.UserRole, dev.id)
            self._list.addItem(item)

    def _filter(self, text: str) -> None:
        text = text.strip().lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(text not in item.text().lower())

    def accept(self) -> None:
        current = self._list.currentItem()
        if current:
            dev_id = current.data(Qt.ItemDataRole.UserRole)
            self._result = next(
                (d for d in self._devices if d.id == dev_id), None
            )
        super().accept()

    def selected_device(self) -> Optional[Device]:
        return self._result