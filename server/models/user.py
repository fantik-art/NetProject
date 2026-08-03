from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    """Модель пользователя сервера"""
    id: int
    username: str
    password_hash: str
    role: str  # admin, manager, operator, viewer
    full_name: str = ""
    email: str = ""
    
    # Состояние подключения
    is_online: bool = False
    current_sector_id: int = 0
    session_id: str = ""
    
    # Права доступа к секторам
    accessible_sectors: list = field(default_factory=list)
    owned_sectors: list = field(default_factory=list)
    
    def can_edit(self) -> bool:
        """Может ли пользователь редактировать"""
        return self.role in ('admin', 'manager', 'operator')
    
    def can_view(self) -> bool:
        """Может ли пользователь просматривать"""
        return True
    
    def is_admin(self) -> bool:
        return self.role == 'admin'
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'full_name': self.full_name,
            'is_online': self.is_online
        }