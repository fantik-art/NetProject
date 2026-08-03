import time
from typing import Optional


class LockService:
    """Сервис управления блокировками секторов"""
    
    def __init__(self, state):
        self.state = state
        self.lock_timeout = 300  # 5 минут
    
    def acquire_lock(self, sector_id: int, user_id: int) -> dict:
        """Захват блокировки сектора"""
        sector = self.state.get_sector(sector_id)
        user = self.state.get_user(user_id)
        
        if not sector or not user:
            return {'success': False, 'error': 'Сектор или пользователь не найден'}
        
        # Проверяем права
        if not user.can_edit():
            return {'success': False, 'error': 'Недостаточно прав для редактирования'}
        
        # Проверяем существующую блокировку
        if sector.is_locked():
            if sector.locked_by == user_id:
                return {'success': True, 'message': 'Сектор уже заблокирован вами'}
            
            # Проверяем таймаут блокировки
            if time.time() - sector.locked_at > self.lock_timeout:
                # Принудительно снимаем блокировку
                sector.unlock(0)
            else:
                return {
                    'success': False,
                    'error': f'Сектор заблокирован пользователем {sector.locked_by_name}'
                }
        
        # Блокируем сектор
        sector.lock(user_id, user.username)
        
        return {
            'success': True,
            'locked_by': user_id,
            'locked_by_name': user.username,
            'locked_at': sector.locked_at
        }
    
    def release_lock(self, sector_id: int, user_id: int) -> dict:
        """Снятие блокировки"""
        sector = self.state.get_sector(sector_id)
        
        if not sector:
            return {'success': False, 'error': 'Сектор не найден'}
        
        if sector.unlock(user_id):
            return {'success': True, 'message': 'Блокировка снята'}
        
        return {'success': False, 'error': 'Не удалось снять блокировку'}
    
    def get_lock_status(self, sector_id: int) -> dict:
        """Получение статуса блокировки"""
        sector = self.state.get_sector(sector_id)
        
        if not sector:
            return {'is_locked': False}
        
        return {
            'is_locked': sector.is_locked(),
            'locked_by': sector.locked_by,
            'locked_by_name': sector.locked_by_name,
            'locked_at': sector.locked_at
        }