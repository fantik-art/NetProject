"""Модель соединения и группы."""

from dataclasses import dataclass
from typing import Optional

from .port import Port


@dataclass
class Connection:
    """Соединение между двумя портами."""
    port1: Port
    port2: Port
    cable_type: str = "Ethernet"
    length: float = 2.0
    group_id: Optional[int] = None


@dataclass
class ConnectionGroup:
    """Логическая группа соединений (канал)."""
    id: int
    name: str
    color: str
    visible: bool = True