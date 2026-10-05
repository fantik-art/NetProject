"""Диалог управления группами."""

from PyQt6.QtWidgets import (
    QGroupBox, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QHBoxLayout, QVBoxLayout, QCheckBox, QMessageBox,
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import Qt

from .base_dialog import BaseDialog
from models.network import NetworkModel
from config.constants import DIALOG_GROUPS
from views.widgets.color_picker import ColorPickerWidget


class GroupManagementDialog(BaseDialog):
    """Управление группами соединений."""

    def __init__(self, model: NetworkModel, parent=None) -> None:
        super().__init__("Управление группами", parent, **DIALOG_GROUPS)
        self.model = model
        self._selected_group = None
        self._build()
        self._refresh_list()

    def _build(self) -> None:
        layout = self.content_layout()

        # Поиск
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по названию...")
        self.search_edit.textChanged.connect(self._refresh_list)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        # Основная область
        main = QHBoxLayout()
        main.setSpacing(10)

        # Список
        self.group_list = QListWidget()
        self.group_list.itemSelectionChanged.connect(self._on_selection)
        main.addWidget(self.group_list, 1)

        # Редактирование
        edit_group = QGroupBox("Редактирование")
        edit_group.setMaximumWidth(320)
        edit_layout = QVBoxLayout(edit_group)

        edit_layout.addWidget(QLabel("Название:"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)
        edit_layout.addWidget(self.name_edit)

        edit_layout.addWidget(QLabel("Цвет:"))
        self.color_picker = ColorPickerWidget()
        self.color_picker.color_changed.connect(self._on_color_changed)
        edit_layout.addWidget(self.color_picker)

        self.visible_cb = QCheckBox("Показывать соединения")
        self.visible_cb.stateChanged.connect(self._on_visibility)
        edit_layout.addWidget(self.visible_cb)

        edit_layout.addStretch()

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(
            "color: #6b7280; font-size: 11px; padding: 6px;"
        )
        edit_layout.addWidget(self.info_label)

        main.addWidget(edit_group)

        layout.addLayout(main, 1)

        # Кнопки управления
        btn_row = QHBoxLayout()

        for text, slot in [
            ("Скрыть/Показать", self._toggle),
            ("Показать все", self._show_all),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)

        del_btn = QPushButton("🗑 Удалить")
        del_btn.setProperty("class", "danger")
        del_btn.clicked.connect(self._delete)
        btn_row.addWidget(del_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.add_buttons("Закрыть")
        # Скрываем кнопку OK — диалог только для управления
        ok_btn = self._button_box.button(
            self._button_box.StandardButton.Ok
        )
        if ok_btn:
            ok_btn.setVisible(False)

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

    def _refresh_list(self) -> None:
        selected_id = None
        current = self.group_list.currentItem()
        if current:
            selected_id = current.data(Qt.ItemDataRole.UserRole)

        self.group_list.clear()
        ft = self.search_edit.text().strip().lower()

        for g in self.model.groups:
            if ft and ft not in g.name.lower():
                continue
            count = len(self.model.get_group_connections(g))
            prefix = "✓" if g.visible else "✗"
            item = QListWidgetItem(f"{prefix}  {g.name}   ({count})")
            item.setData(Qt.ItemDataRole.UserRole, g.id)
            item.setIcon(self._make_color_icon(g.color))
            self.group_list.addItem(item)

            if g.id == selected_id:
                self.group_list.setCurrentItem(item)

    def _on_selection(self) -> None:
        item = self.group_list.currentItem()
        if not item:
            self._selected_group = None
            self.name_edit.clear()
            self.info_label.clear()
            return

        gid = item.data(Qt.ItemDataRole.UserRole)
        self._selected_group = self.model.get_group(gid)
        if not self._selected_group:
            return

        self.name_edit.blockSignals(True)
        self.name_edit.setText(self._selected_group.name)
        self.name_edit.blockSignals(False)

        self.color_picker.set_color(self._selected_group.color)

        self.visible_cb.blockSignals(True)
        self.visible_cb.setChecked(self._selected_group.visible)
        self.visible_cb.blockSignals(False)

        conns = self.model.get_group_connections(self._selected_group)
        total = sum(c.length for c in conns)
        self.info_label.setText(
            f"📊 Соединений: {len(conns)}\n"
            f"📏 Общая длина: {total:.1f} м"
        )

    def _on_name_changed(self, text: str) -> None:
        if self._selected_group and text:
            self._selected_group.name = text
            self.model.notify()
            self._refresh_list()

    def _on_color_changed(self, color: str) -> None:
        if self._selected_group:
            self.model.update_group_color(self._selected_group, color)
            self._refresh_list()

    def _on_visibility(self, state) -> None:
        if self._selected_group:
            self._selected_group.visible = (
                state == Qt.CheckState.Checked.value
            )
            self.model.notify()
            self._refresh_list()

    def _toggle(self) -> None:
        if self._selected_group:
            self._selected_group.visible = not self._selected_group.visible
            self.model.notify()
            self._refresh_list()
            self._on_selection()

    def _show_all(self) -> None:
        for g in self.model.groups:
            g.visible = True
        self.model.notify()
        self._refresh_list()

    def _delete(self) -> None:
        if not self._selected_group:
            return
        reply = QMessageBox.question(
            self, "Удаление",
            f"Удалить группу «{self._selected_group.name}»?\n"
            f"Соединения останутся, но без группы.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.model.remove_group(self._selected_group)
            self._selected_group = None
            self._refresh_list()
            self._on_selection()