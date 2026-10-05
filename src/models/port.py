"""Модель порта."""

from dataclasses import dataclass
from .enums import PortType


@dataclass
class Port:
    """
    Порт устройства.

    Attributes:
        id: Уникальный ID внутри устройства
        name: Читаемое имя (например, "eth0", "OUT 1")
        port_type: Входной (▼) или выходной (■)
        connector: Тип разъёма (SFP LC, SFP MPO, FC, Ethernet, RJ45)
        speed: Скорость (1Gb, 10Gb, 100Gb)
        x, y: Координаты центра
    """
    id: int
    name: str
    port_type: PortType = PortType.OUTPUT
    connector: str = "Ethernet"
    speed: str = "1Gb"
    x: float = 0.0
    y: float = 0.0

    def label(self) -> str:
        """Короткая подпись для отображения рядом с портом."""
        return f"{self.name} · {self.speed}"

    def tooltip(self) -> str:
        """Полная информация для всплывающей подсказки."""
        direction = "Вход" if self.port_type == PortType.INPUT else "Выход"
        return (
            f"{self.name}\n"
            f"{direction} · {self.connector} · {self.speed}"
        )