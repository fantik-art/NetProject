from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from .user import User
from .sector import Sector


@dataclass
class ServerState:
    """Глобальное состояние сервера - ЕДИНАЯ сеть"""

    # Пользователи
    users: Dict[int, User] = field(default_factory=dict)

    # Сектора (логические части сети)
    sectors: Dict[int, Sector] = field(default_factory=dict)

    # ЕДИНАЯ модель сети
    devices: List[dict] = field(default_factory=list)
    connections: List[dict] = field(default_factory=list)
    groups: List[dict] = field(default_factory=list)

    # Настройки отображения
    settings: dict = field(default_factory=lambda: {
        'show_grid': True,
        'show_labels': True,
        'show_sector_bounds': True
    })

    # Версионирование
    global_version: int = 1

    def get_user(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        for user in self.users.values():
            if user.username == username:
                return user
        return None

    def get_sector(self, sector_id: int) -> Optional[Sector]:
        return self.sectors.get(sector_id)

    def get_user_sectors(self, user_id: int) -> List[dict]:
        """Получение секторов, доступных пользователю"""
        user = self.get_user(user_id)
        if not user:
            return []

        if user.is_admin():
            return [s.to_dict() for s in self.sectors.values()]

        return [
            s.to_dict() for s in self.sectors.values()
            if s.can_view(user_id, user.role)
        ]

    def get_visible_devices(self, user_id: int, view_mode: str = 'full',
                            sector_ids: List[int] = None) -> List[dict]:
        """Получение устройств, видимых пользователю"""
        user = self.get_user(user_id)
        if not user:
            return []

        # Админ видит всё
        if user.is_admin() and view_mode == 'full':
            return self.devices

        # Определяем видимые сектора
        visible_sectors = set()

        if view_mode == 'full' and user.role in ('admin', 'manager'):
            # Менеджер может видеть всё, но редактировать только свои сектора
            return self.devices

        elif view_mode == 'single' and sector_ids:
            visible_sectors = set(sector_ids)

        elif view_mode == 'multi' and sector_ids:
            visible_sectors = set(sector_ids)

        else:
            # По умолчанию - только свои сектора
            for sector in self.sectors.values():
                if sector.can_view(user_id, user.role):
                    visible_sectors.add(sector.id)

        # Собираем ID устройств из видимых секторов
        visible_device_ids = set()
        for sector_id in visible_sectors:
            sector = self.sectors.get(sector_id)
            if sector:
                visible_device_ids.update(sector.device_ids)

        # Если пользователь не видит ни одного сектора, показываем всё (гость)
        if not visible_device_ids and not user.is_admin():
            return []

        # Фильтруем устройства
        if visible_device_ids:
            return [d for d in self.devices if d.get('id') in visible_device_ids]

        return self.devices

    def get_visible_connections(self, user_id: int, view_mode: str = 'full',
                                sector_ids: List[int] = None) -> List[dict]:
        """Получение соединений, видимых пользователю"""
        visible_devices = self.get_visible_devices(user_id, view_mode, sector_ids)
        visible_device_ids = {d.get('id') for d in visible_devices}

        return [
            c for c in self.connections
            if (c.get('device1_id') in visible_device_ids or
                c.get('device2_id') in visible_device_ids)
        ]

    def get_state_for_user(self, user_id: int, view_mode: str = 'full',
                           sector_ids: List[int] = None) -> dict:
        """Получение состояния сети для конкретного пользователя"""
        user = self.get_user(user_id)

        if not sector_ids:
            sector_ids = []

        # По умолчанию показываем всё
        visible_devices = list(self.devices)
        visible_connections = list(self.connections)

        if user and not user.is_admin() and view_mode != 'full':
            # Собираем ID устройств из выбранных секторов
            selected_device_ids = set()
            selected_sectors = []

            for sid in sector_ids:
                sector = self.sectors.get(sid)
                if sector and sector.can_view(user_id, user.role):
                    selected_device_ids.update(sector.device_ids)
                    selected_sectors.append(sector)

            if selected_device_ids:
                # Находим межсекторные соединения
                connected_device_ids = set(selected_device_ids)

                # Добавляем устройства из соседних секторов,
                # с которыми есть соединения
                for conn in self.connections:
                    dev1_id = conn.get('device1_id')
                    dev2_id = conn.get('device2_id')

                    # Если одно устройство в выбранном секторе, а другое нет
                    if dev1_id in selected_device_ids and dev2_id not in selected_device_ids:
                        connected_device_ids.add(dev2_id)
                    elif dev2_id in selected_device_ids and dev1_id not in selected_device_ids:
                        connected_device_ids.add(dev1_id)

                # Фильтруем устройства
                visible_devices = [
                    d for d in self.devices
                    if d.get('id') in connected_device_ids
                ]

                # Фильтруем соединения - показываем все, где есть хотя бы одно
                # устройство из выбранных секторов
                visible_connections = [
                    c for c in self.connections
                    if (c.get('device1_id') in connected_device_ids or
                        c.get('device2_id') in connected_device_ids)
                ]

                # Помечаем устройства из других секторов
                for device in visible_devices:
                    device_sectors = self.get_device_sectors(device.get('id'))
                    device['_external'] = not any(s in sector_ids for s in device_sectors)
                    device['_external_sectors'] = [
                        self.sectors[s].name for s in device_sectors
                        if s not in sector_ids and s in self.sectors
                    ]

        # Определяем права и видимые сектора
        can_edit = False
        visible_sectors = []

        for sector in self.sectors.values():
            if user:
                if user.is_admin():
                    can_edit = True
                    sector_info = sector.to_dict()
                    sector_info['can_edit'] = True
                    sector_info['is_current'] = sector.id in sector_ids
                    visible_sectors.append(sector_info)
                elif sector.can_view(user_id, user.role):
                    sector_info = sector.to_dict()
                    sector_info['can_edit'] = sector.can_edit(user_id, user.role)
                    sector_info['is_current'] = sector.id in sector_ids
                    visible_sectors.append(sector_info)
                    if sector.can_edit(user_id, user.role) and sector.id in sector_ids:
                        can_edit = True

        # Добавляем информацию о межсекторных связях
        inter_sector_connections = []
        for conn in visible_connections:
            dev1_id = conn.get('device1_id')
            dev2_id = conn.get('device2_id')

            dev1 = next((d for d in visible_devices if d.get('id') == dev1_id), None)
            dev2 = next((d for d in visible_devices if d.get('id') == dev2_id), None)

            if dev1 and dev2:
                sectors1 = set(dev1.get('sector_ids', []))
                sectors2 = set(dev2.get('sector_ids', []))

                # Если устройства в разных секторах
                if sectors1 != sectors2:
                    inter_sector_connections.append({
                        'connection': conn,
                        'from_sectors': list(sectors1),
                        'to_sectors': list(sectors2)
                    })

        return {
            'devices': visible_devices,
            'connections': visible_connections,
            'inter_sector_connections': inter_sector_connections,
            'groups': self.groups,
            'sectors': visible_sectors,
            'view_mode': view_mode,
            'sector_ids': sector_ids or [],
            'can_edit': can_edit,
            'global_version': self.global_version,
            'settings': self.settings
        }

    def add_device_to_sector(self, device_id: int, sector_id: int):
        """Добавление устройства в сектор"""
        sector = self.get_sector(sector_id)
        if sector:
            sector.device_ids.add(device_id)

    def remove_device_from_sector(self, device_id: int, sector_id: int):
        """Удаление устройства из сектора"""
        sector = self.get_sector(sector_id)
        if sector:
            sector.device_ids.discard(device_id)

    def get_device_sectors(self, device_id: int) -> List[int]:
        """Получение секторов, к которым принадлежит устройство"""
        result = []
        for sector in self.sectors.values():
            if device_id in sector.device_ids:
                result.append(sector.id)
        return result