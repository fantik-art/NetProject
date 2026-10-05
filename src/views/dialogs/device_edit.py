"""Диалог редактирования устройства."""

from PyQt6.QtWidgets import (
    QLineEdit, QComboBox, QFormLayout, QGroupBox,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
)
from PyQt6.QtCore import Qt

from .base_dialog import BaseDialog
from models.network import NetworkModel
from models.device import Device
from models.port import Port
from models.enums import DeviceCategory, PortType, CATEGORY_KEY_MAP, CATEGORY_MAP
from config.constants import DIALOG_DEVICE_EDIT
from views.widgets.port_row import PortRowWidget


class DeviceEditDialog(BaseDialog):
    """Редактирование устройства: имя, тип, категория, модель, порты."""

    def __init__(self, model: NetworkModel, device: Device, parent=None) -> None:
        super().__init__(f"Редактирование: {device.name}", parent,
                         **DIALOG_DEVICE_EDIT)
        self.model = model
        self.device = device
        self._input_rows = []
        self._output_rows = []
        self._build()

    def _build(self) -> None:
        layout = self.content_layout()

        # ===== Общие параметры =====
        info_group = QGroupBox("Основные параметры")
        form = QFormLayout(info_group)
        form.setSpacing(8)

        self.name_edit = QLineEdit(self.device.name)
        form.addRow("Название:", self.name_edit)

        self.type_edit = QLineEdit(self.device.device_type)
        form.addRow("Тип:", self.type_edit)

        self.model_edit = QLineEdit(self.device.model)
        self.model_edit.setPlaceholderText("Например: SW-10G-24")
        form.addRow("Модель:", self.model_edit)

        self.category_combo = QComboBox()
        for cat in DeviceCategory:
            self.category_combo.addItem(cat.value, cat)
        self.category_combo.setCurrentText(self.device.category.value)
        form.addRow("Категория:", self.category_combo)

        layout.addWidget(info_group)

        # ===== Порты =====
        ports_group = QGroupBox("Порты устройства")
        ports_layout = QHBoxLayout(ports_group)
        ports_layout.setSpacing(10)

        # Входные
        input_widget = self._make_ports_column(
            "▼ Входные", self.device.input_ports,
            self._input_rows, True,
        )
        ports_layout.addWidget(input_widget, 1)

        # Выходные
        output_widget = self._make_ports_column(
            "■ Выходные", self.device.output_ports,
            self._output_rows, False,
        )
        ports_layout.addWidget(output_widget, 1)

        layout.addWidget(ports_group, 1)

        self.add_buttons("Сохранить")

    def _make_ports_column(self, title: str, ports: list,
                           rows_list: list, is_input: bool) -> QWidget:
        """Создаёт колонку с портами (заголовок + список + кнопка)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel(f"{title} ({len(ports)})")
        header.setStyleSheet(
            "font-weight: bold; padding: 4px 0; "
            f"color: {'#047857' if is_input else '#b45309'};"
        )
        layout.addWidget(header)

        # Контейнер портов
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(4)
        container_layout.setContentsMargins(4, 4, 4, 4)
        container_layout.addStretch()

        for port in ports:
            row = PortRowWidget(port, is_input)
            row.remove_requested.connect(
                lambda w, c=container_layout, lst=rows_list, h=header:
                self._remove_port(w, c, lst, h)
            )
            container_layout.insertWidget(container_layout.count() - 1, row)
            rows_list.append(row)

        scroll = self.make_scrollable(container)
        scroll.setMinimumHeight(220)
        layout.addWidget(scroll, 1)

        # Кнопка добавления
        add_btn = QPushButton("➕ Добавить порт")
        add_btn.clicked.connect(
            lambda c=container_layout, lst=rows_list, h=header, inp=is_input:
            self._add_port(c, lst, h, inp)
        )
        layout.addWidget(add_btn)

        # Сохраняем ссылки на заголовок для обновления
        widget._header = header
        return widget

    def _add_port(self, container_layout, rows_list, header, is_input: bool) -> None:
        """Добавляет новый порт в устройство."""
        max_id = max((p.id for p in self.device.ports), default=-1)
        port = Port(
            id=max_id + 1,
            name=f"{'in' if is_input else 'out'}{max_id + 1}",
            port_type=PortType.INPUT if is_input else PortType.OUTPUT,
            connector="Ethernet",
            speed="1Gb",
        )
        if is_input:
            self.device.input_ports.append(port)
        else:
            self.device.output_ports.append(port)

        row = PortRowWidget(port, is_input)
        row.remove_requested.connect(
            lambda w, c=container_layout, lst=rows_list, h=header:
            self._remove_port(w, c, lst, h)
        )
        container_layout.insertWidget(container_layout.count() - 1, row)
        rows_list.append(row)

        self._update_header(header, is_input)

    def _remove_port(self, row, container_layout, rows_list, header) -> None:
        """Удаляет порт из устройства."""
        port = row.port
        if self.model.is_port_connected(port):
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Удаление порта",
                f"Порт «{port.name}» имеет соединения. Удалить его и связи?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self.model.remove_connections_for_port(port)

        if port in self.device.input_ports:
            self.device.input_ports.remove(port)
            is_input = True
        else:
            self.device.output_ports.remove(port)
            is_input = False

        container_layout.removeWidget(row)
        rows_list.remove(row)
        row.setParent(None)
        row.deleteLater()

        self._update_header(header, is_input)

    def _update_header(self, header: QLabel, is_input: bool) -> None:
        count = len(self.device.input_ports if is_input else self.device.output_ports)
        prefix = "▼ Входные" if is_input else "■ Выходные"
        header.setText(f"{prefix} ({count})")

    def accept(self) -> None:
        """Сохраняет изменения."""
        self.device.name = self.name_edit.text().strip() or self.device.name
        self.device.device_type = self.type_edit.text().strip()
        self.device.model = self.model_edit.text().strip()
        self.device.category = self.category_combo.currentData()

        # Обновляем имена портов из полей (уже привязаны)
        self.device.update_port_positions()
        self.model.notify()
        super().accept()