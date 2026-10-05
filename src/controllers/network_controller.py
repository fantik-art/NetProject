"""Контроллер — связывает модель, канвас и диалоги."""

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox

from models.network import NetworkModel
from views.canvas import NetworkCanvas
from views.widgets.side_panel import SidePanel
from views.dialogs import (
    DeviceEditDialog, ConnectionDialog,
    ChannelCreationDialog, GroupManagementDialog,
)


class NetworkController(QObject):
    """Обрабатывает сигналы от view и управляет моделью."""

    def __init__(self, model: NetworkModel, canvas: NetworkCanvas,
                 side_panel: SidePanel, window) -> None:
        super().__init__()
        self.model = model
        self.canvas = canvas
        self.side_panel = side_panel
        self.window = window

        # Канвас
        canvas.device_edited.connect(self.edit_device)
        canvas.device_deleted.connect(self._delete_device)
        canvas.connection_requested.connect(self.create_connection)
        canvas.connection_deleted.connect(self._delete_connection)
        canvas.channel_requested.connect(self.create_channel)
        canvas.groups_requested.connect(self.manage_groups)

        # Панель
        side_panel.filter_changed.connect(self._on_filter_changed)
        side_panel.display_changed.connect(self._on_display_changed)
        side_panel.create_channel.connect(self.create_channel)
        side_panel.manage_groups.connect(self.manage_groups)
        side_panel.save_project.connect(window._save_project)
        side_panel.load_project.connect(window._load_project)
        side_panel.delete_selected.connect(self.delete_selected)

    # ========================================================
    #  УСТРОЙСТВА
    # ========================================================

    def edit_device(self, device) -> None:
        dialog = DeviceEditDialog(self.model, device, self.window)
        dialog.exec()

    def _delete_device(self, device) -> None:
        self.model.remove_device(device)

    # ========================================================
    #  СОЕДИНЕНИЯ
    # ========================================================

    def create_connection(self, port1, port2) -> None:
        dialog = ConnectionDialog(self.model, port1, port2, self.window)
        dialog.exec()

    def _delete_connection(self, connection) -> None:
        """Удаляет соединение из модели."""
        self.model.remove_connection(connection)
        self.canvas.update()

    # ========================================================
    #  КАНАЛЫ И ГРУППЫ
    # ========================================================

    def create_channel(self) -> None:
        if not self.model.devices:
            QMessageBox.warning(self.window, "Внимание",
                                "Нет устройств на схеме.")
            return
        dialog = ChannelCreationDialog(self.model, self.window)
        dialog.exec()

    def manage_groups(self) -> None:
        dialog = GroupManagementDialog(self.model, self.window)
        dialog.exec()

    # ========================================================
    #  ФИЛЬТР И ОТОБРАЖЕНИЕ
    # ========================================================

    def _on_filter_changed(self, text: str) -> None:
        self.model.set_filter(text)

    def _on_display_changed(self) -> None:
        settings = self.side_panel.get_display_settings()
        self.model.show_port_labels = settings["show_port_labels"]
        self.model.show_connection_labels = settings["show_connection_labels"]
        self.model.show_grid = settings["show_grid"]
        self.model.notify()

    # ========================================================
    #  УДАЛЕНИЕ
    # ========================================================

    def delete_selected(self) -> None:
        if self.canvas.selected_device:
            reply = QMessageBox.question(
                self.window, "Удаление",
                f"Удалить устройство «{self.canvas.selected_device.name}»?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.model.remove_device(self.canvas.selected_device)
                self.canvas.selected_device = None
                self.canvas.update()
        elif self.canvas.selected_port:
            self.model.remove_connections_for_port(self.canvas.selected_port)
            self.canvas.selected_port = None
            self.canvas.update()