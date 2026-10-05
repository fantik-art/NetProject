"""Диалог создания одиночного соединения."""

from PyQt6.QtWidgets import (
    QGroupBox, QFormLayout, QComboBox, QLabel,
    QVBoxLayout, QWidget, QLineEdit, QHBoxLayout,
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import Qt

from .base_dialog import BaseDialog
from models.network import NetworkModel
from models.port import Port
from config.constants import (
    CABLE_TYPES, CABLE_COLORS,
    CONNECTOR_CABLE_COMPAT, DIALOG_CONNECTION,
    DEFAULT_LENGTH,
)
from views.widgets.color_picker import ColorPickerWidget
from views.widgets.length_selector import LengthSelector


class ConnectionDialog(BaseDialog):
    """Создание соединения между двумя портами."""

    def __init__(self, model: NetworkModel,
                 port1: Port, port2: Port, parent=None) -> None:
        ok, error = model.can_connect(port1, port2)
        if not ok:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(parent, "Невозможно соединить", error)
            self._cancelled = True
            super().__init__("Создание соединения", parent)
            self.reject()
            return

        self._cancelled = False
        super().__init__("Создание соединения", parent,
                         **DIALOG_CONNECTION)
        self.model = model
        self.port1 = port1
        self.port2 = port2
        self._build()

    def _build(self) -> None:
        layout = self.content_layout()

        # Информация
        dev1 = self.model.find_device_by_port(self.port1)
        dev2 = self.model.find_device_by_port(self.port2)

        info_group = QGroupBox("Соединение")
        info_layout = QVBoxLayout(info_group)

        info = QLabel(
            f"<b>{dev1.name}</b><br>"
            f"&nbsp;&nbsp;{self.port1.name} · {self.port1.connector} · {self.port1.speed}<br>"
            f"<br>"
            f"<b>{dev2.name}</b><br>"
            f"&nbsp;&nbsp;{self.port2.name} · {self.port2.connector} · {self.port2.speed}"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info_layout.addWidget(info)
        layout.addWidget(info_group)

        # Параметры кабеля
        cable_group = QGroupBox("Параметры кабеля")
        cable_form = QFormLayout(cable_group)

        self.cable_combo = QComboBox()
        self.cable_combo.addItems(CABLE_TYPES)
        # Автовыбор по совместимости
        compat = CONNECTOR_CABLE_COMPAT.get(self.port1.connector, [])
        if compat:
            self.cable_combo.setCurrentText(compat[0])
        self.cable_combo.currentTextChanged.connect(self._on_cable_changed)
        cable_form.addRow("Тип кабеля:", self.cable_combo)

        self.length_selector = LengthSelector(DEFAULT_LENGTH)
        cable_form.addRow("Длина:", self.length_selector)

        layout.addWidget(cable_group)

        # Группа
        group_group = QGroupBox("Группа соединений")
        group_layout = QVBoxLayout(group_group)

        self.group_combo = QComboBox()
        self.group_combo.addItem("Без группы", None)
        for g in self.model.groups:
            count = len(self.model.get_group_connections(g))
            self.group_combo.addItem(f"● {g.name}  ({count})", g.id)
            idx = self.group_combo.count() - 1
            self.group_combo.setItemIcon(idx, self._make_color_icon(g.color))
        self.group_combo.addItem("+ Новая группа...", "new")
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        group_layout.addWidget(self.group_combo)

        # Панель новой группы
        self.new_group_widget = QWidget()
        ng_layout = QVBoxLayout(self.new_group_widget)
        ng_layout.setContentsMargins(0, 6, 0, 0)
        ng_layout.setSpacing(6)

        ng_layout.addWidget(QLabel("Название:"))
        self.new_group_name = QLineEdit()
        self.new_group_name.setPlaceholderText("Название канала")
        ng_layout.addWidget(self.new_group_name)

        ng_layout.addWidget(QLabel("Цвет:"))
        self.color_picker = ColorPickerWidget()
        ng_layout.addWidget(self.color_picker)

        self.new_group_widget.setVisible(False)
        group_layout.addWidget(self.new_group_widget)

        layout.addWidget(group_group)

        # Красим изначально
        self._on_cable_changed(self.cable_combo.currentText())

        self.add_buttons("Создать")

    @staticmethod
    def _make_color_icon(color: str) -> QIcon:
        pm = QPixmap(14, 14)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(color))
        p.setPen(QPen(QColor("#9ca3af"), 1))
        p.drawRoundedRect(1, 1, 12, 12, 3, 3)
        p.end()
        return QIcon(pm)

    def _on_cable_changed(self, cable_type: str) -> None:
        color = CABLE_COLORS.get(cable_type, "#4b5563")
        self.cable_combo.setStyleSheet(
            f"color: {color}; font-weight: 600;"
        )

    def _on_group_changed(self) -> None:
        self.new_group_widget.setVisible(
            self.group_combo.currentData() == "new"
        )

    def accept(self) -> None:
        cable_type = self.cable_combo.currentText()
        length = self.length_selector.get_length()
        group_id = self.group_combo.currentData()

        if group_id == "new":
            name = self.new_group_name.text().strip() or "Новая группа"
            group = self.model.create_group(name, self.color_picker.get_color())
            group_id = group.id

        self.model.add_connection(
            self.port1, self.port2, cable_type, length, group_id,
        )
        super().accept()