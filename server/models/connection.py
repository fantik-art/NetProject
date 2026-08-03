from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Connection:
    """Модель соединения"""
    port1: object
    port2: object
    cable_type: str = "Ethernet"
    length: float = 1.0
    group_id: Optional[int] = None

    def to_dict(self, model=None) -> dict:
        dev1 = model.find_device_by_port(self.port1) if model else None
        dev2 = model.find_device_by_port(self.port2) if model else None
        return {
            'device1_id': dev1.id if dev1 else -1,
            'port1_id': self.port1.id if hasattr(self.port1, 'id') else self.port1.get('id', 0),
            'device2_id': dev2.id if dev2 else -1,
            'port2_id': self.port2.id if hasattr(self.port2, 'id') else self.port2.get('id', 0),
            'cable_type': self.cable_type,
            'length': self.length,
            'group_id': self.group_id
        }


@dataclass
class ConnectionGroup:
    """Модель группы соединений"""
    id: int
    name: str
    color: str
    visible: bool = True

    def get_connections(self, model) -> List[Connection]:
        return [c for c in model.connections if c.group_id == self.id]

    def cable_length(self, model) -> float:
        return sum(c.length for c in self.get_connections(model))

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'visible': self.visible
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ConnectionGroup':
        return cls(
            id=data['id'],
            name=data['name'],
            color=data['color'],
            visible=data.get('visible', True)
        )