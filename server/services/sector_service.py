from typing import Optional, List
from ..models.sector import Sector


class SectorService:
    """Сервис управления секторами"""
    
    def __init__(self, state):
        self.state = state
    
    def create_sector(self, name: str, owner_id: int, description: str = "") -> Sector:
        """Создание нового сектора"""
        sector_id = len(self.state.sectors) + 1
        
        sector = Sector(
            id=sector_id,
            name=name,
            description=description,
            owner_id=owner_id
        )
        
        self.state.sectors[sector_id] = sector
        
        # Добавляем владельцу права
        user = self.state.get_user(owner_id)
        if user:
            user.owned_sectors.append(sector_id)
            user.accessible_sectors.append(sector_id)
        
        return sector
    
    def get_sector_state(self, sector_id: int) -> Optional[dict]:
        """Получение состояния сектора"""
        sector = self.state.get_sector(sector_id)
        if not sector:
            return None
        return sector.get_state()
    
    def update_device(self, sector_id: int, device_data: dict) -> bool:
        """Обновление устройства в секторе"""
        sector = self.state.get_sector(sector_id)
        if not sector:
            return False
        
        device_id = device_data.get('id')
        
        # Ищем существующее устройство
        for i, dev in enumerate(sector.devices):
            if dev.get('id') == device_id:
                sector.devices[i].update(device_data)
                sector.version += 1
                return True
        
        # Добавляем новое
        sector.devices.append(device_data)
        sector.version += 1
        return True
    
    def remove_device(self, sector_id: int, device_id: int) -> bool:
        """Удаление устройства"""
        sector = self.state.get_sector(sector_id)
        if not sector:
            return False
        
        # Удаляем связанные соединения
        sector.connections = [
            c for c in sector.connections
            if c.get('device1_id') != device_id and c.get('device2_id') != device_id
        ]
        
        # Удаляем устройство
        sector.devices = [d for d in sector.devices if d.get('id') != device_id]
        sector.version += 1
        return True
    
    def add_connection(self, sector_id: int, connection_data: dict) -> bool:
        """Добавление соединения"""
        sector = self.state.get_sector(sector_id)
        if not sector:
            return False
        
        # Проверка на дубликат
        for conn in sector.connections:
            if (conn.get('device1_id') == connection_data.get('device1_id') and
                conn.get('port1_id') == connection_data.get('port1_id') and
                conn.get('device2_id') == connection_data.get('device2_id') and
                conn.get('port2_id') == connection_data.get('port2_id')):
                return False
        
        sector.connections.append(connection_data)
        sector.version += 1
        return True