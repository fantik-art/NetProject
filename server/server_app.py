from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal

from common.protocol import Message, MessageType
from common.utils import hash_password, generate_id
from .models.user import User
from .models.sector import Sector
from .models.state import ServerState
from .models.connection import ConnectionGroup  # ДОБАВИТЬ ИМПОРТ
from .services.auth_service import AuthService
from .services.sector_service import SectorService
from .services.lock_service import LockService
from .services.sync_service import SyncService
from .network.tcp_server import TcpServer


class ServerApp(QObject):
    """Главное приложение сервера"""

    log_message = pyqtSignal(str)
    user_connected = pyqtSignal(int, str)
    user_disconnected = pyqtSignal(int, str)

    def __init__(self, port: int = 5555):
        super().__init__()

        # Состояние сервера
        self.state = ServerState()

        # Сервисы
        self.auth_service = AuthService(self.state)
        self.sector_service = SectorService(self.state)
        self.lock_service = LockService(self.state)

        # TCP сервер
        self.tcp_server = TcpServer(port)
        self.tcp_server.message_received.connect(self._on_message_received)
        self.tcp_server.new_connection.connect(self._on_new_connection)
        self.tcp_server.client_disconnected.connect(self._on_client_disconnected)

        # Сервис синхронизации
        self.sync_service = SyncService(self.state, self.tcp_server)

        # Инициализация тестовых данных
        self._init_test_data()

        print(f"=== СЕРВЕР ИНИЦИАЛИЗИРОВАН ===")
        print(f"Пользователей: {len(self.state.users)}")
        print(f"Секторов: {len(self.state.sectors)}")
        print(f"Устройств: {len(self.state.devices)}")
        print(f"Соединений: {len(self.state.connections)}")
        print(f"Групп: {len(self.state.groups)}")

        # Выводим первые устройства для проверки
        for i, dev in enumerate(self.state.devices[:3]):
            print(f"  Устройство {i + 1}: {dev.get('name')} (ID: {dev.get('id')})")

    def start(self):
        self._init_test_data()
        self.log_message.emit(f"Загружено устройств: {len(self.state.devices)}")
        self.log_message.emit(f"Загружено соединений: {len(self.state.connections)}")
        self.log_message.emit(f"Загружено секторов: {len(self.state.sectors)}")
        return self.tcp_server.start()

    def stop(self):
        self.tcp_server.stop()

    def _init_test_data(self):
        """Создание тестовых данных с полноценной сетью"""

        # ... весь код создания пользователей и секторов ...

        # ========== ГРУППЫ СОЕДИНЕНИЙ (как словари) ==========
        self.state.groups = [
            {
                'id': 1,
                'name': "Магистраль МСК-СПб",
                'color': "#ff6464",
                'visible': True
            },
            {
                'id': 2,
                'name': "ЦОД - Балансировка",
                'color': "#64ff64",
                'visible': True
            },
            {
                'id': 3,
                'name': "Резервные каналы",
                'color': "#6464ff",
                'visible': True
            },
            {
                'id': 4,
                'name': "Межсетевые соединения",
                'color': "#ffff64",
                'visible': True
            },
            {
                'id': 5,
                'name': "Серверная ферма ЦОД",
                'color': "#ff64ff",
                'visible': True
            },
        ]

        # Назначаем группы на соединения
        for conn in self.state.connections:
            # Магистральные соединения -> группа 1
            if conn.get('cable_type') == 'Fiber Optic' and conn.get('length', 0) >= 50:
                conn['group_id'] = 1
            # Балансировщик -> группа 2
            elif conn.get('device1_id') == 8:
                conn['group_id'] = 2
            # Прямые соединения кросс-маршрутизатор -> группа 3
            elif conn.get('device1_id') == 1 and conn.get('device2_id') == 4:
                conn['group_id'] = 3
            # Межсетевые -> группа 4
            elif conn.get('device2_id') == 14:
                conn['group_id'] = 4
            # Серверные -> группа 5
            elif conn.get('device2_id') in [6, 7]:
                conn['group_id'] = 5

    def _on_message_received(self, user_id: int, message: Message):
        """Обработка входящих сообщений"""

        if message.type == MessageType.LOGIN_REQUEST:
            self._handle_login(user_id, message)
            return

        # Проверяем авторизацию
        user = self.state.get_user(user_id)
        if not user and message.type != MessageType.PING:
            return

        # Маршрутизация сообщений
        handlers = {
            MessageType.SECTORS_LIST: self._handle_sectors_list,
            MessageType.SECTOR_JOIN: self._handle_sector_join,
            MessageType.SECTOR_LEAVE: self._handle_sector_leave,
            MessageType.LOCK_REQUEST: self._handle_lock_request,
            MessageType.UNLOCK_REQUEST: self._handle_unlock_request,
            MessageType.DEVICE_ADD: self._handle_device_change,
            MessageType.DEVICE_MOVE: self._handle_device_change,
            MessageType.DEVICE_EDIT: self._handle_device_change,
            MessageType.DEVICE_DELETE: self._handle_device_change,
            MessageType.CONNECTION_ADD: self._handle_connection_change,
            MessageType.CONNECTION_DELETE: self._handle_connection_change,
            MessageType.GROUP_CREATE: self._handle_group_change,
            MessageType.GROUP_DELETE: self._handle_group_change,
            MessageType.PING: lambda uid, msg: self._send_pong(uid),
        }

        handler = handlers.get(message.type)
        if handler:
            handler(user_id, message)

    def _handle_login(self, temp_id: int, message: Message):
        """Обработка входа"""
        username = message.payload.get('username', '')
        password = message.payload.get('password', '')

        result = self.auth_service.authenticate(username, password)

        if result:
            user_id = result['user_id']
            user = self.state.get_user(user_id)
            user.is_online = True
            user.session_id = str(generate_id())

            # Регистрируем клиента
            self.tcp_server.register_client(user_id, username)

            # Отправляем ответ
            response = Message(
                type=MessageType.LOGIN_RESPONSE,
                sender_id=user_id,
                payload=result
            )
            self.sync_service.send_to_user(user_id, response)

            self.user_connected.emit(user_id, username)
            self.log_message.emit(f"Пользователь {username} вошел в систему")
        else:
            self.log_message.emit(f"Неудачная попытка входа: {username}")

    def _handle_sectors_list(self, user_id: int, message: Message):
        """Отправка списка секторов"""
        sectors = self.state.get_user_sectors(user_id)
        response = Message(
            type=MessageType.SECTORS_LIST,
            sender_id=0,
            payload={'sectors': sectors}
        )
        self.sync_service.send_to_user(user_id, response)

    def _handle_sector_join(self, user_id: int, message: Message):
        """Вход в сектор"""
        sector_id = message.sector_id
        sector = self.state.get_sector(sector_id)
        user = self.state.get_user(user_id)

        if not sector or not user:
            self.log_message.emit(f"Ошибка: сектор {sector_id} или пользователь {user_id} не найдены")
            return

        # Проверяем права
        if not sector.can_view(user_id, user.role):
            self.log_message.emit(f"Пользователь {user.username} не имеет доступа к сектору {sector.name}")
            return

        sector.add_user(user_id)
        user.current_sector_id = sector_id
        user.view_mode = 'single'
        user.visible_sectors = [sector_id]

        # Отправляем состояние ВСЕЙ сети, но с учетом прав
        self.sync_service.send_full_state(user_id, 'single', [sector_id])

        # Уведомляем других
        notification = Message(
            type=MessageType.USER_JOINED,
            sender_id=user_id,
            sector_id=sector_id,
            payload={'user': user.to_dict()}
        )
        self.sync_service.broadcast_to_sector(sector_id, notification, user_id)

        self.log_message.emit(
            f"{user.username} вошел в сектор {sector.name} "
            f"(устройств в секторе: {len(sector.device_ids)})"
        )

    def _handle_sector_leave(self, user_id: int, message: Message):
        """Выход из сектора"""
        sector_id = message.sector_id
        sector = self.state.get_sector(sector_id)
        user = self.state.get_user(user_id)

        if sector and user:
            sector.remove_user(user_id)
            user.current_sector_id = 0

            if sector.locked_by == user_id:
                sector.unlock(user_id)

            notification = Message(
                type=MessageType.USER_LEFT,
                sender_id=user_id,
                sector_id=sector_id,
                payload={'user_id': user_id}
            )
            self.sync_service.broadcast_to_sector(sector_id, notification)

    def _handle_lock_request(self, user_id: int, message: Message):
        """Запрос блокировки"""
        sector_id = message.sector_id
        result = self.lock_service.acquire_lock(sector_id, user_id)

        response = Message(
            type=MessageType.LOCK_RESPONSE,
            sender_id=user_id,
            sector_id=sector_id,
            payload=result
        )
        self.sync_service.send_to_user(user_id, response)

        if result.get('success'):
            notification = Message(
                type=MessageType.LOCK_NOTIFICATION,
                sender_id=user_id,
                sector_id=sector_id,
                payload={
                    'is_locked': True,
                    'locked_by_name': result.get('locked_by_name', '')
                }
            )
            self.sync_service.broadcast_to_sector(sector_id, notification, user_id)

    def _handle_unlock_request(self, user_id: int, message: Message):
        """Запрос разблокировки"""
        sector_id = message.sector_id
        result = self.lock_service.release_lock(sector_id, user_id)

        response = Message(
            type=MessageType.UNLOCK_RESPONSE,
            sender_id=user_id,
            sector_id=sector_id,
            payload=result
        )
        self.sync_service.send_to_user(user_id, response)

        if result.get('success'):
            notification = Message(
                type=MessageType.LOCK_NOTIFICATION,
                sender_id=user_id,
                sector_id=sector_id,
                payload={'is_locked': False}
            )
            self.sync_service.broadcast_to_sector(sector_id, notification, user_id)

    def _handle_device_change(self, user_id: int, message: Message):
        """Обработка изменений устройств"""
        sector_id = message.sector_id
        sector = self.state.get_sector(sector_id)

        if not sector:
            return

        # Проверяем блокировку (кроме viewer)
        user = self.state.get_user(user_id)
        if user and user.role != 'viewer':
            if sector.is_locked() and sector.locked_by != user_id:
                return

        device_data = message.payload.get('device', {})

        if message.type == MessageType.DEVICE_ADD:
            self.sector_service.update_device(sector_id, device_data)
        elif message.type == MessageType.DEVICE_MOVE:
            self.sector_service.update_device(sector_id, device_data)
        elif message.type == MessageType.DEVICE_EDIT:
            self.sector_service.update_device(sector_id, device_data)
        elif message.type == MessageType.DEVICE_DELETE:
            self.sector_service.remove_device(sector_id, device_data.get('id', 0))

        sector.add_change(message.type.name, user_id, device_data)
        sector.version += 1

        self.sync_service.broadcast_delta(
            sector_id,
            [{'type': message.type.name, 'device': device_data}],
            user_id
        )

    def _handle_connection_change(self, user_id: int, message: Message):
        """Обработка изменений соединений"""
        sector_id = message.sector_id
        conn_data = message.payload.get('connection', {})

        if message.type == MessageType.CONNECTION_ADD:
            self.sector_service.add_connection(sector_id, conn_data)

        sector = self.state.get_sector(sector_id)
        if sector:
            sector.add_change(message.type.name, user_id, conn_data)
            sector.version += 1

        self.sync_service.broadcast_delta(
            sector_id,
            [{'type': message.type.name, 'connection': conn_data}],
            user_id
        )

    def _handle_group_change(self, user_id: int, message: Message):
        """Обработка изменений групп"""
        sector_id = message.sector_id
        group_data = message.payload.get('group', {})

        sector = self.state.get_sector(sector_id)
        if sector:
            if message.type == MessageType.GROUP_CREATE:
                sector.groups.append(group_data)
            elif message.type == MessageType.GROUP_DELETE:
                sector.groups = [g for g in sector.groups
                                 if g.get('id') != group_data.get('id')]
            sector.version += 1

        self.sync_service.broadcast_delta(
            sector_id,
            [{'type': message.type.name, 'group': group_data}],
            user_id
        )

    def _send_pong(self, user_id: int):
        """Ответ на ping"""
        response = Message(type=MessageType.PONG, sender_id=0)
        self.sync_service.send_to_user(user_id, response)

    def _on_new_connection(self, user_id: int, socket):
        """Обработка нового соединения"""
        pass

    def _on_client_disconnected(self, user_id: int):
        """Обработка отключения клиента"""
        user = self.state.get_user(user_id)
        if user:
            username = user.username
            user.is_online = False

            if user.current_sector_id:
                sector = self.state.get_sector(user.current_sector_id)
                if sector:
                    sector.remove_user(user_id)
                    if sector.locked_by == user_id:
                        sector.unlock(user_id)

                    notification = Message(
                        type=MessageType.USER_LEFT,
                        sender_id=user_id,
                        sector_id=user.current_sector_id,
                        payload={'user_id': user_id}
                    )
                    self.sync_service.broadcast_to_sector(
                        user.current_sector_id, notification
                    )

            self.user_disconnected.emit(user_id, username)
            self.log_message.emit(f"Пользователь {username} отключился")

        # В класс ServerApp добавляем новые методы:

    def _handle_view_change(self, user_id: int, message: Message):
            """Обработка изменения режима просмотра"""
            view_mode = message.payload.get('view_mode', 'full')
            sector_ids = message.payload.get('sector_ids', [])

            user = self.state.get_user(user_id)
            if not user:
                return

            # Сохраняем настройки просмотра пользователя
            user.view_mode = view_mode
            user.visible_sectors = sector_ids

            # Отправляем обновленное состояние
            self.sync_service.send_full_state(user_id, view_mode, sector_ids)

            self.log_message.emit(
                f"Пользователь {user.username} изменил вид: {view_mode} "
                f"(сектора: {sector_ids})"
            )

    def _handle_sector_join(self, user_id: int, message: Message):
            """Вход в сектор (для редактирования)"""
            sector_id = message.sector_id
            sector = self.state.get_sector(sector_id)
            user = self.state.get_user(user_id)

            if not sector or not user:
                return

            # Проверяем права на вход в сектор
            if not sector.can_view(user_id, user.role):
                self.log_message.emit(f"Пользователь {user.username} не имеет доступа к сектору {sector.name}")
                return

            sector.add_user(user_id)
            user.current_sector_id = sector_id
            user.view_mode = 'single'
            user.visible_sectors = [sector_id]

            # Отправляем состояние
            self.sync_service.send_full_state(user_id, 'single', [sector_id])

            # Уведомляем других в секторе
            notification = Message(
                type=MessageType.USER_JOINED,
                sender_id=user_id,
                sector_id=sector_id,
                payload={'user': user.to_dict()}
            )
            self.sync_service.broadcast_to_sector(sector_id, notification, user_id)

            self.log_message.emit(f"{user.username} вошел в сектор {sector.name}")

    def _init_test_data(self):
            """Создание тестовых данных с ЕДИНОЙ сетью"""

            # Создаем пользователей
            users_data = [
                (1, "admin", "admin123", "admin", "Администратор"),
                (2, "manager1", "manager123", "manager", "Менеджер сети"),
                (3, "operator1", "operator123", "operator", "Оператор магистрали"),
                (4, "operator2", "operator123", "operator", "Оператор серверной"),
                (5, "viewer1", "viewer123", "viewer", "Наблюдатель"),
            ]

            for uid, username, password, role, full_name in users_data:
                user = User(
                    id=uid,
                    username=username,
                    password_hash=hash_password(password),
                    role=role,
                    full_name=full_name
                )
                self.state.users[uid] = user

            # Создаем сектора (части единой сети)
            sectors_data = [
                (1, "🏢 Магистральная сеть", "Внешние подключения",
                 {'x': 0, 'y': 0, 'width': 1200, 'height': 400}, "#4682b4", 2),
                (2, "🔌 Локальная сеть", "Локальные кроссы",
                 {'x': 0, 'y': 350, 'width': 600, 'height': 400}, "#87ceeb", 2),
                (3, "⚡ Коммутационное оборудование", "Агрегаторы и коммутаторы",
                 {'x': 500, 'y': 350, 'width': 700, 'height': 400}, "#3cb371", 3),
                (4, "🖥 Серверная", "Серверное оборудование",
                 {'x': 900, 'y': 0, 'width': 400, 'height': 700}, "#9370db", 4),
            ]

            for sid, name, desc, bounds, color, owner_id in sectors_data:
                sector = Sector(
                    id=sid, name=name, description=desc,
                    bounds=bounds, color=color, owner_id=owner_id
                )

                # Настраиваем права
                if sid == 1:  # Магистраль
                    sector.editors = {2, 3}  # manager1 и operator1
                    sector.viewers = {4, 5}  # operator2 и viewer1
                elif sid == 4:  # Серверная
                    sector.editors = {2, 4}  # manager1 и operator2
                    sector.viewers = {3, 5}  # operator1 и viewer1
                else:
                    sector.editors = {2}  # manager1
                    sector.viewers = {3, 4, 5}  # все остальные

                self.state.sectors[sid] = sector

            # Создаем ЕДИНУЮ сеть устройств
            self.state.devices = [
                # Магистральная сеть (сектор 1)
                {
                    'id': 1, 'name': 'Магистральный кросс',
                    'device_type': 'Main Cross-connect',
                    'category': 'GLOBAL_INPUT', 'x': 300, 'y': 200,
                    'width': 160, 'height': 100,
                    'sector_ids': [1],
                    'input_ports': [
                        {'id': 0, 'name': 'IN 1', 'port_type': 'input', 'x': 220, 'y': 170},
                        {'id': 1, 'name': 'IN 2', 'port_type': 'input', 'x': 220, 'y': 200},
                        {'id': 2, 'name': 'IN 3', 'port_type': 'input', 'x': 220, 'y': 230},
                    ],
                    'output_ports': [
                        {'id': 3, 'name': 'OUT 1', 'port_type': 'output', 'x': 380, 'y': 185},
                        {'id': 4, 'name': 'OUT 2', 'port_type': 'output', 'x': 380, 'y': 215},
                    ]
                },
                # Локальная сеть (сектор 2)
                {
                    'id': 2, 'name': 'Локальный кросс',
                    'device_type': 'Local Cross-connect',
                    'category': 'LOCAL_INPUT', 'x': 200, 'y': 500,
                    'width': 160, 'height': 100,
                    'sector_ids': [2],
                    'input_ports': [
                        {'id': 0, 'name': 'IN 1', 'port_type': 'input', 'x': 120, 'y': 470},
                        {'id': 1, 'name': 'IN 2', 'port_type': 'input', 'x': 120, 'y': 500},
                    ],
                    'output_ports': [
                        {'id': 2, 'name': 'OUT 1', 'port_type': 'output', 'x': 280, 'y': 485},
                        {'id': 3, 'name': 'OUT 2', 'port_type': 'output', 'x': 280, 'y': 515},
                    ]
                },
                # Коммутационное оборудование (сектор 3)
                {
                    'id': 3, 'name': 'Агрегатор',
                    'device_type': 'Aggregator',
                    'category': 'SWITCHES', 'x': 700, 'y': 500,
                    'width': 180, 'height': 120,
                    'sector_ids': [3],
                    'input_ports': [
                        {'id': 0, 'name': 'IN 1', 'port_type': 'input', 'x': 610, 'y': 460},
                        {'id': 1, 'name': 'IN 2', 'port_type': 'input', 'x': 610, 'y': 490},
                        {'id': 2, 'name': 'IN 3', 'port_type': 'input', 'x': 610, 'y': 520},
                    ],
                    'output_ports': [
                        {'id': 3, 'name': 'OUT 1', 'port_type': 'output', 'x': 790, 'y': 470},
                        {'id': 4, 'name': 'OUT 2', 'port_type': 'output', 'x': 790, 'y': 500},
                        {'id': 5, 'name': 'OUT 3', 'port_type': 'output', 'x': 790, 'y': 530},
                    ]
                },
                # Серверная (сектор 4)
                {
                    'id': 4, 'name': 'Сервер приложений 1',
                    'device_type': 'Application Server',
                    'category': 'SERVERS', 'x': 1050, 'y': 150,
                    'width': 160, 'height': 100,
                    'sector_ids': [4],
                    'input_ports': [
                        {'id': 0, 'name': 'IN 1', 'port_type': 'input', 'x': 970, 'y': 135},
                        {'id': 1, 'name': 'IN 2', 'port_type': 'input', 'x': 970, 'y': 165},
                    ],
                    'output_ports': [
                        {'id': 2, 'name': 'OUT 1', 'port_type': 'output', 'x': 1130, 'y': 150},
                    ]
                },
                {
                    'id': 5, 'name': 'Сервер БД',
                    'device_type': 'Database Server',
                    'category': 'SERVERS', 'x': 1050, 'y': 350,
                    'width': 160, 'height': 100,
                    'sector_ids': [4],
                    'input_ports': [
                        {'id': 0, 'name': 'IN 1', 'port_type': 'input', 'x': 970, 'y': 335},
                        {'id': 1, 'name': 'IN 2', 'port_type': 'input', 'x': 970, 'y': 365},
                    ],
                    'output_ports': []
                },
            ]

            # Привязываем устройства к секторам
            for device in self.state.devices:
                for sector_id in device.get('sector_ids', []):
                    self.state.add_device_to_sector(device['id'], sector_id)

            # Создаем соединения (межсекторные!)
            self.state.connections = [
                # Магистраль -> Локальная сеть (межсекторное)
                {
                    'device1_id': 1, 'port1_id': 3,
                    'device2_id': 2, 'port2_id': 0,
                    'cable_type': 'Fiber Optic', 'length': 50.0
                },
                # Локальная сеть -> Агрегатор
                {
                    'device1_id': 2, 'port1_id': 2,
                    'device2_id': 3, 'port2_id': 0,
                    'cable_type': 'Ethernet', 'length': 5.0
                },
                # Агрегатор -> Сервер приложений (межсекторное)
                {
                    'device1_id': 3, 'port1_id': 3,
                    'device2_id': 4, 'port2_id': 0,
                    'cable_type': 'Fiber Optic', 'length': 10.0
                },
                # Агрегатор -> Сервер БД (межсекторное)
                {
                    'device1_id': 3, 'port1_id': 4,
                    'device2_id': 5, 'port2_id': 0,
                    'cable_type': 'Fiber Optic', 'length': 10.0
                },
            ]

            # Настраиваем связи между секторами
            self.state.sectors[1].connected_sectors = {2}
            self.state.sectors[2].connected_sectors = {1, 3}
            self.state.sectors[3].connected_sectors = {2, 4}
            self.state.sectors[4].connected_sectors = {3}