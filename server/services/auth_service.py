import hashlib
from typing import Optional


class AuthService:
    """Сервис аутентификации"""
    
    def __init__(self, state):
        self.state = state
    
    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """Аутентификация пользователя"""
        user = self.state.get_user_by_username(username)
        
        if not user:
            return None
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        if user.password_hash != password_hash:
            return None
        
        return {
            'success': True,
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'full_name': user.full_name,
            'sectors': self.state.get_user_sectors(user.id)
        }
    
    def validate_session(self, user_id: int, session_id: str) -> bool:
        """Проверка сессии"""
        user = self.state.get_user(user_id)
        if not user:
            return False
        return user.session_id == session_id