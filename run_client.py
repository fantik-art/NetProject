#!/usr/bin/env python3
import sys
from PyQt6.QtWidgets import QApplication

from client.views.main_window import MainWindow
from client.views.login_dialog import LoginDialog
from client.network.tcp_client import TcpClient
from common.protocol import Message, MessageType


class ClientApp:
    """Приложение клиента"""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setStyle('Fusion')

        self._setup_style()

        self.window = MainWindow()
        self.client = TcpClient()

        self._connect_signals()

        self.window.show()
        self.show_login()

    def _setup_style(self):
        self.app.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; color: #cdd6f4; }
            QWidget { color: #cdd6f4; }
            QGroupBox { 
                font-weight: bold; border: 1px solid #45475a; border-radius: 5px; 
                margin-top: 10px; padding-top: 10px; color: #cdd6f4;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #89b4fa;
            }
            QPushButton { 
                padding: 8px 15px; border: 1px solid #45475a; border-radius: 3px; 
                background-color: #313244; color: #cdd6f4;
            }
            QPushButton:hover { background-color: #45475a; }
            QPushButton:disabled { color: #585b70; }
            QLabel { color: #cdd6f4; }
            QListWidget {
                background-color: #313244; color: #cdd6f4; border: 1px solid #45475a;
            }
            QStatusBar { background-color: #313244; color: #a6adc8; }
            QSplitter::handle { background-color: #45475a; width: 2px; }
        """)

    def _connect_signals(self):
        # Сигналы окна
        self.window.login_requested.connect(self.show_login)
        self.window.sector_selected.connect(self.join_sector)
        self.window.lock_toggled.connect(self.toggle_lock)
        self.window.leave_sector.connect(self.leave_sector)

        # Сигналы канваса
        self.window.canvas.device_moved.connect(self.on_device_moved)
        self.window.canvas.device_added.connect(self.on_device_added)
        self.window.canvas.device_deleted.connect(self.on_device_deleted)
        self.window.canvas.connection_requested.connect(self.on_connection_requested)

        # Сигналы клиента
        self.window.canvas.sector_changed.connect(self.on_sector_changed)
        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.message_received.connect(self.on_message)
        self.client.connection_error.connect(self.on_error)
        self.window.view_mode_changed.connect(self.on_view_mode_changed)

    def on_sector_changed(self, sector: dict):
        """Отправка изменений сектора на сервер"""
        msg = Message(
            type=MessageType.SECTOR_EDIT,  # Нужно добавить в MessageType
            sector_id=sector.get('id', 0),
            payload={'sector': sector}
        )
        self.client.send_message(msg)

    def on_view_mode_changed(self, view_mode: str, sector_ids: list):
        """Отправка изменения режима просмотра на сервер"""
        msg = Message(
            type=MessageType.VIEW_CHANGE,
            payload={
                'view_mode': view_mode,
                'sector_ids': sector_ids
            }
        )
        self.client.send_message(msg)

    def show_login(self):
        dialog = LoginDialog(self.window)
        if dialog.exec():
            info = dialog.get_connection_info()
            self.client.connect_to_server(info['host'], info['port'])
            self._pending_login = info

    def on_connected(self):
        self.window.status_bar.showMessage("Подключено к серверу")
        if hasattr(self, '_pending_login'):
            info = self._pending_login
            msg = Message(
                type=MessageType.LOGIN_REQUEST,
                payload={'username': info['username'], 'password': info['password']}
            )
            self.client.send_message(msg)

    def on_disconnected(self):
        self.window.status_bar.showMessage("Отключено от сервера")

    def on_message(self, message: Message):
        """Обработка входящих сообщений"""

        if message.type == MessageType.LOGIN_RESPONSE:
            if message.payload.get('success'):
                self.window.update_user_info(message.payload)
                # Запрашиваем список секторов
                self.client.send_message(Message(type=MessageType.SECTORS_LIST))
                self._current_user_id = message.payload.get('user_id')
                self._current_user_role = message.payload.get('role', 'viewer')
            else:
                self.window.status_bar.showMessage(
                    f"Ошибка: {message.payload.get('error')}"
                )

        elif message.type == MessageType.SECTORS_LIST:
            sectors = message.payload.get('sectors', [])
            self.window.update_sectors(sectors)

            # Автоматически входим в первый доступный сектор
            if sectors and not self.window.current_sector_id:
                first_sector = sectors[0]
                self.join_sector(first_sector.get('id', 0))

        elif message.type == MessageType.FULL_STATE:
            state = message.payload

            # Подробное логирование
            print(f"Получено FULL_STATE:")
            print(f"  - Устройств: {len(state.get('devices', []))}")
            print(f"  - Соединений: {len(state.get('connections', []))}")
            print(f"  - Секторов: {len(state.get('sectors', []))}")
            print(f"  - Групп: {len(state.get('groups', []))}")

            # Загружаем состояние в канвас
            self.window.canvas.load_state(state)
            self.window.update_version(state.get('global_version', 1))

            # Обновляем пользователей
            users = state.get('users', [])
            self.window.update_users(users)

            # Обновляем информацию о секторе
            sectors = state.get('sectors', [])
            for sector in sectors:
                if sector.get('id') == self.window.current_sector_id:
                    self.window.on_sector_joined(sector.get('id'), sector.get('name'))
                    break

            # Обновляем права на редактирование
            can_edit = state.get('can_edit', False)
            self.window.canvas.set_editable(can_edit)

            self.window.status_bar.showMessage(
                f"Загружено: {len(state.get('devices', []))} устройств, "
                f"{len(state.get('connections', []))} соединений"
            )

        elif message.type == MessageType.DELTA_UPDATE:
            changes = message.payload.get('changes', [])
            self.window.canvas.apply_changes(changes)
            self.window.update_version(message.payload.get('version', 1))

        elif message.type == MessageType.USER_JOINED:
            user = message.payload.get('user', {})
            self.window.add_user(user)

        elif message.type == MessageType.USER_LEFT:
            self.window.remove_user(message.payload.get('user_id', 0))

        elif message.type == MessageType.LOCK_RESPONSE:
            if message.payload.get('success'):
                self.window.update_lock_status(True, message.payload.get('locked_by_name', ''))

        elif message.type == MessageType.UNLOCK_RESPONSE:
            if message.payload.get('success'):
                self.window.update_lock_status(False)

        elif message.type == MessageType.LOCK_NOTIFICATION:
            is_locked = message.payload.get('is_locked', False)
            self.window.update_lock_status(is_locked, message.payload.get('locked_by_name', ''))

    def on_error(self, error: str):
        self.window.status_bar.showMessage(f"Ошибка: {error}")

    def join_sector(self, sector_id: int):
        """Вход в сектор"""
        self._current_sector = sector_id
        msg = Message(type=MessageType.SECTOR_JOIN, sector_id=sector_id)
        self.client.send_message(msg)

    def leave_sector(self):
        """Выход из сектора"""
        if hasattr(self, '_current_sector'):
            msg = Message(type=MessageType.SECTOR_LEAVE, sector_id=self._current_sector)
            self.client.send_message(msg)
        self.window.on_sector_left()

    def toggle_lock(self):
        """Переключение блокировки"""
        if not self.window.current_sector_id:
            return

        if self.window.is_locked:
            msg = Message(type=MessageType.UNLOCK_REQUEST, sector_id=self.window.current_sector_id)
        else:
            msg = Message(type=MessageType.LOCK_REQUEST, sector_id=self.window.current_sector_id)
        self.client.send_message(msg)

    def on_device_moved(self, device_id: int, x: float, y: float):
        """Отправка перемещения устройства"""
        msg = Message(
            type=MessageType.DEVICE_MOVE,
            sector_id=self.window.current_sector_id,
            payload={'device': {'id': device_id, 'x': x, 'y': y}}
        )
        self.client.send_message(msg)

    def on_device_added(self, device: dict):
        """Отправка нового устройства"""
        msg = Message(
            type=MessageType.DEVICE_ADD,
            sector_id=self.window.current_sector_id,
            payload={'device': device}
        )
        self.client.send_message(msg)

    def on_device_deleted(self, device_id: int):
        """Отправка удаления устройства"""
        msg = Message(
            type=MessageType.DEVICE_DELETE,
            sector_id=self.window.current_sector_id,
            payload={'device': {'id': device_id}}
        )
        self.client.send_message(msg)

    def on_connection_requested(self, dev1: int, port1: int, dev2: int, port2: int):
        """Отправка запроса на создание соединения"""
        msg = Message(
            type=MessageType.CONNECTION_ADD,
            sector_id=self.window.current_sector_id,
            payload={
                'connection': {
                    'device1_id': dev1,
                    'port1_id': port1,
                    'device2_id': dev2,
                    'port2_id': port2,
                    'cable_type': 'Ethernet',
                    'length': 1.0
                }
            }
        )
        self.client.send_message(msg)

    def run(self):
        return self.app.exec()


if __name__ == '__main__':
    client = ClientApp()
    sys.exit(client.run())