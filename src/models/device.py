"""Модель устройства."""

from dataclasses import dataclass, field
from typing import ClassVar, List

from .enums import DeviceCategory, PortType
from .port import Port
from config.constants import (
    DEVICE_WIDTH, DEVICE_HEADER_HEIGHT, DEVICE_FOOTER_HEIGHT,
    DEVICE_PORT_SPACING, DEVICE_MIN_PORT_AREA, DEVICE_MIN_HEIGHT,
)


@dataclass
class Device:
    """
    Сетевое устройство.

    Высота рассчитывается автоматически по количеству портов.
    """
    id: int
    name: str
    x: float = 100.0
    y: float = 100.0
    width: float = DEVICE_WIDTH
    height: float = DEVICE_MIN_HEIGHT
    device_type: str = "Switch"
    category: DeviceCategory = DeviceCategory.SWITCHES
    model: str = ""
    input_ports: List[Port] = field(default_factory=list)
    output_ports: List[Port] = field(default_factory=list)

    # ClassVar — не поля dataclass
    HEADER_HEIGHT: ClassVar[float] = DEVICE_HEADER_HEIGHT
    FOOTER_HEIGHT: ClassVar[float] = DEVICE_FOOTER_HEIGHT
    PORT_SPACING: ClassVar[float] = DEVICE_PORT_SPACING
    MIN_PORT_AREA: ClassVar[float] = DEVICE_MIN_PORT_AREA
    MIN_HEIGHT: ClassVar[float] = DEVICE_MIN_HEIGHT

    @property
    def ports(self) -> List[Port]:
        return self.input_ports + self.output_ports

    def calculate_height(self) -> float:
        """Высота по максимальному количеству портов на стороне."""
        max_ports = max(len(self.input_ports), len(self.output_ports))
        if max_ports == 0:
            return self.MIN_HEIGHT

        port_area = (max_ports + 1) * self.PORT_SPACING
        port_area = max(port_area, self.MIN_PORT_AREA)

        total = self.HEADER_HEIGHT + port_area + self.FOOTER_HEIGHT
        return max(total, self.MIN_HEIGHT)

    def update_port_positions(self) -> None:
        """Пересчитывает высоту и координаты портов."""
        self.height = self.calculate_height()

        if self.input_ports:
            top = self.y - self.height / 2 + self.HEADER_HEIGHT
            bottom = self.y + self.height / 2 - self.FOOTER_HEIGHT
            area_h = bottom - top
            for i, port in enumerate(self.input_ports):
                port.x = self.x - self.width / 2
                port.y = top + (i + 1) * (area_h / (len(self.input_ports) + 1))

        if self.output_ports:
            top = self.y - self.height / 2 + self.HEADER_HEIGHT
            bottom = self.y + self.height / 2 - self.FOOTER_HEIGHT
            area_h = bottom - top
            for i, port in enumerate(self.output_ports):
                port.x = self.x + self.width / 2
                port.y = top + (i + 1) * (area_h / (len(self.output_ports) + 1))

    def add_port(self, name: str, port_type: PortType,
                 connector: str = "Ethernet", speed: str = "1Gb") -> Port:
        """Добавляет порт с указанными параметрами."""
        max_id = max((p.id for p in self.ports), default=-1)
        port = Port(
            id=max_id + 1,
            name=name,
            port_type=port_type,
            connector=connector,
            speed=speed,
        )
        if port_type == PortType.INPUT:
            self.input_ports.append(port)
        else:
            self.output_ports.append(port)
        return port