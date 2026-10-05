"""Диалог создания канала связи."""

from typing import List

from PyQt6.QtWidgets import (
    QGroupBox, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QMessageBox,
)
from PyQt6.QtCore import Qt

from .base_dialog import BaseDialog
from .selectors import DeviceSelectorDialog
from models.network import NetworkModel
from models.device import Device
from config.constants import DIALOG_CHANNEL
from views.widgets.color_picker import ColorPickerWidget
from views.widgets.segment_editor import SegmentEditorWidget


class ChannelCreationDialog(BaseDialog):
    """Создание канала: маршрут из устройств + настройка сегментов."""

    def __init__(self, model: NetworkModel, parent=None) -> None:
        super().__init__("Создание канала связи", parent,
                         **DIALOG_CHANNEL)
        self.model = model
        self.route_devices: List[Device] = []
        self.segment_widgets: List[SegmentEditorWidget] = []
        self._build()

    def _build(self) -> None:
        layout = self.content_layout()

        # ===== Название + цвет =====
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        name_group = QGroupBox("Название канала")
        name_layout = QVBoxLayout(name_group)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(
            "Например: Магистраль МСК — СПб"
        )
        name_layout.addWidget(self.name_edit)
        top_row.addWidget(name_group, 2)

        color_group = QGroupBox("Цвет группы")
        color_layout = QVBoxLayout(color_group)
        self.color_picker = ColorPickerWidget()
        color_layout.addWidget(self.color_picker)
        top_row.addWidget(color_group, 1)

        layout.addLayout(top_row)

        # ===== Маршрут =====
        route_group = QGroupBox("Маршрут канала")
        route_layout = QHBoxLayout(route_group)
        route_layout.setSpacing(10)

        # Список устройств
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Устройства в порядке следования:"))

        self.route_list = QListWidget()
        self.route_list.setMinimumHeight(120)
        self.route_list.setMaximumHeight(160)
        self.route_list.itemDoubleClicked.connect(lambda _: self._remove_device())
        left_layout.addWidget(self.route_list)
        route_layout.addWidget(left, 1)

        # Кнопки управления маршрутом
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 20, 0, 0)
        right_layout.setSpacing(4)

        for text, slot in [
            ("➕ Добавить", self._add_device),
            ("➖ Удалить", self._remove_device),
            ("⬆ Вверх", lambda: self._move_device(-1)),
            ("⬇ Вниз", lambda: self._move_device(1)),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            right_layout.addWidget(btn)

        right_layout.addStretch()
        route_layout.addWidget(right)

        layout.addWidget(route_group)

        # ===== Сегменты =====
        segments_group = QGroupBox("Сегменты канала")
        segments_layout = QVBoxLayout(segments_group)

        self.segments_container = QWidget()
        self.segments_container_layout = QVBoxLayout(self.segments_container)
        self.segments_container_layout.setSpacing(10)
        self.segments_container_layout.setContentsMargins(0, 0, 0, 0)
        self.segments_container_layout.addStretch()

        scroll = self.make_scrollable(self.segments_container)
        scroll.setMinimumHeight(240)
        segments_layout.addWidget(scroll)

        self.empty_hint = QLabel(
            "Добавьте минимум два устройства, чтобы настроить сегменты."
        )
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setStyleSheet(
            "color: #6b7280; font-style: italic; padding: 20px;"
        )
        segments_layout.addWidget(self.empty_hint)

        layout.addWidget(segments_group, 1)

        # ===== Сводка =====
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(
            "background-color: #f7f9fc; border-radius: 4px; "
            "padding: 8px; color: #4a5568; font-size: 12px;"
        )
        layout.addWidget(self.summary_label)

        self.add_buttons("Создать канал")
        self._update_summary()

    # ========================================================
    #  МАРШРУТ
    # ========================================================

    def _add_device(self) -> None:
        if not self.model.devices:
            QMessageBox.warning(self, "Внимание", "Нет устройств на схеме")
            return

        dialog = DeviceSelectorDialog(self.model.devices, self)
        if dialog.exec() and dialog.selected_device():
            device = dialog.selected_device()
            self.route_devices.append(device)
            self._refresh_route_list()
            self._rebuild_segments()

    def _remove_device(self) -> None:
        row = self.route_list.currentRow()
        if 0 <= row < len(self.route_devices):
            del self.route_devices[row]
            self._refresh_route_list()
            self._rebuild_segments()

    def _move_device(self, direction: int) -> None:
        row = self.route_list.currentRow()
        new_row = row + direction
        if (0 <= row < len(self.route_devices) and
                0 <= new_row < len(self.route_devices)):
            self.route_devices[row], self.route_devices[new_row] = \
                self.route_devices[new_row], self.route_devices[row]
            self._refresh_route_list()
            self.route_list.setCurrentRow(new_row)
            self._rebuild_segments()

    def _refresh_route_list(self) -> None:
        self.route_list.clear()
        for i, dev in enumerate(self.route_devices):
            item = QListWidgetItem(f"{i + 1}.  {dev.name}")
            item.setData(Qt.ItemDataRole.UserRole, dev.id)
            self.route_list.addItem(item)

    # ========================================================
    #  СЕГМЕНТЫ
    # ========================================================

    def _rebuild_segments(self) -> None:
        # Очистка
        for w in self.segment_widgets:
            self.segments_container_layout.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
        self.segment_widgets.clear()

        # Показываем/скрываем hint
        self.empty_hint.setVisible(len(self.route_devices) < 2)

        # Создаём новые
        if len(self.route_devices) >= 2:
            for i in range(len(self.route_devices) - 1):
                seg = SegmentEditorWidget(
                    self.model,
                    self.route_devices[i],
                    self.route_devices[i + 1],
                    i + 1,
                )
                self.segment_widgets.append(seg)
                # Вставляем перед stretch
                self.segments_container_layout.insertWidget(i, seg)

        self._update_summary()

    # ========================================================
    #  СВОДКА
    # ========================================================

    def _update_summary(self) -> None:
        if len(self.route_devices) < 2:
            self.summary_label.setText(
                "ℹ️ Добавьте минимум два устройства для создания канала."
            )
            return

        total = 0.0
        cables = set()
        for w in self.segment_widgets:
            data = w.get_connection_data()
            if data:
                total += data["length"]
                cables.add(data["cable_type"])

        route = " → ".join(d.name for d in self.route_devices)
        cable_str = ", ".join(sorted(cables)) if cables else "—"

        self.summary_label.setText(
            f"📊 <b>Маршрут:</b> {route}<br>"
            f"📏 <b>Сегментов:</b> {len(self.segment_widgets)}  ·  "
            f"<b>Длина:</b> {total:.1f} м  ·  "
            f"<b>Кабели:</b> {cable_str}"
        )
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)

    # ========================================================
    #  СОЗДАНИЕ
    # ========================================================

    def accept(self) -> None:
        if len(self.route_devices) < 2:
            QMessageBox.warning(self, "Ошибка",
                                "Добавьте минимум 2 устройства.")
            return

        name = self.name_edit.text().strip() or "Новый канал"
        color = self.color_picker.get_color()

        # Проверки
        errors = []
        for i, w in enumerate(self.segment_widgets):
            ok, err = w.is_valid()
            if not ok:
                errors.append(f"Сегмент {i + 1}: {err}")

        if errors:
            QMessageBox.warning(
                self, "Ошибки в сегментах",
                "Исправьте следующие проблемы:\n\n" + "\n".join(errors),
            )
            return

        group = self.model.create_group(name, color)

        success = 0
        failed = []
        for i, w in enumerate(self.segment_widgets):
            data = w.get_connection_data()
            if not data:
                continue
            conn = self.model.add_connection(
                data["out_port"], data["in_port"],
                data["cable_type"], data["length"], group.id,
            )
            if conn:
                success += 1
            else:
                failed.append(f"Сегмент {i + 1}")

        if success == 0:
            self.model.remove_group(group)
            QMessageBox.critical(self, "Ошибка",
                                 "Не создано ни одного соединения.")
            return

        message = f"Канал «{name}» создан!\n\nСоединений: {success}"
        if failed:
            message += f"\nНе удалось: {', '.join(failed)}"
        QMessageBox.information(self, "Успех", message)
        super().accept()