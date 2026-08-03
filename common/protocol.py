import json
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from .enums import MessageType


@dataclass
class Message:
    """Базово сооебщение протокола"""
    type: MessageType
    sender_id: int = 0
    sector_id: int = 0
    timestamp: float = field(default_factory=time.time)
    payload: dict = field(default_factory=dict)

    def serialize(self) -> bytes:
        """Сериализация в байты"""
        data = {
            'type': self.type.value,
            'sender_id': self.sender_id,
            'sector_id': self.sector_id,
            'timestamp': self.timestamp,
            'payload': self.payload
        }
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        header = struct.pack('!I', len(json_data))
        return header + json_data

    @classmethod
    def deserialize(cls, data: bytes) -> 'Message':
        """Десериализация из байтов"""
        obj = json.loads(data.decode('utf-8'))
        return cls(
            type=MessageType(obj['type']),
            sender_id=obj['sender_id'],
            sector_id=obj['sector_id'],
            timestamp=obj['timestamp'],
            payload=obj['payload']
        )