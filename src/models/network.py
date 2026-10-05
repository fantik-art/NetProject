"""Модель всей сети."""

import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal

from .device import Device
from .connection import Connection, ConnectionGroup
from .enums import DeviceCategory, PortType, CATEGORY_MAP, CATEGORY_KEY_MAP
from .port import Port
from config.constants import (
    GROUP_PALETTE, CONNECTOR_GROUPS, CONNECTOR_CABLE_COMPAT,
)
from config.templates import DEVICE_TEMPLATES


class NetworkModel(QObject):
    """Модель сети: устройства, соединения, группы."""

    data_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.devices: List[Device] = []
        self.connections: List[Connection] = []
        self.groups: List[ConnectionGroup] = []

        self.next_device_id = 0
        self.next_group_id = 0

        self.filter_text = ""
        self.show_port_labels = True
        self.show_connection_labels = True
        self.show_grid = True

    # ========================================================
    #  УВЕДОМЛЕНИЯ
    # ========================================================

    def notify(self) -> None:
        """Уведомляет наблюдателей об изменении."""
        self.data_changed.emit()

    # ========================================================
    #  УСТРОЙСТВА
    # ========================================================

    def add_device_from_template(self, template_name: str,
                                 x: float = 100, y: float = 100) -> Optional[Device]:
        """Создаёт устройство по шаблону."""
        template = DEVICE_TEMPLATES.get(template_name)
        if not template:
            return None

        device = Device(
            id=self.next_device_id,
            name=f"{template_name} #{self.next_device_id}",
            x=x, y=y,
            device_type=template["device_type"],
            category=CATEGORY_MAP[template["category"]],
            model=template.get("model", ""),
        )

        for name, connector, speed in template.get("input_ports", []):
            device.add_port(name, PortType.INPUT, connector, speed)

        for name, connector, speed in template.get("output_ports", []):
            device.add_port(name, PortType.OUTPUT, connector, speed)

        device.update_port_positions()
        self.next_device_id += 1
        self.devices.append(device)
        self.notify()
        return device

    def add_empty_device(self, device_type: str,
                         category: DeviceCategory,
                         x: float = 100, y: float = 100) -> Device:
        """Создаёт пустое устройство без портов."""
        device = Device(
            id=self.next_device_id,
            name=f"{device_type} #{self.next_device_id}",
            x=x, y=y,
            device_type=device_type,
            category=category,
        )
        self.next_device_id += 1
        self.devices.append(device)
        self.notify()
        return device

    def remove_device(self, device: Device) -> None:
        """Удаляет устройство и все его соединения."""
        self.connections = [
            c for c in self.connections
            if c.port1 not in device.ports and c.port2 not in device.ports
        ]
        if device in self.devices:
            self.devices.remove(device)
        self.notify()

    def move_device(self, device: Device, x: float, y: float) -> None:
        """Перемещает устройство."""
        device.x = x
        device.y = y
        device.update_port_positions()
        self.notify()

    def find_device_by_port(self, port: Port) -> Optional[Device]:
        """Находит устройство по порту."""
        for d in self.devices:
            if port in d.ports:
                return d
        return None

    def get_device_by_id(self, device_id: int) -> Optional[Device]:
        for d in self.devices:
            if d.id == device_id:
                return d
        return None

    # ========================================================
    #  СОЕДИНЕНИЯ
    # ========================================================

    def is_port_connected(self, port: Port) -> bool:
        """Проверяет, занят ли порт."""
        return any(port is c.port1 or port is c.port2 for c in self.connections)

    def _connectors_compatible(self, port1: Port, port2: Port) -> Tuple[bool, str]:
        """Проверяет совместимость разъёмов."""
        c1, c2 = port1.connector, port2.connector

        for group_name, connectors in CONNECTOR_GROUPS.items():
            if c1 in connectors and c2 in connectors:
                return True, ""

        return False, (
            f"Разъёмы несовместимы: {c1} ↔ {c2}\n"
            f"Соединение возможно только в пределах одной группы:\n"
            f"  • LC: SFP LC, FC\n"
            f"  • MPO: SFP MPO\n"
            f"  • Медь: Ethernet, RJ45"
        )

    def can_connect(self, port1: Port, port2: Port) -> Tuple[bool, str]:
        """Полная проверка возможности соединения."""
        if port1.port_type == port2.port_type:
            return False, "Соединение только между выходом и входом!"

        out_port = port1 if port1.port_type == PortType.OUTPUT else port2
        in_port = port2 if port1.port_type == PortType.OUTPUT else port1

        if self.is_port_connected(out_port):
            dev = self.find_device_by_port(out_port)
            name = dev.name if dev else "?"
            return False, f"Порт «{out_port.name}» ({name}) уже занят."

        if self.is_port_connected(in_port):
            dev = self.find_device_by_port(in_port)
            name = dev.name if dev else "?"
            return False, f"Порт «{in_port.name}» ({name}) уже занят."

        dev1 = self.find_device_by_port(out_port)
        dev2 = self.find_device_by_port(in_port)
        if dev1 and dev2 and dev1.id == dev2.id:
            return False, "Нельзя соединить порты одного устройства."

        return self._connectors_compatible(out_port, in_port)

    def add_connection(self, port1: Port, port2: Port,
                       cable_type: str = "Ethernet",
                       length: float = 2.0,
                       group_id: Optional[int] = None) -> Optional[Connection]:
        """Добавляет соединение с проверкой."""
        ok, _ = self.can_connect(port1, port2)
        if not ok:
            return None

        for c in self.connections:
            if (c.port1 is port1 and c.port2 is port2) or \
               (c.port1 is port2 and c.port2 is port1):
                return None

        if port1.port_type == PortType.OUTPUT:
            conn = Connection(port1, port2, cable_type, length, group_id)
        else:
            conn = Connection(port2, port1, cable_type, length, group_id)

        self.connections.append(conn)
        self.notify()
        return conn

    def remove_connections_for_port(self, port: Port) -> None:
        self.connections = [
            c for c in self.connections if c.port1 != port and c.port2 != port
        ]
        self.notify()

    def get_visible_connections(self) -> List[Connection]:
        """Соединения с учётом фильтра групп."""
        if not self.filter_text:
            return list(self.connections)

        visible_ids = {
            g.id for g in self.groups
            if self.filter_text in g.name.lower()
        }
        return [
            c for c in self.connections
            if c.group_id is None or c.group_id in visible_ids
        ]

    def set_filter(self, text: str) -> None:
        self.filter_text = text.strip().lower()
        self.notify()

    # ========================================================
    #  ГРУППЫ
    # ========================================================

    def create_group(self, name: str, color: Optional[str] = None) -> ConnectionGroup:
        """Создаёт группу с указанным или автовыбранным цветом."""
        if color is None:
            color = GROUP_PALETTE[self.next_group_id % len(GROUP_PALETTE)]

        group = ConnectionGroup(self.next_group_id, name, color)
        self.next_group_id += 1
        self.groups.append(group)
        self.notify()
        return group

    def remove_group(self, group: ConnectionGroup) -> None:
        for c in self.connections:
            if c.group_id == group.id:
                c.group_id = None
        if group in self.groups:
            self.groups.remove(group)
        self.notify()

    def update_group_color(self, group: ConnectionGroup, color: str) -> None:
        group.color = color
        self.notify()

    def get_group(self, group_id: int) -> Optional[ConnectionGroup]:
        for g in self.groups:
            if g.id == group_id:
                return g
        return None

    def get_group_connections(self, group: ConnectionGroup) -> List[Connection]:
        return [c for c in self.connections if c.group_id == group.id]

    # ========================================================
    #  СЕРИАЛИЗАЦИЯ
    # ========================================================

    def to_dict(self) -> dict:
        return {
            "devices": [self._device_to_dict(d) for d in self.devices],
            "connections": self._connections_to_dict(),
            "groups": [
                {
                    "id": g.id, "name": g.name,
                    "color": g.color, "visible": g.visible,
                } for g in self.groups
            ],
            "settings": {
                "show_port_labels": self.show_port_labels,
                "show_connection_labels": self.show_connection_labels,
                "show_grid": self.show_grid,
            },
            "counters": {
                "next_device_id": self.next_device_id,
                "next_group_id": self.next_group_id,
            },
        }

    @staticmethod
    def _device_to_dict(device: Device) -> dict:
        return {
            "id": device.id,
            "name": device.name,
            "x": device.x, "y": device.y,
            "width": device.width, "height": device.height,
            "device_type": device.device_type,
            "category": CATEGORY_KEY_MAP[device.category],
            "model": device.model,
            "input_ports": [
                {"id": p.id, "name": p.name,
                 "connector": p.connector, "speed": p.speed}
                for p in device.input_ports
            ],
            "output_ports": [
                {"id": p.id, "name": p.name,
                 "connector": p.connector, "speed": p.speed}
                for p in device.output_ports
            ],
        }

    def _connections_to_dict(self) -> List[dict]:
        result = []
        for c in self.connections:
            dev1 = self.find_device_by_port(c.port1)
            dev2 = self.find_device_by_port(c.port2)
            if dev1 and dev2:
                result.append({
                    "device1_id": dev1.id, "port1_id": c.port1.id,
                    "device2_id": dev2.id, "port2_id": c.port2.id,
                    "cable_type": c.cable_type,
                    "length": c.length,
                    "group_id": c.group_id,
                })
        return result

    def from_dict(self, data: dict) -> None:
        self.devices.clear()
        self.connections.clear()
        self.groups.clear()

        settings = data.get("settings", {})
        self.show_port_labels = settings.get("show_port_labels", True)
        self.show_connection_labels = settings.get("show_connection_labels", True)
        self.show_grid = settings.get("show_grid", True)

        device_map: Dict[int, Device] = {}
        for dd in data.get("devices", []):
            device = Device(
                id=dd["id"], name=dd["name"],
                x=dd["x"], y=dd["y"],
                width=dd.get("width", 200),
                height=dd.get("height", 90),
                device_type=dd["device_type"],
                category=CATEGORY_MAP[dd["category"]],
                model=dd.get("model", ""),
            )
            for p in dd.get("input_ports", []):
                device.input_ports.append(Port(
                    id=p["id"], name=p["name"],
                    port_type=PortType.INPUT,
                    connector=p.get("connector", "Ethernet"),
                    speed=p.get("speed", "1Gb"),
                ))
            for p in dd.get("output_ports", []):
                device.output_ports.append(Port(
                    id=p["id"], name=p["name"],
                    port_type=PortType.OUTPUT,
                    connector=p.get("connector", "Ethernet"),
                    speed=p.get("speed", "1Gb"),
                ))
            device.update_port_positions()
            self.devices.append(device)
            device_map[device.id] = device

        for gd in data.get("groups", []):
            self.groups.append(ConnectionGroup(
                gd["id"], gd["name"], gd["color"],
                gd.get("visible", True),
            ))

        for cd in data.get("connections", []):
            dev1 = device_map.get(cd["device1_id"])
            dev2 = device_map.get(cd["device2_id"])
            if not dev1 or not dev2:
                continue
            port1 = next((p for p in dev1.ports if p.id == cd["port1_id"]), None)
            port2 = next((p for p in dev2.ports if p.id == cd["port2_id"]), None)
            if port1 and port2:
                self.connections.append(Connection(
                    port1, port2,
                    cd.get("cable_type", "Ethernet"),
                    cd.get("length", 2.0),
                    cd.get("group_id"),
                ))

        counters = data.get("counters", {})
        self.next_device_id = counters.get("next_device_id", self._calc_next_device_id())
        self.next_group_id = counters.get("next_group_id", self._calc_next_group_id())

        self.notify()

    def _calc_next_device_id(self) -> int:
        return max((d.id for d in self.devices), default=-1) + 1

    def _calc_next_group_id(self) -> int:
        return max((g.id for g in self.groups), default=-1) + 1

    def remove_connection(self, connection: Connection) -> None:
        """
        Удаляет конкретное соединение.

        Args:
            connection: соединение для удаления
        """
        if connection in self.connections:
            self.connections.remove(connection)
            self.notify()