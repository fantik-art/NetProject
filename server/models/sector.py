from dataclasses import dataclass, field
from typing import Dict, Set, List, Optional
import time


@dataclass
class Sector:
    """Сектор сети - логическая часть общей инфраструктуры"""
    id: int
    name: str
    description: str = ""

    # Границы сектора на общей карте (для визуального выделения)
    bounds: dict = field(default_factory=lambda: {
        'x': 0, 'y': 0, 'width': 800, 'height': 600
    })
    color: str = "#45475a"  # Цвет рамки сектора

    # Привязка к пользователям и ролям
    owner_id: int = 0
    team_id: int = 0

    # Устройства, принадлежащие сектору (хранятся в общем состоянии)
    device_ids: Set[int] = field(default_factory=set)

    # Права доступа
    editors: Set[int] = field(default_factory=set)  # Кто может редактировать
    viewers: Set[int] = field(default_factory=set)  # Кто может только смотреть

    # Активные пользователи
    active_users: Set[int] = field(default_factory=set)

    # Блокировка
    locked_by: int = 0
    locked_by_name: str = ""
    locked_at: float = 0.0

    # Версионирование
    version: int = 1

    # Связи с другими секторами (для отображения межсекторных соединений)
    connected_sectors: Set[int] = field(default_factory=set)

    def is_locked(self) -> bool:
        return self.locked_by > 0

    def can_edit(self, user_id: int, user_role: str) -> bool:
        """Проверка прав на редактирование"""
        if user_role == 'admin':
            return True
        if user_role == 'viewer':
            return False
        return user_id in self.editors or user_id == self.owner_id

    def can_view(self, user_id: int, user_role: str) -> bool:
        """Проверка прав на просмотр"""
        if user_role == 'admin':
            return True
        return (user_id in self.viewers or
                user_id in self.editors or
                user_id == self.owner_id)

    def lock(self, user_id: int, username: str) -> bool:
        if self.is_locked() and self.locked_by != user_id:
            return False
        self.locked_by = user_id
        self.locked_by_name = username
        self.locked_at = time.time()
        return True

    def unlock(self, user_id: int) -> bool:
        if self.locked_by == user_id or user_id == 0:  # 0 = admin force
            self.locked_by = 0
            self.locked_by_name = ""
            self.locked_at = 0
            return True
        return False

    def add_user(self, user_id: int):
        self.active_users.add(user_id)

    def remove_user(self, user_id: int):
        self.active_users.discard(user_id)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'bounds': self.bounds,
            'color': self.color,
            'owner_id': self.owner_id,
            'device_ids': list(self.device_ids),
            'active_users': len(self.active_users),
            'is_locked': self.is_locked(),
            'locked_by_name': self.locked_by_name,
            'version': self.version,
            'connected_sectors': list(self.connected_sectors)
        }