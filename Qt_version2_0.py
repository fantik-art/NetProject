"""
Network Visualizer v2.0 — Визуализация сетевой инфраструктуры.

Полностью переработанная версия с поддержкой:
  - Типов портов (SFP LC, SFP MPO, FC, MPO, Ethernet)
  - Скоростей (100Gb, 10Gb, 1Gb)
  - Типов кабелей (Optical LC, Optical MPO, Infiniband, Ethernet)
  - Классов-фабрик устройств для быстрого создания типовых конфигураций
  - Динамической высоты устройств по количеству портов
  - Проверки занятости портов
  - Групп соединений с настраиваемым цветом
  - Сохранения/загрузки в JSON

Архитектура: MVC
  - Model: NetworkModel, Device, Port, Connection, ConnectionGroup
  - View: NetworkCanvas (отрисовка, взаимодействие)
  - Controller: NetworkController (связь Model и View)
"""

import sys
import json
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, ClassVar
from enum import Enum
from collections import defaultdict
from functools import partial

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QGroupBox, QFrame,
    QFileDialog, QMessageBox, QComboBox, QListWidget, QListWidgetItem,
    QSplitter, QMenu, QInputDialog, QDialog, QFormLayout,
    QDoubleSpinBox, QDialogButtonBox, QScrollArea, QSpinBox,
    QToolBar, QStatusBar, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QGridLayout, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QObject, pyqtSignal, QPointF, QRectF, QSize
)
from PyQt6.QtGui import (
    QPainter, QPainterPath, QPen, QBrush, QColor, QFont,
    QPolygonF, QAction, QIcon, QPixmap, QKeySequence
)


# ============================================================
#  ПЕРЕЧИСЛЕНИЯ
# ============================================================

class PortType(Enum):
    """Тип порта: входной или выходной."""
    INPUT = "input"
    OUTPUT = "output"


class DeviceCategory(Enum):
    """Категория устройства."""
    GLOBAL_INPUT = "Входные (глобальные)"
    LOCAL_INPUT = "Входные (локальные)"
    SWITCHES = "Коммутаторы"
    SERVERS = "Сервера"


class PortConnector(Enum):
    """Тип разъёма порта."""
    SFP_LC = "SFP LC"
    SFP_MPO = "SFP MPO"
    FC = "FC"
    MPO = "MPO"
    ETHERNET = "Ethernet"
    RJ45 = "RJ45"


class PortSpeed(Enum):
    """Скорость порта."""
    GB_1 = "1Gb"
    GB_10 = "10Gb"
    GB_100 = "100Gb"


class CableType(Enum):
    """Тип кабеля."""
    OPTICAL_LC = "Optical LC"
    OPTICAL_MPO = "Optical MPO"
    INFINIBAND = "Infiniband"
    ETHERNET = "Ethernet"


# ✅ Цвета кабелей
CABLE_COLORS = {
    "Optical LC": "#f59e0b",  # желто-оранжевый
    "Optical MPO": "#8b5cf6",  # фиолетовый
    "Infiniband": "#4b5563",  # тёмно-серый
    "Ethernet": "#9ca3af",  # серый
}

# ✅ Стили линий для каждого типа кабеля
CABLE_STYLES = {
    "Optical LC": Qt.PenStyle.SolidLine,
    "Optical MPO": Qt.PenStyle.DashLine,
    "Infiniband": Qt.PenStyle.SolidLine,
    "Ethernet": Qt.PenStyle.SolidLine,
}

# ✅ Совместимость разъёмов с кабелями
CONNECTOR_CABLE_COMPATIBILITY = {
    "SFP LC": ["Optical LC"],
    "SFP MPO": ["Optical MPO"],
    "FC": ["Optical LC"],
    "MPO": ["Optical MPO"],
    "Ethernet": ["Ethernet", "Infiniband"],
    "RJ45": ["Ethernet"],
}

# ✅ Цвета разъёмов для отрисовки портов
CONNECTOR_COLORS = {
    "SFP LC": "#f59e0b",
    "SFP MPO": "#8b5cf6",
    "FC": "#f97316",
    "MPO": "#a855f7",
    "Ethernet": "#9ca3af",
    "RJ45": "#6b7280",
}


# ============================================================
#  МОДЕЛИ ДАННЫХ
# ============================================================

@dataclass
class Port:
    """
    Порт устройства.

    Attributes:
        id: Уникальный идентификатор порта
        name: Имя порта (например "eth0", "sfp1")
        port_type: Входной (▼) или выходной (■)
        connector: Тип разъёма (SFP LC, MPO и т.д.)
        speed: Скорость (1Gb, 10Gb, 100Gb)
        x, y: Координаты центра порта
    """
    id: int
    name: str
    port_type: PortType = PortType.OUTPUT
    connector: str = "Ethernet"
    speed: str = "1Gb"
    x: float = 0.0
    y: float = 0.0

    def label(self) -> str:
        """Возвращает краткую подпись порта для отображения."""
        return f"{self.name} [{self.speed}]"

    def full_info(self) -> str:
        """Возвращает полную информацию о порте."""
        return f"{self.name} • {self.connector} • {self.speed}"


@dataclass
class Device:
    """
    Сетевое устройство.

    ВАЖНО: Высота устройства динамическая — пересчитывается
    автоматически в зависимости от количества портов.
    """
    id: int
    name: str
    x: float = 100.0
    y: float = 100.0
    width: float = 180.0
    height: float = 100.0
    device_type: str = "Switch"
    category: DeviceCategory = DeviceCategory.SWITCHES
    model: str = ""
    input_ports: List[Port] = field(default_factory=list)
    output_ports: List[Port] = field(default_factory=list)

    # ✅ ClassVar — не поля dataclass
    HEADER_HEIGHT: ClassVar[float] = 26.0
    FOOTER_HEIGHT: ClassVar[float] = 28.0
    PORT_SPACING: ClassVar[float] = 20.0
    MIN_PORT_AREA_HEIGHT: ClassVar[float] = 40.0
    MIN_HEIGHT: ClassVar[float] = 80.0

    @property
    def ports(self) -> List[Port]:
        """Возвращает все порты устройства."""
        return self.input_ports + self.output_ports

    def calculate_height(self) -> float:
        """Вычисляет высоту устройства по количеству портов."""
        max_ports = max(len(self.input_ports), len(self.output_ports))

        if max_ports == 0:
            return self.MIN_HEIGHT

        port_area = (max_ports + 1) * self.PORT_SPACING
        port_area = max(port_area, self.MIN_PORT_AREA_HEIGHT)

        total = self.HEADER_HEIGHT + port_area + self.FOOTER_HEIGHT
        return max(total, self.MIN_HEIGHT)

    def update_port_positions(self):
        """Пересчитывает высоту и позиции портов."""
        self.height = self.calculate_height()

        # Входные порты (слева)
        count_in = len(self.input_ports)
        if count_in > 0:
            top = self.y - self.height / 2 + self.HEADER_HEIGHT
            bottom = self.y + self.height / 2 - self.FOOTER_HEIGHT
            area_height = bottom - top

            for i, port in enumerate(self.input_ports):
                port.x = self.x - self.width / 2
                port.y = top + (i + 1) * (area_height / (count_in + 1))

        # Выходные порты (справа)
        count_out = len(self.output_ports)
        if count_out > 0:
            top = self.y - self.height / 2 + self.HEADER_HEIGHT
            bottom = self.y + self.height / 2 - self.FOOTER_HEIGHT
            area_height = bottom - top

            for i, port in enumerate(self.output_ports):
                port.x = self.x + self.width / 2
                port.y = top + (i + 1) * (area_height / (count_out + 1))

    def add_port(self, name: str, port_type: PortType,
                 connector: str = "Ethernet", speed: str = "1Gb"):
        """Добавляет порт с заданными параметрами."""
        max_id = max((p.id for p in self.ports), default=-1)
        port = Port(
            id=max_id + 1,
            name=name,
            port_type=port_type,
            connector=connector,
            speed=speed
        )
        if port_type == PortType.INPUT:
            self.input_ports.append(port)
        else:
            self.output_ports.append(port)
        return port


@dataclass
class Connection:
    """Соединение между двумя портами."""
    port1: Port
    port2: Port
    cable_type: str = "Ethernet"
    length: float = 1.0
    group_id: Optional[int] = None


@dataclass
class ConnectionGroup:
    """Группа соединений (логический канал)."""
    id: int
    name: str
    color: str
    visible: bool = True


# ============================================================
#  ФАБРИКИ УСТРОЙСТВ
# ============================================================

class DeviceFactory:
    """
    Фабрика устройств — шаблоны для быстрого создания.

    Каждый шаблон описывает типовую конфигурацию устройства:
      - имя модели
      - тип
      - категория
      - список портов с разъёмами и скоростями
    """

    TEMPLATES = {
        # ===== Коммутаторы =====
        "Агрегатор 100Gb": {
            "device_type": "Aggregator",
            "category": DeviceCategory.SWITCHES,
            "model": "AG-100G-32",
            "input_ports": [
                ("IN 1", "SFP MPO", "100Gb"),
                ("IN 2", "SFP MPO", "100Gb"),
                ("IN 3", "SFP MPO", "100Gb"),
                ("IN 4", "SFP MPO", "100Gb"),
            ],
            "output_ports": [
                ("OUT 1", "SFP MPO", "100Gb"),
                ("OUT 2", "SFP MPO", "100Gb"),
                ("OUT 3", "SFP MPO", "100Gb"),
                ("OUT 4", "SFP MPO", "100Gb"),
                ("OUT 5", "SFP MPO", "100Gb"),
                ("OUT 6", "SFP MPO", "100Gb"),
            ]
        },
        "Коммутатор 10Gb": {
            "device_type": "Switch",
            "category": DeviceCategory.SWITCHES,
            "model": "SW-10G-24",
            "input_ports": [
                ("IN 1", "SFP LC", "10Gb"),
                ("IN 2", "SFP LC", "10Gb"),
                ("IN 3", "SFP LC", "10Gb"),
                ("IN 4", "SFP LC", "10Gb"),
            ],
            "output_ports": [
                (f"OUT {i + 1}", "SFP LC", "10Gb") for i in range(8)
            ]
        },
        "Коммутатор 1Gb": {
            "device_type": "Switch",
            "category": DeviceCategory.SWITCHES,
            "model": "SW-1G-48",
            "input_ports": [
                ("IN 1", "SFP LC", "1Gb"),
                ("IN 2", "SFP LC", "1Gb"),
            ],
            "output_ports": [
                (f"eth{i}", "Ethernet", "1Gb") for i in range(12)
            ]
        },
        "Маршрутизатор": {
            "device_type": "Router",
            "category": DeviceCategory.SWITCHES,
            "model": "RT-10G-8",
            "input_ports": [
                ("WAN 1", "SFP LC", "10Gb"),
                ("WAN 2", "SFP LC", "10Gb"),
            ],
            "output_ports": [
                ("LAN 1", "SFP LC", "10Gb"),
                ("LAN 2", "SFP LC", "10Gb"),
                ("LAN 3", "Ethernet", "1Gb"),
                ("LAN 4", "Ethernet", "1Gb"),
            ]
        },

        # ===== Кроссы и патч-панели =====
        "Магистральный кросс": {
            "device_type": "Main Cross-connect",
            "category": DeviceCategory.GLOBAL_INPUT,
            "model": "MC-100G-16",
            "input_ports": [
                (f"IN {i + 1}", "SFP MPO", "100Gb") for i in range(8)
            ],
            "output_ports": [
                (f"OUT {i + 1}", "SFP MPO", "100Gb") for i in range(8)
            ]
        },
        "Оптический кросс": {
            "device_type": "Fiber Cross-connect",
            "category": DeviceCategory.GLOBAL_INPUT,
            "model": "FC-10G-24",
            "input_ports": [
                (f"IN {i + 1}", "FC", "10Gb") for i in range(12)
            ],
            "output_ports": [
                (f"OUT {i + 1}", "FC", "10Gb") for i in range(12)
            ]
        },
        "Патч-панель LC": {
            "device_type": "Patch Panel",
            "category": DeviceCategory.LOCAL_INPUT,
            "model": "PP-LC-24",
            "input_ports": [
                (f"IN {i + 1}", "SFP LC", "10Gb") for i in range(12)
            ],
            "output_ports": [
                (f"OUT {i + 1}", "SFP LC", "10Gb") for i in range(12)
            ]
        },
        "Патч-панель MPO": {
            "device_type": "MPO Panel",
            "category": DeviceCategory.LOCAL_INPUT,
            "model": "PP-MPO-16",
            "input_ports": [
                (f"IN {i + 1}", "MPO", "100Gb") for i in range(8)
            ],
            "output_ports": [
                (f"OUT {i + 1}", "MPO", "100Gb") for i in range(8)
            ]
        },

        # ===== Серверы =====
        "Сервер 100Gb": {
            "device_type": "Application Server",
            "category": DeviceCategory.SERVERS,
            "model": "SRV-100G",
            "input_ports": [
                ("Infiniband 1", "MPO", "100Gb"),
                ("Infiniband 2", "MPO", "100Gb"),
                ("mgmt", "Ethernet", "1Gb"),
            ],
            "output_ports": [
                ("OUT 1", "SFP MPO", "100Gb"),
            ]
        },
        "Сервер БД 10Gb": {
            "device_type": "Database Server",
            "category": DeviceCategory.SERVERS,
            "model": "SRV-DB-10G",
            "input_ports": [
                ("eth0", "SFP LC", "10Gb"),
                ("eth1", "SFP LC", "10Gb"),
                ("mgmt", "Ethernet", "1Gb"),
            ],
            "output_ports": []
        },
        "Хранилище": {
            "device_type": "Storage",
            "category": DeviceCategory.SERVERS,
            "model": "STOR-100G",
            "input_ports": [
                (f"IB {i + 1}", "MPO", "100Gb") for i in range(4)
            ],
            "output_ports": []
        },

        # ===== Кастомное устройство =====
        "Пустое устройство": {
            "device_type": "Custom Device",
            "category": DeviceCategory.SWITCHES,
            "model": "",
            "input_ports": [],
            "output_ports": []
        }
    }

    @classmethod
    def create_device(cls, template_name: str, device_id: int,
                      x: float = 100, y: float = 100) -> Optional[Device]:
        """
        Создаёт устройство по шаблону.

        Args:
            template_name: Название шаблона из TEMPLATES
            device_id: ID нового устройства
            x, y: Координаты центра

        Returns:
            Созданное устройство или None если шаблон не найден.
        """
        template = cls.TEMPLATES.get(template_name)
        if not template:
            return None

        device = Device(
            id=device_id,
            name=f"{template_name} {device_id}",
            x=x, y=y,
            device_type=template["device_type"],
            category=template["category"],
            model=template.get("model", "")
        )

        # Добавляем входные порты
        for port_name, connector, speed in template.get("input_ports", []):
            device.add_port(port_name, PortType.INPUT, connector, speed)

        # Добавляем выходные порты
        for port_name, connector, speed in template.get("output_ports", []):
            device.add_port(port_name, PortType.OUTPUT, connector, speed)

        device.update_port_positions()
        return device

    @classmethod
    def get_categories(cls) -> Dict[str, List[str]]:
        """Возвращает шаблоны сгруппированные по категории."""
        categories = defaultdict(list)
        for name, template in cls.TEMPLATES.items():
            cat = template["category"].value
            categories[cat].append(name)
        return dict(categories)

    @classmethod
    def get_connectors(cls) -> List[str]:
        """Возвращает список доступных типов разъёмов."""
        return [c.value for c in PortConnector]

    @classmethod
    def get_speeds(cls) -> List[str]:
        """Возвращает список доступных скоростей."""
        return [s.value for s in PortSpeed]

    @classmethod
    def get_cable_types(cls) -> List[str]:
        """Возвращает список доступных типов кабелей."""
        return [c.value for c in CableType]


# ============================================================
#  МОДЕЛЬ
# ============================================================

class NetworkModel(QObject):
    """Модель сети — хранит данные и уведомляет об изменениях."""

    data_changed = pyqtSignal()

    def __init__(self):
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

    def notify_observers(self):
        """Уведомляет всех наблюдателей об изменении."""
        self.data_changed.emit()

    # ===== Устройства =====

    def add_device_from_template(self, template_name: str,
                                 x: float = 100, y: float = 100) -> Optional[Device]:
        """Создаёт устройство из шаблона."""
        device = DeviceFactory.create_device(
            template_name, self.next_device_id, x, y
        )
        if device:
            self.next_device_id += 1
            self.devices.append(device)
            self.notify_observers()
        return device

    def add_device(self, device_type: str, category: DeviceCategory,
                   x: float = 100, y: float = 100) -> Device:
        """Создаёт пустое устройство без портов."""
        device = Device(
            id=self.next_device_id,
            name=f"{device_type} {self.next_device_id}",
            device_type=device_type,
            category=category,
            x=x, y=y
        )
        self.next_device_id += 1
        self.devices.append(device)
        self.notify_observers()
        return device

    def remove_device(self, device: Device):
        """Удаляет устройство и все связанные соединения."""
        self.connections = [
            c for c in self.connections
            if c.port1 not in device.ports and c.port2 not in device.ports
        ]
        self.devices.remove(device)
        self.notify_observers()

    # ===== Соединения =====

    def is_port_connected(self, port: Port) -> bool:
        """Проверяет, используется ли порт."""
        return any(
            port is c.port1 or port is c.port2
            for c in self.connections
        )

    def get_port_connection(self, port: Port) -> Optional[Connection]:
        """Возвращает соединение с участием порта."""
        for c in self.connections:
            if port is c.port1 or port is c.port2:
                return c
        return None

    def are_connectors_compatible(self, port1: Port, port2: Port) -> Tuple[bool, str]:
        """
        Проверяет совместимость разъёмов портов.

        Возвращает (совместимы, сообщение).
        """
        c1 = port1.connector
        c2 = port2.connector

        # Если хотя бы один из них Ethernet — совместимы
        if c1 == "Ethernet" and c2 == "Ethernet":
            return True, ""
        if c1 == "RJ45" and c2 == "RJ45":
            return True, ""

        # Оптические
        optical_connectors = {"SFP LC", "SFP MPO", "FC", "MPO"}
        if c1 in optical_connectors and c2 in optical_connectors:
            # Проверяем совместимость LC ↔ SFP LC, MPO ↔ SFP MPO
            lc_group = {"SFP LC", "FC"}
            mpo_group = {"SFP MPO", "MPO"}

            if (c1 in lc_group and c2 in lc_group) or \
                    (c1 in mpo_group and c2 in mpo_group):
                return True, ""
            else:
                return False, (
                    f"Разъёмы несовместимы: {c1} ↔ {c2}\n"
                    f"LC-совместимые: SFP LC, FC\n"
                    f"MPO-совместимые: SFP MPO, MPO"
                )

        return False, f"Разъёмы несовместимы: {c1} ↔ {c2}"

    def can_connect(self, port1: Port, port2: Port) -> Tuple[bool, str]:
        """Проверяет возможность соединения между портами."""
        if port1.port_type == port2.port_type:
            return False, "Соединение возможно только между выходом и входом!"

        out_port = port1 if port1.port_type == PortType.OUTPUT else port2
        in_port = port2 if port1.port_type == PortType.OUTPUT else port1

        # Проверка занятости
        if self.is_port_connected(out_port):
            dev = self.find_device_by_port(out_port)
            name = dev.name if dev else "?"
            return False, (
                f"Выходной порт «{out_port.name}» устройства «{name}» "
                f"уже занят!"
            )

        if self.is_port_connected(in_port):
            dev = self.find_device_by_port(in_port)
            name = dev.name if dev else "?"
            return False, (
                f"Входной порт «{in_port.name}» устройства «{name}» "
                f"уже занят!"
            )

        # Проверка одного устройства
        dev1 = self.find_device_by_port(out_port)
        dev2 = self.find_device_by_port(in_port)
        if dev1 and dev2 and dev1.id == dev2.id:
            return False, "Нельзя соединить порты одного устройства!"

        # Проверка совместимости разъёмов
        return self.are_connectors_compatible(out_port, in_port)

    def add_connection(self, port1: Port, port2: Port,
                       cable_type: str = "Ethernet",
                       length: float = 1.0,
                       group_id: Optional[int] = None) -> Optional[Connection]:
        """Создаёт соединение с проверками."""
        can, error = self.can_connect(port1, port2)
        if not can:
            return None

        for conn in self.connections:
            if (conn.port1 is port1 and conn.port2 is port2) or \
                    (conn.port1 is port2 and conn.port2 is port1):
                return None

        if port1.port_type == PortType.OUTPUT:
            conn = Connection(port1, port2, cable_type, length, group_id)
        else:
            conn = Connection(port2, port1, cable_type, length, group_id)

        self.connections.append(conn)
        self.notify_observers()
        return conn

    def remove_connections_for_port(self, port: Port):
        """Удаляет соединения порта."""
        self.connections = [
            c for c in self.connections if c.port1 != port and c.port2 != port
        ]
        self.notify_observers()

    # ===== Группы =====

    def create_group(self, name: str, color: Optional[str] = None) -> ConnectionGroup:
        """Создаёт группу с указанным или автовыбранным цветом."""
        if color is None:
            colors = [
                "#ef4444", "#f97316", "#f59e0b", "#eab308",
                "#84cc16", "#22c55e", "#10b981", "#14b8a6",
                "#06b6d4", "#0ea5e9", "#3b82f6", "#6366f1",
                "#8b5cf6", "#a855f7", "#d946ef", "#ec4899",
            ]
            color = colors[self.next_group_id % len(colors)]

        group = ConnectionGroup(self.next_group_id, name, color)
        self.next_group_id += 1
        self.groups.append(group)
        self.notify_observers()
        return group

    def remove_group(self, group: ConnectionGroup):
        """Удаляет группу, отвязывая соединения."""
        for conn in self.connections:
            if conn.group_id == group.id:
                conn.group_id = None
        if group in self.groups:
            self.groups.remove(group)
        self.notify_observers()

    def update_group_color(self, group: ConnectionGroup, color: str):
        """Меняет цвет группы."""
        group.color = color
        self.notify_observers()

    def get_group(self, group_id: int) -> Optional[ConnectionGroup]:
        """Возвращает группу по ID."""
        for g in self.groups:
            if g.id == group_id:
                return g
        return None

    def get_group_connections(self, group: ConnectionGroup) -> List[Connection]:
        """Возвращает соединения группы."""
        return [c for c in self.connections if c.group_id == group.id]

    # ===== Поиск =====

    def find_device_by_port(self, port: Port) -> Optional[Device]:
        """Находит устройство по порту."""
        for d in self.devices:
            if port in d.ports:
                return d
        return None

    def get_visible_connections(self) -> List[Connection]:
        """Возвращает соединения с учётом фильтра."""
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

    def set_filter(self, text: str):
        """Устанавливает фильтр групп."""
        self.filter_text = text.strip().lower()
        self.notify_observers()

    def move_device(self, device: Device, x: float, y: float):
        """Перемещает устройство."""
        device.x = x
        device.y = y
        device.update_port_positions()
        self.notify_observers()

    # ===== Сериализация =====

    def to_dict(self) -> dict:
        """Сериализует модель."""
        data = {
            'devices': [],
            'connections': [],
            'groups': [],
            'settings': {
                'show_port_labels': self.show_port_labels,
                'show_connection_labels': self.show_connection_labels,
                'show_grid': self.show_grid
            }
        }

        for device in self.devices:
            data['devices'].append({
                'id': device.id,
                'name': device.name,
                'x': device.x, 'y': device.y,
                'width': device.width, 'height': device.height,
                'device_type': device.device_type,
                'category': device.category.value,
                'model': device.model,
                'input_ports': [
                    {
                        'id': p.id, 'name': p.name,
                        'connector': p.connector, 'speed': p.speed
                    } for p in device.input_ports
                ],
                'output_ports': [
                    {
                        'id': p.id, 'name': p.name,
                        'connector': p.connector, 'speed': p.speed
                    } for p in device.output_ports
                ]
            })

        for conn in self.connections:
            dev1 = self.find_device_by_port(conn.port1)
            dev2 = self.find_device_by_port(conn.port2)
            if dev1 and dev2:
                data['connections'].append({
                    'device1_id': dev1.id, 'port1_id': conn.port1.id,
                    'device2_id': dev2.id, 'port2_id': conn.port2.id,
                    'cable_type': conn.cable_type,
                    'length': conn.length,
                    'group_id': conn.group_id
                })

        for group in self.groups:
            data['groups'].append({
                'id': group.id, 'name': group.name,
                'color': group.color, 'visible': group.visible
            })

        return data

    def from_dict(self, data: dict):
        """Загружает модель из словаря."""
        self.devices.clear()
        self.connections.clear()
        self.groups.clear()

        if 'settings' in data:
            s = data['settings']
            self.show_port_labels = s.get('show_port_labels', True)
            self.show_connection_labels = s.get('show_connection_labels', True)
            self.show_grid = s.get('show_grid', True)

        device_map = {}
        for dev_data in data['devices']:
            device = Device(
                id=dev_data['id'],
                name=dev_data['name'],
                x=dev_data['x'], y=dev_data['y'],
                width=dev_data.get('width', 180),
                height=dev_data.get('height', 100),
                device_type=dev_data['device_type'],
                category=DeviceCategory(dev_data['category']),
                model=dev_data.get('model', '')
            )

            for p in dev_data.get('input_ports', []):
                device.input_ports.append(Port(
                    id=p['id'], name=p['name'],
                    port_type=PortType.INPUT,
                    connector=p.get('connector', 'Ethernet'),
                    speed=p.get('speed', '1Gb')
                ))

            for p in dev_data.get('output_ports', []):
                device.output_ports.append(Port(
                    id=p['id'], name=p['name'],
                    port_type=PortType.OUTPUT,
                    connector=p.get('connector', 'Ethernet'),
                    speed=p.get('speed', '1Gb')
                ))

            device.update_port_positions()
            self.devices.append(device)
            device_map[device.id] = device
            self.next_device_id = max(self.next_device_id, device.id + 1)

        for group_data in data.get('groups', []):
            group = ConnectionGroup(
                group_data['id'], group_data['name'],
                group_data['color'], group_data.get('visible', True)
            )
            self.groups.append(group)
            self.next_group_id = max(self.next_group_id, group.id + 1)

        for conn_data in data['connections']:
            dev1 = device_map.get(conn_data['device1_id'])
            dev2 = device_map.get(conn_data['device2_id'])
            if dev1 and dev2:
                port1 = next(
                    (p for p in dev1.ports if p.id == conn_data['port1_id']),
                    None
                )
                port2 = next(
                    (p for p in dev2.ports if p.id == conn_data['port2_id']),
                    None
                )
                if port1 and port2:
                    conn = Connection(
                        port1, port2,
                        conn_data.get('cable_type', 'Ethernet'),
                        conn_data.get('length', 1.0),
                        conn_data.get('group_id')
                    )
                    self.connections.append(conn)

        self.notify_observers()


# ============================================================
#  ВИДЖЕТ ВЫБОРА ЦВЕТА
# ============================================================

class ColorPickerWidget(QWidget):
    """Виджет выбора цвета из палитры."""

    color_changed = pyqtSignal(str)

    DEFAULT_COLORS = [
        "#ef4444", "#f97316", "#f59e0b", "#eab308",
        "#84cc16", "#22c55e", "#10b981", "#14b8a6",
        "#06b6d4", "#0ea5e9", "#3b82f6", "#6366f1",
        "#8b5cf6", "#a855f7", "#d946ef", "#ec4899",
    ]

    def __init__(self, initial: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.selected_color = initial or self.DEFAULT_COLORS[0]
        self._buttons = []
        self._initialized = False

        self._setup_ui()
        self._initialized = True

    def _setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        cols = 8
        for i, color in enumerate(self.DEFAULT_COLORS):
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(color)
            btn.setProperty("hex_color", color)
            btn.clicked.connect(partial(self._on_click, color))

            row = i // cols
            col = i % cols
            layout.addWidget(btn, row, col)
            self._buttons.append(btn)

        self._refresh_styles()

    def _on_click(self, color: str):
        if not self._initialized:
            return
        if color == self.selected_color:
            return
        self.selected_color = color
        self._refresh_styles()
        self.color_changed.emit(color)

    def _refresh_styles(self):
        for btn in self._buttons:
            color = btn.property("hex_color")
            is_sel = color == self.selected_color
            border = "#1f2937" if is_sel else "transparent"
            width = 3 if is_sel else 0
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: {width}px solid {border};
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    border: 2px solid #6b7280;
                }}
            """)

    def get_color(self) -> str:
        return self.selected_color

    def set_color(self, color: str):
        self.selected_color = color
        self._refresh_styles()


# ============================================================
#  КАНВАС
# ============================================================

class NetworkCanvas(QWidget):
    """Канвас для отображения и редактирования сети."""

    device_selected = pyqtSignal(object)
    connection_requested = pyqtSignal(object, object)
    device_edited = pyqtSignal(object)
    device_deleted = pyqtSignal(object)
    channel_requested = pyqtSignal()
    groups_requested = pyqtSignal()

    def __init__(self, model: NetworkModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.model.data_changed.connect(self.update)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(600, 400)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAutoFillBackground(True)

        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        self.selected_device: Optional[Device] = None
        self.selected_port: Optional[Port] = None
        self.connection_mode = False
        self.dragging_device: Optional[Device] = None
        self.drag_offset = QPointF()

        self.panning = False
        self.pan_start = QPointF()
        self.pan_offset_start = QPointF()

    # ===== Координаты =====

    def to_canvas(self, x, y):
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    def to_scene(self, cx, cy):
        return (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale

    # ===== Отрисовка =====

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(self.rect(), QColor("#fafbfc"))

        painter.save()
        painter.translate(self.offset_x, self.offset_y)
        painter.scale(self.scale, self.scale)

        if self.model.show_grid:
            self._draw_grid(painter)

        self._draw_connections(painter)

        for device in self.model.devices:
            self._draw_device(painter, device)

        if self.connection_mode and self.selected_port:
            self._draw_temp_connection(painter)

        painter.restore()

        if self.model.filter_text:
            self._draw_filter_indicator(painter)

    def _draw_temp_connection(self, painter: QPainter):
        """Временная линия соединения от порта к курсору."""
        if not self.selected_port:
            return

        cursor_pos = self.mapFromGlobal(self.cursor().pos())
        sx, sy = self.to_scene(cursor_pos.x(), cursor_pos.y())

        pen = QPen(QColor("#f59e0b"), 2)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(
            QPointF(self.selected_port.x, self.selected_port.y),
            QPointF(sx, sy)
        )

    def _draw_grid(self, painter: QPainter):
        """Фоновая сетка."""
        pen = QPen(QColor("#e8ecf1"), 1)
        pen.setCosmetic(True)
        painter.setPen(pen)

        left, top = self.to_scene(0, 0)
        right, bottom = self.to_scene(self.width(), self.height())

        grid = 50
        x = int(left // grid) * grid
        while x < right:
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))
            x += grid

        y = int(top // grid) * grid
        while y < bottom:
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            y += grid

    def _draw_connections(self, painter: QPainter):
        """Рисует все видимые соединения."""
        visible = self.model.get_visible_connections()

        grouped = defaultdict(list)
        for conn in visible:
            if conn.group_id is not None:
                group = self.model.get_group(conn.group_id)
                if group and group.visible:
                    grouped[conn.group_id].append(conn)

        # Фон групп
        for group_id, conns in grouped.items():
            if len(conns) > 1:
                group = self.model.get_group(group_id)
                if group:
                    self._draw_group_background(painter, conns, group)

        # Отдельные соединения
        for conn in visible:
            group = (self.model.get_group(conn.group_id)
                     if conn.group_id is not None else None)
            if group and not group.visible:
                continue

            color = group.color if group else CABLE_COLORS.get(
                conn.cable_type, "#9ca3af"
            )
            self._draw_single_connection(
                painter, conn, color, group.name if group else None
            )

    def _draw_group_background(self, painter: QPainter,
                               connections, group):
        """Фон группы — полупрозрачная широкая линия."""
        color = QColor(group.color)
        color.setAlpha(100)

        pen = QPen(color, 6)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        for conn in connections:
            path = self._make_bezier_path(conn.port1, conn.port2)
            painter.drawPath(path)

    def _make_bezier_path(self, port1, port2) -> QPainterPath:
        """Кривая Безье между портами."""
        x1, y1 = port1.x, port1.y
        x2, y2 = port2.x, port2.y

        dx = abs(x2 - x1) * 0.4
        ctrl1 = QPointF(x1 + dx, y1)
        ctrl2 = QPointF(x2 - dx, y2)

        path = QPainterPath()
        path.moveTo(x1, y1)
        path.cubicTo(ctrl1, ctrl2, QPointF(x2, y2))
        return path

    def _draw_single_connection(self, painter, conn, color, group_name):
        """Одно соединение — кривая, стрелка, подпись."""
        # Толщина зависит от скорости порта
        width = 2
        if conn.port1.speed == "100Gb" or conn.port2.speed == "100Gb":
            width = 3
        elif conn.port1.speed == "10Gb" or conn.port2.speed == "10Gb":
            width = 2.5

        pen = QPen(QColor(color), width)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setStyle(CABLE_STYLES.get(conn.cable_type, Qt.PenStyle.SolidLine))

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        path = self._make_bezier_path(conn.port1, conn.port2)
        painter.drawPath(path)

        self._draw_arrow(painter, conn.port1, conn.port2, color)

        if self.model.show_connection_labels:
            self._draw_connection_label(painter, conn, group_name)

    def _draw_arrow(self, painter, port1, port2, color):
        """Стрелка направления на кривой."""
        x1, y1 = port1.x, port1.y
        x2, y2 = port2.x, port2.y

        t = 0.7
        dx = abs(x2 - x1) * 0.4
        cx1, cy1 = x1 + dx, y1
        cx2, cy2 = x2 - dx, y2

        ax = ((1 - t) ** 3 * x1 + 3 * (1 - t) ** 2 * t * cx1 +
              3 * (1 - t) * t ** 2 * cx2 + t ** 3 * x2)
        ay = ((1 - t) ** 3 * y1 + 3 * (1 - t) ** 2 * t * cy1 +
              3 * (1 - t) * t ** 2 * cy2 + t ** 3 * y2)

        angle = math.atan2(y2 - y1, x2 - x1)
        size = 7.0

        p1 = QPointF(ax + size * math.cos(angle), ay + size * math.sin(angle))
        p2 = QPointF(ax + size * math.cos(angle + 2.5), ay + size * math.sin(angle + 2.5))
        p3 = QPointF(ax + size * math.cos(angle - 2.5), ay + size * math.sin(angle - 2.5))

        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([p1, p2, p3]))

    def _draw_connection_label(self, painter, conn, group_name):
        """Подпись соединения."""
        mid_x = (conn.port1.x + conn.port2.x) / 2
        mid_y = (conn.port1.y + conn.port2.y) / 2

        items = []
        if group_name:
            items.append(group_name)
        items.append(f"{conn.cable_type} | {conn.length:.1f}м")

        font = QFont("Arial")
        font.setPointSizeF(7)
        painter.setFont(font)

        lh = 12.0
        th = len(items) * lh
        lw = 140.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.drawRoundedRect(
            QRectF(mid_x - lw / 2, mid_y - th / 2, lw, th), 3, 3
        )

        painter.setPen(QColor("#1f2937"))
        for i, item in enumerate(items):
            y = mid_y - th / 2 + (i + 1) * lh
            painter.drawText(
                QRectF(mid_x - lw / 2, y - lh, lw, lh),
                Qt.AlignmentFlag.AlignCenter, item
            )

    def _draw_device(self, painter, device: Device):
        """Рисует устройство."""
        colors = {
            DeviceCategory.GLOBAL_INPUT: ("#4682b4", "#00008b"),
            DeviceCategory.LOCAL_INPUT: ("#87ceeb", "#006496"),
            DeviceCategory.SWITCHES: ("#3cb371", "#006400"),
            DeviceCategory.SERVERS: ("#9370db", "#4b0082")
        }
        fill_color, border_color = colors.get(
            device.category, ("#808080", "#404040")
        )

        if device == self.selected_device:
            border_color = "#f59e0b"

        w, h = device.width, device.height
        header_h = device.HEADER_HEIGHT
        footer_h = device.FOOTER_HEIGHT

        rect = QRectF(device.x - w / 2, device.y - h / 2, w, h)

        # Тело устройства
        border_pen = QPen(QColor(border_color), 2)
        border_pen.setCosmetic(True)
        painter.setPen(border_pen)
        painter.setBrush(QBrush(QColor(fill_color)))
        painter.drawRoundedRect(rect, 5, 5)

        # Заголовок
        header_rect = QRectF(device.x - w / 2, device.y - h / 2, w, header_h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
        painter.drawRect(header_rect)

        painter.setPen(QColor("white"))
        font = QFont("Arial")
        font.setPointSizeF(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            header_rect, Qt.AlignmentFlag.AlignCenter, device.name
        )

        # Подпись типа и модели
        footer_rect = QRectF(
            device.x - w / 2, device.y + h / 2 - footer_h, w, footer_h
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 60)))
        painter.drawRect(footer_rect)

        painter.setPen(QColor(255, 255, 255, 230))
        font.setPointSizeF(6.5)
        font.setBold(False)
        painter.setFont(font)

        type_text = device.device_type
        if device.model:
            type_text += f" • {device.model}"

        painter.drawText(
            footer_rect, Qt.AlignmentFlag.AlignCenter, type_text
        )

        # Порты
        for port in device.input_ports:
            self._draw_port(painter, port, is_input=True)
        for port in device.output_ports:
            self._draw_port(painter, port, is_input=False)

    def _draw_port(self, painter, port: Port, is_input: bool):
        """Рисует порт с цветом по типу разъёма."""
        size = 5.0
        is_connected = self.model.is_port_connected(port)

        # ✅ Цвет по типу разъёма
        connector_color = CONNECTOR_COLORS.get(port.connector, "#9ca3af")

        # ✅ Приглушение если занят
        if is_connected:
            base_color = QColor(connector_color)
            base_color = base_color.darker(120)
            outline_color = "#047857"
        else:
            base_color = QColor(connector_color)
            outline_color = "#4b5563"

        # Красный контур если выбран
        if port == self.selected_port:
            pen = QPen(QColor("#dc2626"), 2)
        else:
            pen = QPen(QColor(outline_color), 1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(base_color))

        # Форма порта
        if is_input:
            triangle = QPolygonF([
                QPointF(port.x - size, port.y - size),
                QPointF(port.x - size, port.y + size),
                QPointF(port.x + size, port.y)
            ])
            painter.drawPolygon(triangle)
        else:
            painter.drawRect(QRectF(
                port.x - size, port.y - size, size * 2, size * 2
            ))

        # Подпись порта
        if self.model.show_port_labels:
            painter.setPen(QColor("#1f2937"))
            font = QFont("Arial")
            font.setPointSizeF(5.5)
            painter.setFont(font)
            painter.drawText(
                QRectF(port.x - 30, port.y - 22, 60, 12),
                Qt.AlignmentFlag.AlignCenter,
                port.label()
            )

    def _draw_filter_indicator(self, painter: QPainter):
        """Индикатор фильтра."""
        painter.save()
        painter.resetTransform()

        visible = [
            g.name for g in self.model.groups
            if self.model.filter_text in g.name.lower()
        ]
        text = f"🔍 Фильтр: '{self.model.filter_text}'"
        if visible:
            text += f" | {', '.join(visible)}"

        rect = QRectF(10, 10, 400, 30)
        painter.setPen(QPen(QColor("#cccccc"), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawRoundedRect(rect, 5, 5)

        painter.setPen(QColor("#0066c8"))
        font = QFont("Arial", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(10, 0, -10, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text
        )
        painter.restore()

    # ===== Поиск =====

    def _find_port_at(self, cx, cy) -> Optional[Port]:
        """Находит порт по координатам."""
        sx, sy = self.to_scene(cx, cy)
        for device in self.model.devices:
            for port in device.ports:
                dx = sx - port.x
                dy = sy - port.y
                if dx * dx + dy * dy < 100:
                    return port
        return None

    def _find_device_at(self, cx, cy) -> Optional[Device]:
        """Находит устройство по координатам."""
        sx, sy = self.to_scene(cx, cy)
        for device in reversed(self.model.devices):
            if (abs(sx - device.x) < device.width / 2 and
                    abs(sy - device.y) < device.height / 2):
                return device
        return None

    # ===== События мыши =====

    def mousePressEvent(self, event):
        self.setFocus()

        pos = event.position()
        sx, sy = self.to_scene(pos.x(), pos.y())

        # Панорамирование
        if (event.button() == Qt.MouseButton.MiddleButton or
                (event.button() == Qt.MouseButton.LeftButton and
                 event.modifiers() == Qt.KeyboardModifier.ControlModifier)):
            self.panning = True
            self.pan_start = pos
            self.pan_offset_start = QPointF(self.offset_x, self.offset_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        # ПКМ
        if event.button() == Qt.MouseButton.RightButton:
            port = self._find_port_at(pos.x(), pos.y())
            if port:
                if self.model.is_port_connected(port):
                    dev = self.model.find_device_by_port(port)
                    name = dev.name if dev else "?"
                    QMessageBox.warning(
                        self, "Порт занят",
                        f"Порт «{port.name}» устройства «{name}» уже используется."
                    )
                    return

                if port.port_type != PortType.OUTPUT:
                    QMessageBox.information(
                        self, "Неверный порт",
                        f"Порт «{port.name}» — входной.\n"
                        f"Начните соединение с ВЫХОДНОГО порта (■)."
                    )
                    return

                self.connection_mode = True
                self.selected_port = port
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.update()
            else:
                self._show_context_menu(event)
            return

        # ЛКМ
        if event.button() == Qt.MouseButton.LeftButton:
            if self.connection_mode:
                port = self._find_port_at(pos.x(), pos.y())
                if port:
                    self._finish_connection(port)
                else:
                    self._cancel_connection()
                return

            port = self._find_port_at(pos.x(), pos.y())
            if port:
                self.selected_port = port
                self.selected_device = self.model.find_device_by_port(port)
                self.update()
                return

            device = self._find_device_at(pos.x(), pos.y())
            if device:
                self.selected_device = device
                self.selected_port = None
                self.dragging_device = device
                self.drag_offset = QPointF(sx - device.x, sy - device.y)
                self.device_selected.emit(device)
                self.update()
                return

            self.selected_device = None
            self.selected_port = None
            self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()

        if self.panning:
            delta = pos - self.pan_start
            self.offset_x = self.pan_offset_start.x() + delta.x()
            self.offset_y = self.pan_offset_start.y() + delta.y()
            self.update()
            return

        if self.dragging_device:
            sx, sy = self.to_scene(pos.x(), pos.y())
            self.model.move_device(
                self.dragging_device,
                sx - self.drag_offset.x(),
                sy - self.drag_offset.y()
            )
            return

        if self.connection_mode:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.panning:
                self.panning = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
            self.dragging_device = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            device = self._find_device_at(pos.x(), pos.y())
            if device:
                self.device_edited.emit(device)

    def wheelEvent(self, event):
        pos = event.position()
        sx, sy = self.to_scene(pos.x(), pos.y())

        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        new_scale = self.scale * factor

        if 0.1 <= new_scale <= 5.0:
            self.scale = new_scale
            self.offset_x = pos.x() - sx * self.scale
            self.offset_y = pos.y() - sy * self.scale
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete and self.selected_device:
            self.device_deleted.emit(self.selected_device)
        elif event.key() == Qt.Key.Key_Escape:
            self._cancel_connection()

    # ===== Соединения =====

    def _finish_connection(self, target_port: Port):
        if not self.selected_port or self.selected_port == target_port:
            self._cancel_connection()
            return

        can, error = self.model.can_connect(self.selected_port, target_port)
        if not can:
            QMessageBox.warning(self, "Невозможно создать соединение", error)
            self._cancel_connection()
            return

        self.connection_requested.emit(self.selected_port, target_port)
        self._cancel_connection()

    def _cancel_connection(self):
        self.connection_mode = False
        self.selected_port = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    # ===== Контекстное меню =====

    def _show_context_menu(self, event):
        pos = event.position()
        sx, sy = self.to_scene(pos.x(), pos.y())

        menu = QMenu(self)

        # Подменю создания устройств (из фабрики)
        create_menu = menu.addMenu("➕ Создать устройство")
        categories = DeviceFactory.get_categories()

        for cat_name, templates in categories.items():
            cat_menu = create_menu.addMenu(cat_name)
            for template_name in templates:
                action = cat_menu.addAction(template_name)
                action.triggered.connect(
                    partial(self._create_device_at, template_name, sx, sy)
                )

        menu.addSeparator()

        channel_action = menu.addAction("🔗 Создать канал")
        channel_action.triggered.connect(self.channel_requested.emit)

        groups_action = menu.addAction("📊 Управление группами")
        groups_action.triggered.connect(self.groups_requested.emit)

        menu.addSeparator()

        delete_action = menu.addAction("🗑️ Удалить выбранное")
        delete_action.triggered.connect(self._delete_selected)

        menu.exec(event.globalPosition().toPoint())

    def _create_device_at(self, template_name: str, x: float, y: float):
        """Создаёт устройство из шаблона в указанной точке."""
        device = self.model.add_device_from_template(template_name, x, y)
        if device:
            self.selected_device = device
            self.update()

    def _delete_selected(self):
        if self.selected_device:
            reply = QMessageBox.question(
                self, "Удаление",
                f"Удалить устройство '{self.selected_device.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.device_deleted.emit(self.selected_device)
                self.selected_device = None
                self.update()
        elif self.selected_port:
            self.model.remove_connections_for_port(self.selected_port)
            self.selected_port = None
            self.update()


# ============================================================
#  ДИАЛОГ РЕДАКТИРОВАНИЯ УСТРОЙСТВА
# ============================================================

class DeviceEditDialog(QDialog):
    """Диалог редактирования устройства."""

    def __init__(self, model: NetworkModel, device: Device, parent=None):
        super().__init__(parent)
        self.model = model
        self.device = device
        self._updating = False

        self.setWindowTitle(f"Редактирование: {device.name}")
        self.resize(700, 600)

        self.input_edits = []
        self.output_edits = []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ===== Основные параметры =====
        info_group = QGroupBox("Основные параметры")
        form = QFormLayout(info_group)

        self.name_edit = QLineEdit(self.device.name)
        form.addRow("Название:", self.name_edit)

        self.type_edit = QLineEdit(self.device.device_type)
        form.addRow("Тип:", self.type_edit)

        self.model_edit = QLineEdit(self.device.model)
        self.model_edit.setPlaceholderText("Например: SW-10G-24")
        form.addRow("Модель:", self.model_edit)

        self.category_combo = QComboBox()
        for cat in DeviceCategory:
            self.category_combo.addItem(cat.value)
        self.category_combo.setCurrentText(self.device.category.value)
        form.addRow("Категория:", self.category_combo)

        layout.addWidget(info_group)

        # ===== Порты =====
        ports_group = QGroupBox("Порты устройства")
        ports_layout = QHBoxLayout(ports_group)

        # Входные
        in_frame = QWidget()
        in_layout = QVBoxLayout(in_frame)
        in_layout.setContentsMargins(0, 0, 0, 0)

        self.in_header = QLabel(f"▼ Входные порты ({len(self.device.input_ports)})")
        self.in_header.setStyleSheet("font-weight: bold; color: #047857;")
        in_layout.addWidget(self.in_header)

        in_scroll = QScrollArea()
        in_scroll.setWidgetResizable(True)
        in_scroll.setMinimumHeight(250)

        in_container = QWidget()
        self.in_container_layout = QVBoxLayout(in_container)
        self.in_container_layout.setSpacing(4)
        self.in_container_layout.setContentsMargins(4, 4, 4, 4)
        self.in_container_layout.addStretch()

        for port in self.device.input_ports:
            self._add_port_row(self.in_container_layout, port,
                               self.input_edits, True)

        in_scroll.setWidget(in_container)
        in_layout.addWidget(in_scroll)

        add_in_btn = QPushButton("➕ Добавить входной порт")
        add_in_btn.clicked.connect(
            lambda: self._add_new_port(self.in_container_layout, True)
        )
        in_layout.addWidget(add_in_btn)

        # Выходные
        out_frame = QWidget()
        out_layout = QVBoxLayout(out_frame)
        out_layout.setContentsMargins(0, 0, 0, 0)

        self.out_header = QLabel(f"■ Выходные порты ({len(self.device.output_ports)})")
        self.out_header.setStyleSheet("font-weight: bold; color: #b45309;")
        out_layout.addWidget(self.out_header)

        out_scroll = QScrollArea()
        out_scroll.setWidgetResizable(True)
        out_scroll.setMinimumHeight(250)

        out_container = QWidget()
        self.out_container_layout = QVBoxLayout(out_container)
        self.out_container_layout.setSpacing(4)
        self.out_container_layout.setContentsMargins(4, 4, 4, 4)
        self.out_container_layout.addStretch()

        for port in self.device.output_ports:
            self._add_port_row(self.out_container_layout, port,
                               self.output_edits, False)

        out_scroll.setWidget(out_container)
        out_layout.addWidget(out_scroll)

        add_out_btn = QPushButton("➕ Добавить выходной порт")
        add_out_btn.clicked.connect(
            lambda: self._add_new_port(self.out_container_layout, False)
        )
        out_layout.addWidget(add_out_btn)

        ports_layout.addWidget(in_frame)
        ports_layout.addWidget(out_frame)

        layout.addWidget(ports_group, 1)

        # ===== Кнопки =====
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_port_row(self, layout, port: Port, edit_list: list, is_input: bool):
        """Строка редактирования порта с полями разъёма и скорости."""
        widget = QWidget()
        widget._port = port
        widget._marked_for_deletion = False

        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        # Имя порта
        name_edit = QLineEdit(port.name)
        name_edit.setMaximumWidth(90)
        row.addWidget(name_edit)
        widget._name_edit = name_edit

        # Тип разъёма
        connector_combo = QComboBox()
        connector_combo.addItems(DeviceFactory.get_connectors())
        connector_combo.setCurrentText(port.connector)
        connector_combo.setMaximumWidth(100)
        connector_combo.currentTextChanged.connect(
            partial(self._on_port_changed, widget)
        )
        row.addWidget(connector_combo)
        widget._connector_combo = connector_combo

        # Скорость
        speed_combo = QComboBox()
        speed_combo.addItems(DeviceFactory.get_speeds())
        speed_combo.setCurrentText(port.speed)
        speed_combo.setMaximumWidth(70)
        speed_combo.currentTextChanged.connect(
            partial(self._on_port_changed, widget)
        )
        row.addWidget(speed_combo)
        widget._speed_combo = speed_combo

        row.addStretch()

        # Кнопка удаления
        del_btn = QPushButton("×")
        del_btn.setMaximumWidth(28)
        del_btn.setProperty("class", "danger")
        del_btn.clicked.connect(
            partial(self._remove_port, widget, port, edit_list)
        )
        row.addWidget(del_btn)

        layout.insertWidget(layout.count() - 1, widget)
        edit_list.append(widget)

    def _on_port_changed(self, widget, _text):
        """Обновляет параметры порта при изменении."""
        if hasattr(widget, '_port'):
            widget._port.name = widget._name_edit.text()
            widget._port.connector = widget._connector_combo.currentText()
            widget._port.speed = widget._speed_combo.currentText()

    def _add_new_port(self, layout, is_input: bool):
        """Добавляет новый порт."""
        if self._updating:
            return
        self._updating = True

        try:
            max_id = max((p.id for p in self.device.ports), default=-1)
            port = Port(
                id=max_id + 1,
                name=f"{'IN' if is_input else 'OUT'} {max_id + 1}",
                port_type=PortType.INPUT if is_input else PortType.OUTPUT,
                connector="Ethernet",
                speed="1Gb"
            )

            if is_input:
                self.device.input_ports.append(port)
                self._add_port_row(layout, port, self.input_edits, True)
            else:
                self.device.output_ports.append(port)
                self._add_port_row(layout, port, self.output_edits, False)

            self.in_header.setText(
                f"▼ Входные порты ({len(self.device.input_ports)})"
            )
            self.out_header.setText(
                f"■ Выходные порты ({len(self.device.output_ports)})"
            )
        finally:
            self._updating = False

    def _remove_port(self, widget, port: Port, edit_list: list):
        """Удаляет порт."""
        if self._updating:
            return
        self._updating = True

        try:
            has_conn = self.model.is_port_connected(port)
            if has_conn:
                reply = QMessageBox.question(
                    self, "Удаление порта",
                    f"Порт '{port.name}' имеет соединения. Удалить?",
                    QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                self.model.remove_connections_for_port(port)

            if port in self.device.input_ports:
                self.device.input_ports.remove(port)
            elif port in self.device.output_ports:
                self.device.output_ports.remove(port)

            edit_list.remove(widget)
            widget.setParent(None)
            widget.deleteLater()

            self.in_header.setText(
                f"▼ Входные порты ({len(self.device.input_ports)})"
            )
            self.out_header.setText(
                f"■ Выходные порты ({len(self.device.output_ports)})"
            )
        finally:
            self._updating = False

    def _save(self):
        """Сохраняет изменения."""
        if self._updating:
            return
        self._updating = True

        try:
            self.device.name = self.name_edit.text()
            self.device.device_type = self.type_edit.text()
            self.device.model = self.model_edit.text()
            self.device.category = DeviceCategory(self.category_combo.currentText())

            # Обновляем параметры портов
            for widget in self.input_edits + self.output_edits:
                if hasattr(widget, '_port'):
                    widget._port.name = widget._name_edit.text()
                    widget._port.connector = widget._connector_combo.currentText()
                    widget._port.speed = widget._speed_combo.currentText()

            self.device.update_port_positions()
            self.model.notify_observers()
            self.accept()
        finally:
            self._updating = False


# ============================================================
#  ДИАЛОГ СОЗДАНИЯ СОЕДИНЕНИЯ
# ============================================================

class ConnectionDialog(QDialog):
    """Диалог создания одиночного соединения."""

    def __init__(self, model: NetworkModel, port1: Port, port2: Port, parent=None):
        super().__init__(parent)

        can, error = model.can_connect(port1, port2)
        if not can:
            QMessageBox.warning(parent, "Невозможно создать соединение", error)
            self.reject()
            return

        self.model = model
        self.port1 = port1
        self.port2 = port2

        self.setWindowTitle("Создание соединения")
        self.resize(450, 500)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # Информация о портах
        dev1 = self.model.find_device_by_port(self.port1)
        dev2 = self.model.find_device_by_port(self.port2)

        info_group = QGroupBox("Соединение")
        info_layout = QVBoxLayout(info_group)

        info = QLabel(
            f"<b>{dev1.name}</b><br>"
            f"  {self.port1.full_info()}<br>"
            f"  ↓<br>"
            f"<b>{dev2.name}</b><br>"
            f"  {self.port2.full_info()}"
        )
        info_layout.addWidget(info)

        layout.addWidget(info_group)

        # Параметры
        cable_group = QGroupBox("Параметры кабеля")
        cable_form = QFormLayout(cable_group)

        self.cable_combo = QComboBox()
        self.cable_combo.addItems(DeviceFactory.get_cable_types())

        # ✅ Автовыбор типа кабеля по совместимости
        connector = self.port1.connector
        compatible = CONNECTOR_CABLE_COMPATIBILITY.get(connector, [])
        if compatible:
            self.cable_combo.setCurrentText(compatible[0])

        self.cable_combo.setStyleSheet(
            f"color: {CABLE_COLORS.get(self.cable_combo.currentText(), '#000')};"
            "font-weight: bold;"
        )
        self.cable_combo.currentTextChanged.connect(self._on_cable_changed)
        cable_form.addRow("Тип кабеля:", self.cable_combo)

        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(0.1, 10000.0)
        self.length_spin.setValue(1.0)
        self.length_spin.setSuffix(" м")
        cable_form.addRow("Длина:", self.length_spin)

        layout.addWidget(cable_group)

        # Группа
        group_group = QGroupBox("Группа соединений")
        group_layout = QVBoxLayout(group_group)

        self.group_combo = QComboBox()
        self.group_combo.addItem("Без группы", None)
        for g in self.model.groups:
            count = len(self.model.get_group_connections(g))
            self.group_combo.addItem(f"● {g.name} ({count})", g.id)
            idx = self.group_combo.count() - 1
            self.group_combo.setItemIcon(idx, self._make_color_icon(g.color))

        self.group_combo.addItem("+ Новая группа...", "new")
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        group_layout.addWidget(self.group_combo)

        # Панель новой группы
        self.new_group_widget = QWidget()
        new_layout = QVBoxLayout(self.new_group_widget)
        new_layout.setContentsMargins(0, 6, 0, 0)

        new_layout.addWidget(QLabel("Название:"))
        self.new_group_name = QLineEdit()
        self.new_group_name.setPlaceholderText("Название группы")
        new_layout.addWidget(self.new_group_name)

        new_layout.addWidget(QLabel("Цвет:"))
        self.color_picker = ColorPickerWidget()
        new_layout.addWidget(self.color_picker)

        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(28)
        self.color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        new_layout.addWidget(self.color_preview)

        self.color_picker.color_changed.connect(self._on_color_changed)
        self._on_color_changed(self.color_picker.get_color())

        self.new_group_widget.setVisible(False)
        group_layout.addWidget(self.new_group_widget)

        layout.addWidget(group_group)

        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _make_color_icon(self, color: str) -> QIcon:
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(QPen(QColor("#9ca3af"), 1))
        painter.drawRoundedRect(1, 1, 12, 12, 3, 3)
        painter.end()
        return QIcon(pixmap)

    def _on_cable_changed(self, text: str):
        color = CABLE_COLORS.get(text, "#000")
        self.cable_combo.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )

    def _on_group_changed(self, index):
        self.new_group_widget.setVisible(
            self.group_combo.currentData() == "new"
        )

    def _on_color_changed(self, color: str):
        self.color_preview.setStyleSheet(f"""
            background-color: {color};
            border: 2px solid #d0d7e2;
            border-radius: 5px;
            color: white;
            font-weight: bold;
        """)
        self.color_preview.setText(color.upper())

    def _save(self):
        cable_type = self.cable_combo.currentText()
        length = self.length_spin.value()
        group_id = self.group_combo.currentData()

        if group_id == "new":
            name = self.new_group_name.text().strip() or "Новая группа"
            color = self.color_picker.get_color()
            group = self.model.create_group(name, color)
            group_id = group.id

        self.model.add_connection(
            self.port1, self.port2, cable_type, length, group_id
        )
        self.accept()


# ============================================================
#  ДИАЛОГ СОЗДАНИЯ КАНАЛА
# ============================================================

class ChannelSegmentWidget(QGroupBox):
    """Виджет одного сегмента канала."""

    def __init__(self, model: NetworkModel, device1: Device, device2: Device,
                 index: int, parent=None):
        super().__init__(parent)
        self.model = model
        self.device1 = device1
        self.device2 = device2
        self.index = index

        self.setTitle(f"Сегмент {index}: {device1.name} → {device2.name}")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Выходной порт
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Выходной порт:"))
        self.out_port_combo = QComboBox()
        self.out_port_combo.setMinimumWidth(220)
        self._populate_out_ports()
        out_row.addWidget(self.out_port_combo, 1)
        layout.addLayout(out_row)

        # Входной порт
        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("Входной порт:"))
        self.in_port_combo = QComboBox()
        self.in_port_combo.setMinimumWidth(220)
        self._populate_in_ports()
        in_row.addWidget(self.in_port_combo, 1)
        layout.addLayout(in_row)

        # Кабель
        cable_row = QHBoxLayout()
        cable_row.addWidget(QLabel("Кабель:"))

        self.cable_combo = QComboBox()
        self.cable_combo.addItems(DeviceFactory.get_cable_types())
        self.cable_combo.setMinimumWidth(140)
        cable_row.addWidget(self.cable_combo)

        cable_row.addWidget(QLabel("Длина:"))
        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(0.1, 10000.0)
        self.length_spin.setValue(2.0)
        self.length_spin.setSuffix(" м")
        self.length_spin.setDecimals(1)
        self.length_spin.setMaximumWidth(100)
        cable_row.addWidget(self.length_spin)

        cable_row.addStretch()
        layout.addLayout(cable_row)

        # Статус
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 11px; padding: 4px;")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.out_port_combo.currentIndexChanged.connect(self._update_status)
        self.in_port_combo.currentIndexChanged.connect(self._update_status)
        self._update_status()

    def _populate_out_ports(self):
        """Заполняет список выходных портов."""
        self.out_port_combo.clear()
        for port in self.device1.output_ports:
            is_busy = self.model.is_port_connected(port)
            prefix = "❌ " if is_busy else "✅ "
            label = f"{prefix}{port.full_info()}"
            self.out_port_combo.addItem(label, port)

            if is_busy:
                idx = self.out_port_combo.count() - 1
                item = self.out_port_combo.model().item(idx)
                if item:
                    item.setEnabled(False)

        # Автовыбор первого свободного
        for i in range(self.out_port_combo.count()):
            item = self.out_port_combo.model().item(i)
            if item and item.isEnabled():
                self.out_port_combo.setCurrentIndex(i)
                break

    def _populate_in_ports(self):
        """Заполняет список входных портов."""
        self.in_port_combo.clear()
        for port in self.device2.input_ports:
            is_busy = self.model.is_port_connected(port)
            prefix = "❌ " if is_busy else "✅ "
            label = f"{prefix}{port.full_info()}"
            self.in_port_combo.addItem(label, port)

            if is_busy:
                idx = self.in_port_combo.count() - 1
                item = self.in_port_combo.model().item(idx)
                if item:
                    item.setEnabled(False)

        for i in range(self.in_port_combo.count()):
            item = self.in_port_combo.model().item(i)
            if item and item.isEnabled():
                self.in_port_combo.setCurrentIndex(i)
                break

    def _update_status(self):
        """Обновляет статус сегмента."""
        out_port = self.out_port_combo.currentData()
        in_port = self.in_port_combo.currentData()

        if not out_port or not in_port:
            self.status_label.setText("⚠️ Выберите порты")
            self.status_label.setStyleSheet(
                "color: #b45309; font-size: 11px; padding: 4px;"
            )
            return

        can, error = self.model.can_connect(out_port, in_port)
        if can:
            self.status_label.setText("✅ Соединение возможно")
            self.status_label.setStyleSheet(
                "color: #047857; font-size: 11px; padding: 4px;"
            )
        else:
            self.status_label.setText(f"❌ {error}")
            self.status_label.setStyleSheet(
                "color: #b91c1c; font-size: 11px; padding: 4px;"
            )

    def get_connection_data(self) -> Optional[dict]:
        out_port = self.out_port_combo.currentData()
        in_port = self.in_port_combo.currentData()

        if not out_port or not in_port:
            return None

        return {
            'out_port': out_port,
            'in_port': in_port,
            'cable_type': self.cable_combo.currentText(),
            'length': self.length_spin.value()
        }

    def is_valid(self) -> Tuple[bool, str]:
        data = self.get_connection_data()
        if not data:
            return False, "Не выбраны порты"
        can, error = self.model.can_connect(data['out_port'], data['in_port'])
        if not can:
            return False, error
        return True, ""


class ChannelCreationDialog(QDialog):
    """Диалог создания канала связи."""

    def __init__(self, model: NetworkModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.route_devices: List[Device] = []
        self.segment_widgets: List[ChannelSegmentWidget] = []

        self._initialized = False
        self._updating = False

        self.setWindowTitle("Создание канала связи")
        self.resize(850, 800)
        self.setMinimumSize(750, 650)

        self._setup_ui()
        self._initialized = True
        self._update_summary()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ===== Название + Цвет =====
        top_row = QHBoxLayout()

        name_group = QGroupBox("Название канала")
        name_layout = QVBoxLayout(name_group)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Например: Магистраль Москва — СПб")
        self.name_edit.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.name_edit)
        top_row.addWidget(name_group, 2)

        color_group = QGroupBox("Цвет группы")
        color_layout = QVBoxLayout(color_group)
        self.color_picker = ColorPickerWidget()
        self.color_picker.color_changed.connect(self._on_color_changed)
        color_layout.addWidget(self.color_picker)

        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(28)
        self.color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color_layout.addWidget(self.color_preview)
        self._update_color_preview(self.color_picker.get_color())
        top_row.addWidget(color_group, 1)

        layout.addLayout(top_row)

        # ===== Маршрут =====
        route_group = QGroupBox("Маршрут канала")
        route_layout = QHBoxLayout(route_group)

        devices_widget = QWidget()
        devices_layout = QVBoxLayout(devices_widget)
        devices_layout.setContentsMargins(0, 0, 0, 0)
        devices_layout.addWidget(QLabel("Устройства маршрута:"))

        self.route_list = QListWidget()
        self.route_list.setMaximumHeight(140)
        self.route_list.itemDoubleClicked.connect(
            partial(self._on_route_double_clicked)
        )
        devices_layout.addWidget(self.route_list)
        route_layout.addWidget(devices_widget, 1)

        # Кнопки
        btns_widget = QWidget()
        btns_layout = QVBoxLayout(btns_widget)
        btns_layout.setContentsMargins(0, 20, 0, 0)
        btns_layout.setSpacing(4)

        add_btn = QPushButton("➕ Добавить")
        add_btn.clicked.connect(self._add_device)
        btns_layout.addWidget(add_btn)

        remove_btn = QPushButton("➖ Удалить")
        remove_btn.clicked.connect(self._remove_device)
        btns_layout.addWidget(remove_btn)

        up_btn = QPushButton("⬆ Вверх")
        up_btn.clicked.connect(partial(self._move_device, -1))
        btns_layout.addWidget(up_btn)

        down_btn = QPushButton("⬇ Вниз")
        down_btn.clicked.connect(partial(self._move_device, 1))
        btns_layout.addWidget(down_btn)
        btns_layout.addStretch()

        route_layout.addWidget(btns_widget)
        layout.addWidget(route_group)

        # ===== Сегменты =====
        segments_group = QGroupBox("Сегменты канала")
        segments_outer = QVBoxLayout(segments_group)

        self.segments_scroll = QScrollArea()
        self.segments_scroll.setWidgetResizable(True)
        self.segments_scroll.setMinimumHeight(240)
        self.segments_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.segments_container = QWidget()
        self.segments_layout = QVBoxLayout(self.segments_container)
        self.segments_layout.setSpacing(10)
        self.segments_layout.setContentsMargins(0, 0, 0, 0)
        self.segments_layout.addStretch()

        self.segments_scroll.setWidget(self.segments_container)
        segments_outer.addWidget(self.segments_scroll)

        self.empty_hint = QLabel(
            "Добавьте минимум два устройства для создания сегментов."
        )
        self.empty_hint.setStyleSheet(
            "color: #6b7280; font-style: italic; padding: 20px;"
        )
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        segments_outer.addWidget(self.empty_hint)

        layout.addWidget(segments_group, 1)

        # ===== Сводка =====
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet(
            "color: #4a5568; font-size: 12px; padding: 8px; "
            "background-color: #f7f9fc; border-radius: 4px;"
        )
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # ===== Кнопки =====
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._create_channel)
        buttons.rejected.connect(self.reject)

        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText("Создать канал")

        layout.addWidget(buttons)

    def _on_name_changed(self, text: str):
        if self._initialized:
            self._update_summary()

    def _on_color_changed(self, color: str):
        if self._initialized:
            self._update_color_preview(color)

    def _update_color_preview(self, color: str):
        self.color_preview.setStyleSheet(f"""
            background-color: {color};
            border: 2px solid #d0d7e2;
            border-radius: 5px;
            color: white;
            font-weight: bold;
        """)
        self.color_preview.setText(f"Выбранный цвет: {color.upper()}")

    def _on_route_double_clicked(self, item):
        self._remove_device()

    def _add_device(self):
        if not self.model.devices:
            QMessageBox.warning(self, "Внимание", "Нет устройств на схеме")
            return

        device = self._show_device_selector()
        if device:
            self.route_devices.append(device)
            self.route_list.addItem(f"{len(self.route_devices)}. {device.name}")
            self._rebuild_segments()

    def _show_device_selector(self) -> Optional[Device]:
        dialog = QDialog(self)
        dialog.setWindowTitle("Выберите устройство")
        dialog.resize(400, 500)

        layout = QVBoxLayout(dialog)

        search = QLineEdit()
        search.setPlaceholderText("🔍 Поиск...")
        layout.addWidget(search)

        list_widget = QListWidget()
        for d in self.model.devices:
            item = QListWidgetItem(f"{d.name}  ({d.device_type})")
            item.setData(Qt.ItemDataRole.UserRole, d.id)
            list_widget.addItem(item)
        layout.addWidget(list_widget)

        def filter_items(text):
            text = text.lower()
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                item.setHidden(text not in item.text().lower())

        search.textChanged.connect(filter_items)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        result = None
        if dialog.exec() == QDialog.DialogCode.Accepted:
            item = list_widget.currentItem()
            if item:
                dev_id = item.data(Qt.ItemDataRole.UserRole)
                result = next(
                    (d for d in self.model.devices if d.id == dev_id), None
                )
        return result

    def _remove_device(self):
        row = self.route_list.currentRow()
        if 0 <= row < len(self.route_devices):
            self.route_list.takeItem(row)
            del self.route_devices[row]
            self._renumber_route()
            self._rebuild_segments()

    def _move_device(self, direction: int):
        row = self.route_list.currentRow()
        new_row = row + direction
        if (0 <= row < len(self.route_devices) and
                0 <= new_row < len(self.route_devices)):
            self.route_devices[row], self.route_devices[new_row] = \
                self.route_devices[new_row], self.route_devices[row]

            text = self.route_list.takeItem(row)
            self.route_list.insertItem(new_row, text)
            self.route_list.setCurrentRow(new_row)

            self._renumber_route()
            self._rebuild_segments()

    def _renumber_route(self):
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            if i < len(self.route_devices):
                item.setText(f"{i + 1}. {self.route_devices[i].name}")

    def _rebuild_segments(self):
        """Пересоздаёт виджеты сегментов."""
        for w in self.segment_widgets:
            self.segments_layout.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
        self.segment_widgets.clear()

        while self.segments_layout.count() > 1:
            item = self.segments_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        self.empty_hint.setVisible(len(self.route_devices) < 2)

        if len(self.route_devices) >= 2:
            for i in range(len(self.route_devices) - 1):
                d1 = self.route_devices[i]
                d2 = self.route_devices[i + 1]

                segment = ChannelSegmentWidget(
                    self.model, d1, d2, i + 1, self
                )
                self.segment_widgets.append(segment)
                self.segments_layout.insertWidget(i, segment)

        if self._initialized:
            self._update_summary()

    def _update_summary(self):
        if len(self.route_devices) < 2:
            self.summary_label.setText(
                "ℹ️ Добавьте минимум два устройства для создания канала."
            )
            return

        total_length = 0.0
        cable_types = set()
        for w in self.segment_widgets:
            data = w.get_connection_data()
            if data:
                total_length += data['length']
                cable_types.add(data['cable_type'])

        route_str = " → ".join(d.name for d in self.route_devices)
        cable_str = ", ".join(sorted(cable_types)) if cable_types else "—"

        self.summary_label.setText(
            f"📊 <b>Маршрут:</b> {route_str}<br>"
            f"📏 <b>Сегментов:</b> {len(self.segment_widgets)}  •  "
            f"<b>Длина:</b> {total_length:.1f} м  •  "
            f"<b>Кабели:</b> {cable_str}"
        )
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)

    def _create_channel(self):
        if len(self.route_devices) < 2:
            QMessageBox.warning(
                self, "Ошибка", "Добавьте минимум 2 устройства."
            )
            return

        name = self.name_edit.text().strip() or "Новый канал"
        color = self.color_picker.get_color()

        # Проверка сегментов
        errors = []
        for i, w in enumerate(self.segment_widgets):
            valid, error = w.is_valid()
            if not valid:
                errors.append(f"Сегмент {i + 1}: {error}")

        if errors:
            QMessageBox.warning(
                self, "Ошибки в сегментах",
                "Исправьте проблемы:\n\n" + "\n".join(errors)
            )
            return

        group = self.model.create_group(name, color)

        success = 0
        failed = []

        for i, w in enumerate(self.segment_widgets):
            data = w.get_connection_data()
            if not data:
                continue

            conn = self.model.add_connection(
                data['out_port'],
                data['in_port'],
                data['cable_type'],
                data['length'],
                group.id
            )

            if conn:
                success += 1
            else:
                failed.append(f"Сегмент {i + 1}")

        if success == 0:
            self.model.remove_group(group)
            QMessageBox.critical(self, "Ошибка", "Не создано ни одного соединения.")
            return

        message = f"Канал «{name}» создан!\n\nСоединений: {success}"
        if failed:
            message += f"\nНе удалось: {', '.join(failed)}"

        QMessageBox.information(self, "Успех", message)
        self.accept()


# ============================================================
#  УПРАВЛЕНИЕ ГРУППАМИ
# ============================================================

class GroupManagementDialog(QDialog):
    """Управление группами соединений."""

    def __init__(self, model: NetworkModel, parent=None):
        super().__init__(parent)
        self.model = model

        self.setWindowTitle("Управление группами")
        self.resize(750, 550)

        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # Поиск
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по названию...")
        self.search_edit.textChanged.connect(self._refresh_list)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        # Основная область
        main_row = QHBoxLayout()

        self.group_list = QListWidget()
        self.group_list.itemSelectionChanged.connect(self._on_selection_changed)
        main_row.addWidget(self.group_list, 1)

        # Панель редактирования
        edit_panel = QGroupBox("Редактирование")
        edit_panel.setMaximumWidth(300)
        edit_layout = QVBoxLayout(edit_panel)

        edit_layout.addWidget(QLabel("Название:"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)
        edit_layout.addWidget(self.name_edit)

        edit_layout.addWidget(QLabel("Цвет:"))
        self.color_picker = ColorPickerWidget()
        self.color_picker.color_changed.connect(self._on_color_changed)
        edit_layout.addWidget(self.color_picker)

        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(30)
        self.color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit_layout.addWidget(self.color_preview)

        self.visible_cb = QCheckBox("Показывать соединения")
        self.visible_cb.stateChanged.connect(self._on_visibility_changed)
        edit_layout.addWidget(self.visible_cb)

        edit_layout.addStretch()

        self.info_label = QLabel()
        self.info_label.setStyleSheet(
            "color: #6b7280; font-size: 11px; padding: 6px;"
        )
        self.info_label.setWordWrap(True)
        edit_layout.addWidget(self.info_label)

        main_row.addWidget(edit_panel)
        layout.addLayout(main_row, 1)

        # Кнопки
        btn_row = QHBoxLayout()

        toggle_btn = QPushButton("Скрыть/Показать")
        toggle_btn.clicked.connect(self._toggle)
        btn_row.addWidget(toggle_btn)

        show_all_btn = QPushButton("Показать все")
        show_all_btn.clicked.connect(self._show_all)
        btn_row.addWidget(show_all_btn)

        delete_btn = QPushButton("🗑 Удалить")
        delete_btn.setProperty("class", "danger")
        delete_btn.clicked.connect(self._delete)
        btn_row.addWidget(delete_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _make_color_icon(self, color: str) -> QIcon:
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(QPen(QColor("#9ca3af"), 1))
        painter.drawRoundedRect(1, 1, 12, 12, 3, 3)
        painter.end()
        return QIcon(pixmap)

    def _refresh_list(self):
        selected_id = None
        current = self.group_list.currentItem()
        if current:
            selected_id = current.data(Qt.ItemDataRole.UserRole)

        self.group_list.clear()
        ft = self.search_edit.text().strip().lower()

        for g in self.model.groups:
            if not ft or ft in g.name.lower():
                count = len(self.model.get_group_connections(g))
                prefix = "✓" if g.visible else "✗"

                item = QListWidgetItem(f"{prefix}  {g.name}  ({count})")
                item.setData(Qt.ItemDataRole.UserRole, g.id)
                item.setIcon(self._make_color_icon(g.color))
                self.group_list.addItem(item)

                if g.id == selected_id:
                    self.group_list.setCurrentItem(item)

    def _get_selected(self) -> Optional[ConnectionGroup]:
        item = self.group_list.currentItem()
        if item:
            gid = item.data(Qt.ItemDataRole.UserRole)
            return self.model.get_group(gid)
        return None

    def _on_selection_changed(self):
        group = self._get_selected()
        if not group:
            self.name_edit.clear()
            self.info_label.clear()
            return

        self.name_edit.blockSignals(True)
        self.name_edit.setText(group.name)
        self.name_edit.blockSignals(False)

        self.color_picker.set_color(group.color)
        self._update_color_preview(group.color)

        self.visible_cb.blockSignals(True)
        self.visible_cb.setChecked(group.visible)
        self.visible_cb.blockSignals(False)

        conns = self.model.get_group_connections(group)
        total = sum(c.length for c in conns)
        self.info_label.setText(
            f"📊 Соединений: {len(conns)}\n"
            f"📏 Длина: {total:.1f} м"
        )

    def _update_color_preview(self, color: str):
        self.color_preview.setStyleSheet(f"""
            background-color: {color};
            border: 2px solid #d0d7e2;
            border-radius: 5px;
            color: white;
            font-weight: bold;
        """)
        self.color_preview.setText(color.upper())

    def _on_name_changed(self, text: str):
        group = self._get_selected()
        if group and text:
            group.name = text
            self.model.notify_observers()
            item = self.group_list.currentItem()
            if item:
                count = len(self.model.get_group_connections(group))
                prefix = "✓" if group.visible else "✗"
                item.setText(f"{prefix}  {text}  ({count})")

    def _on_color_changed(self, color: str):
        group = self._get_selected()
        if group:
            self.model.update_group_color(group, color)
            self._update_color_preview(color)
            item = self.group_list.currentItem()
            if item:
                item.setIcon(self._make_color_icon(color))

    def _on_visibility_changed(self, state):
        group = self._get_selected()
        if group:
            group.visible = state == Qt.CheckState.Checked.value
            self.model.notify_observers()
            self._refresh_list()

    def _toggle(self):
        group = self._get_selected()
        if group:
            group.visible = not group.visible
            self._refresh_list()
            self._on_selection_changed()
            self.model.notify_observers()

    def _show_all(self):
        for g in self.model.groups:
            g.visible = True
        self._refresh_list()
        self._on_selection_changed()
        self.model.notify_observers()

    def _delete(self):
        group = self._get_selected()
        if group:
            reply = QMessageBox.question(
                self, "Удаление",
                f"Удалить группу '{group.name}'?\n"
                f"Соединения останутся без группы.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.model.remove_group(group)
                self._refresh_list()
                self._on_selection_changed()


# ============================================================
#  КОНТРОЛЛЕР
# ============================================================

class NetworkController(QObject):
    """Контроллер — связывает модель и представление."""

    def __init__(self, model: NetworkModel, canvas: NetworkCanvas, window):
        super().__init__()
        self.model = model
        self.canvas = canvas
        self.window = window

        canvas.connection_requested.connect(self._on_connection_requested)
        canvas.device_edited.connect(self._on_device_edited)
        canvas.device_deleted.connect(self._on_device_deleted)
        canvas.channel_requested.connect(self._on_channel_requested)
        canvas.groups_requested.connect(self._on_groups_requested)

    def delete_selected(self):
        """Удаляет выбранное устройство или порт."""
        if self.canvas.selected_device:
            reply = QMessageBox.question(
                self.canvas, "Удаление",
                f"Удалить устройство '{self.canvas.selected_device.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.model.remove_device(self.canvas.selected_device)
                self.canvas.selected_device = None
                self.canvas.update()
        elif self.canvas.selected_port:
            self.model.remove_connections_for_port(self.canvas.selected_port)
            self.canvas.selected_port = None
            self.canvas.update()

    def _on_connection_requested(self, port1, port2):
        dialog = ConnectionDialog(self.model, port1, port2, self.canvas)
        dialog.exec()

    def _on_device_edited(self, device):
        dialog = DeviceEditDialog(self.model, device, self.canvas)
        dialog.exec()

    def _on_device_deleted(self, device):
        self.model.remove_device(device)

    def _on_channel_requested(self):
        dialog = ChannelCreationDialog(self.model, self.canvas)
        dialog.exec()
        self.canvas.update()

    def _on_groups_requested(self):
        dialog = GroupManagementDialog(self.model, self.canvas)
        dialog.exec()
        self.canvas.update()


# ============================================================
#  ГЛАВНОЕ ОКНО
# ============================================================

class MainWindow(QMainWindow):
    """Главное окно приложения."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Network Visualizer v2.0")
        self.resize(1500, 900)
        self.setMinimumSize(1100, 700)

        self.model = NetworkModel()
        self.canvas = NetworkCanvas(self.model)
        self.controller = NetworkController(self.model, self.canvas, self)

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._create_demo_network()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._create_left_panel())
        layout.addWidget(self.canvas, 1)

    def _create_left_panel(self) -> QWidget:
        """Левая панель инструментов."""
        container = QWidget()
        container.setMinimumWidth(280)
        container.setMaximumWidth(320)
        container.setObjectName("leftPanel")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Заголовок
        header = QLabel("Network Visualizer")
        header.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: #0066cc; padding-bottom: 6px;"
        )
        layout.addWidget(header)

        # Фильтр
        filter_group = QGroupBox("🔍 Фильтр групп")
        fl = QVBoxLayout(filter_group)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Поиск группы...")
        self.filter_edit.textChanged.connect(self.model.set_filter)
        fl.addWidget(self.filter_edit)

        clear_btn = QPushButton("✕ Очистить")
        clear_btn.clicked.connect(lambda: self.filter_edit.clear())
        fl.addWidget(clear_btn)
        layout.addWidget(filter_group)

        # Отображение
        display_group = QGroupBox("👁 Отображение")
        dl = QVBoxLayout(display_group)

        self.show_ports_cb = QCheckBox("Подписи портов")
        self.show_ports_cb.setChecked(True)
        self.show_ports_cb.stateChanged.connect(
            lambda s: setattr(self.model, 'show_port_labels',
                              s == Qt.CheckState.Checked.value)
        )
        self.show_ports_cb.stateChanged.connect(self.model.notify_observers)
        dl.addWidget(self.show_ports_cb)

        self.show_conns_cb = QCheckBox("Подписи соединений")
        self.show_conns_cb.setChecked(True)
        self.show_conns_cb.stateChanged.connect(
            lambda s: setattr(self.model, 'show_connection_labels',
                              s == Qt.CheckState.Checked.value)
        )
        self.show_conns_cb.stateChanged.connect(self.model.notify_observers)
        dl.addWidget(self.show_conns_cb)

        self.show_grid_cb = QCheckBox("Сетка")
        self.show_grid_cb.setChecked(True)
        self.show_grid_cb.stateChanged.connect(
            lambda s: setattr(self.model, 'show_grid',
                              s == Qt.CheckState.Checked.value)
        )
        self.show_grid_cb.stateChanged.connect(self.model.notify_observers)
        dl.addWidget(self.show_grid_cb)

        layout.addWidget(display_group)

        # Легенда кабелей
        legend_group = QGroupBox("🔌 Типы кабелей")
        legend_layout = QVBoxLayout(legend_group)
        legend_layout.setSpacing(4)

        for cable_name, color in CABLE_COLORS.items():
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 2, 4, 2)
            rl.setSpacing(8)

            marker = QLabel()
            marker.setFixedSize(24, 4)
            marker.setStyleSheet(f"""
                background-color: {color};
                border-radius: 2px;
            """)
            rl.addWidget(marker)

            label = QLabel(cable_name)
            label.setStyleSheet("color: #4a5568; font-size: 11px;")
            rl.addWidget(label, 1)

            legend_layout.addWidget(row)

        layout.addWidget(legend_group)

        # Типы портов
        ports_legend = QGroupBox("🔗 Типы разъёмов")
        pl = QVBoxLayout(ports_legend)
        pl.setSpacing(4)

        for connector, color in CONNECTOR_COLORS.items():
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 2, 4, 2)
            rl.setSpacing(8)

            marker = QLabel()
            marker.setFixedSize(12, 12)
            marker.setStyleSheet(f"""
                background-color: {color};
                border-radius: 3px;
                border: 1px solid #4b5563;
            """)
            rl.addWidget(marker)

            label = QLabel(connector)
            label.setStyleSheet("color: #4a5568; font-size: 11px;")
            rl.addWidget(label, 1)

            pl.addWidget(row)

        layout.addWidget(ports_legend)

        # Действия
        actions_group = QGroupBox("Действия")
        al = QVBoxLayout(actions_group)
        al.setSpacing(6)

        channel_btn = QPushButton("🔗 Создать канал")
        channel_btn.clicked.connect(self.controller._on_channel_requested)
        al.addWidget(channel_btn)

        groups_btn = QPushButton("📊 Группы соединений")
        groups_btn.clicked.connect(self.controller._on_groups_requested)
        al.addWidget(groups_btn)

        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self._save_project)
        al.addWidget(save_btn)

        load_btn = QPushButton("📂 Загрузить")
        load_btn.clicked.connect(self._load_project)
        al.addWidget(load_btn)

        delete_btn = QPushButton("🗑️ Удалить выбранное")
        delete_btn.setProperty("class", "danger")
        delete_btn.clicked.connect(self.controller.delete_selected)
        al.addWidget(delete_btn)

        layout.addWidget(actions_group)

        layout.addStretch()

        scroll.setWidget(panel)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        return container

    def _setup_menu(self):
        menubar = self.menuBar()

        # Файл
        file_menu = menubar.addMenu("Файл")

        new_action = QAction("Новый проект", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        save_action = QAction("Сохранить", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)

        load_action = QAction("Загрузить", self)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        load_action.triggered.connect(self._load_project)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Правка
        edit_menu = menubar.addMenu("Правка")

        channel_action = QAction("Создать канал...", self)
        channel_action.triggered.connect(self.controller._on_channel_requested)
        edit_menu.addAction(channel_action)

        groups_action = QAction("Управление группами...", self)
        groups_action.triggered.connect(self.controller._on_groups_requested)
        edit_menu.addAction(groups_action)

        edit_menu.addSeparator()

        delete_action = QAction("Удалить выбранное", self)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.triggered.connect(self.controller.delete_selected)
        edit_menu.addAction(delete_action)

        # Вид
        view_menu = menubar.addMenu("Вид")

        ports_action = QAction("Подписи портов", self)
        ports_action.setCheckable(True)
        ports_action.setChecked(True)
        ports_action.toggled.connect(self.show_ports_cb.setChecked)
        view_menu.addAction(ports_action)

        conns_action = QAction("Подписи соединений", self)
        conns_action.setCheckable(True)
        conns_action.setChecked(True)
        conns_action.toggled.connect(self.show_conns_cb.setChecked)
        view_menu.addAction(conns_action)

        grid_action = QAction("Сетка", self)
        grid_action.setCheckable(True)
        grid_action.setChecked(True)
        grid_action.toggled.connect(self.show_grid_cb.setChecked)
        view_menu.addAction(grid_action)

        # Помощь
        help_menu = menubar.addMenu("Помощь")

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        toolbar = QToolBar("Основная")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction("📄 Новый", self)
        new_action.triggered.connect(self._new_project)
        toolbar.addAction(new_action)

        save_action = QAction("💾 Сохранить", self)
        save_action.triggered.connect(self._save_project)
        toolbar.addAction(save_action)

        load_action = QAction("📂 Загрузить", self)
        load_action.triggered.connect(self._load_project)
        toolbar.addAction(load_action)

        toolbar.addSeparator()

        channel_action = QAction("🔗 Канал", self)
        channel_action.triggered.connect(self.controller._on_channel_requested)
        toolbar.addAction(channel_action)

        groups_action = QAction("📊 Группы", self)
        groups_action.triggered.connect(self.controller._on_groups_requested)
        toolbar.addAction(groups_action)

        toolbar.addSeparator()

        delete_action = QAction("🗑️ Удалить", self)
        delete_action.triggered.connect(self.controller.delete_selected)
        toolbar.addAction(delete_action)

    def _setup_statusbar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            "ПКМ на канвасе — создать устройство  •  "
            "ПКМ на порте (■) — начать соединение  •  "
            "Двойной клик — редактировать  •  "
            "Ctrl+ЛКМ — панорамирование  •  Колесико — масштаб"
        )

    def _create_demo_network(self):
        """Демонстрационная сеть из фабричных шаблонов."""
        # Создаём устройства
        mc = self.model.add_device_from_template("Магистральный кросс", 200, 200)
        oc = self.model.add_device_from_template("Оптический кросс", 200, 500)
        ag = self.model.add_device_from_template("Агрегатор 100Gb", 600, 200)
        sw = self.model.add_device_from_template("Коммутатор 10Gb", 600, 500)
        srv = self.model.add_device_from_template("Сервер 100Gb", 1000, 200)
        stor = self.model.add_device_from_template("Хранилище", 1000, 500)

        # Группы
        g1 = self.model.create_group("Магистраль МСК-СПб", "#f59e0b")
        g2 = self.model.create_group("ЦОД Storage", "#8b5cf6")
        g3 = self.model.create_group("Резервные каналы", "#ef4444")

        # Соединения с проверкой
        if mc and oc:
            self.model.add_connection(
                mc.output_ports[0], oc.input_ports[0],
                "Optical MPO", 50.0, g1.id
            )

        if oc and ag:
            self.model.add_connection(
                oc.output_ports[0], ag.input_ports[0],
                "Optical LC", 5.0, g1.id
            )

        if ag and sw:
            self.model.add_connection(
                ag.output_ports[0], sw.input_ports[0],
                "Optical LC", 2.0, g3.id
            )

        if ag and srv:
            self.model.add_connection(
                ag.output_ports[1], srv.input_ports[0],
                "Infiniband", 3.0, g2.id
            )

        if sw and stor:
            self.model.add_connection(
                sw.output_ports[0], stor.input_ports[0],
                "Ethernet", 1.0, None
            )

    def _new_project(self):
        reply = QMessageBox.question(
            self, "Новый проект", "Создать новый проект?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.model.devices.clear()
            self.model.connections.clear()
            self.model.groups.clear()
            self.model.next_device_id = 0
            self.model.next_group_id = 0
            self.model.notify_observers()

    def _save_project(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", "", "JSON Files (*.json)"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.model.to_dict(), f, indent=2, ensure_ascii=False)
                self.status_bar.showMessage(f"Сохранено: {filename}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    def _load_project(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Загрузить проект", "", "JSON Files (*.json)"
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.model.from_dict(json.load(f))
                self.status_bar.showMessage(f"Загружено: {filename}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить: {e}")

    def _show_about(self):
        QMessageBox.about(
            self, "О программе",
            "<h2>Network Visualizer v2.0</h2>"
            "<p>Визуализация сетевой инфраструктуры</p>"
            "<p><b>Типы кабелей:</b></p>"
            "<ul>"
            "<li><span style='color:#f59e0b'>■</span> Optical LC</li>"
            "<li><span style='color:#8b5cf6'>■</span> Optical MPO</li>"
            "<li><span style='color:#4b5563'>■</span> Infiniband</li>"
            "<li><span style='color:#9ca3af'>■</span> Ethernet</li>"
            "</ul>"
            "<p><b>Типы разъёмов:</b> SFP LC, SFP MPO, FC, MPO, Ethernet, RJ45</p>"
            "<p><b>Скорости:</b> 1Gb, 10Gb, 100Gb</p>"
        )


# ============================================================
#  СТИЛИ И ЗАПУСК
# ============================================================

APP_STYLE = """
    QWidget {
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 13px;
        color: #2c3e50;
    }
    QMainWindow, QDialog {
        background-color: #f7f9fc;
    }
    QMenuBar {
        background-color: #ffffff;
        border-bottom: 1px solid #e3e8ef;
        padding: 4px 8px;
    }
    QMenuBar::item {
        padding: 6px 12px;
        border-radius: 4px;
    }
    QMenuBar::item:selected {
        background-color: #e8f0fe;
        color: #0066cc;
    }
    QMenu {
        background-color: #ffffff;
        border: 1px solid #e3e8ef;
        border-radius: 6px;
        padding: 5px;
    }
    QMenu::item {
        padding: 7px 20px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: #e8f0fe;
        color: #0066cc;
    }
    QMenu::separator {
        height: 1px;
        background-color: #e3e8ef;
        margin: 4px 10px;
    }
    QToolBar {
        background-color: #ffffff;
        border-bottom: 1px solid #e3e8ef;
        padding: 4px 8px;
        spacing: 4px;
    }
    QToolButton {
        padding: 6px 10px;
        border-radius: 4px;
        background: transparent;
    }
    QToolButton:hover {
        background-color: #e8f0fe;
        color: #0066cc;
    }
    QPushButton {
        padding: 7px 14px;
        border: 1px solid #d0d7e2;
        border-radius: 5px;
        background-color: #ffffff;
        min-height: 16px;
    }
    QPushButton:hover {
        background-color: #f0f4fa;
        border-color: #b8c4d4;
    }
    QPushButton:pressed {
        background-color: #e2e9f3;
    }
    QPushButton:default {
        border-color: #0066cc;
        background-color: #0066cc;
        color: #ffffff;
    }
    QPushButton[class="danger"] {
        color: #d92d20;
    }
    QPushButton[class="danger"]:hover {
        background-color: #fef3f2;
        border-color: #fda29b;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        padding: 6px 10px;
        border: 1px solid #d0d7e2;
        border-radius: 5px;
        background-color: #ffffff;
        min-height: 16px;
        selection-background-color: #b8d4f8;
    }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
        border-color: #0066cc;
    }
    QComboBox::drop-down {
        border: none;
        width: 22px;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid #6b7280;
        margin-right: 6px;
    }
    QComboBox QAbstractItemView {
        background-color: #ffffff;
        border: 1px solid #e3e8ef;
        border-radius: 5px;
        selection-background-color: #e8f0fe;
        selection-color: #0066cc;
        outline: none;
        padding: 4px;
    }
    QCheckBox {
        padding: 4px 0;
        spacing: 8px;
    }
    QCheckBox::indicator {
        width: 15px;
        height: 15px;
        border: 1px solid #d0d7e2;
        border-radius: 3px;
        background-color: #ffffff;
    }
    QCheckBox::indicator:checked {
        background-color: #0066cc;
        border-color: #0066cc;
    }
    QGroupBox {
        background-color: #ffffff;
        border: 1px solid #e3e8ef;
        border-radius: 8px;
        margin-top: 14px;
        padding-top: 12px;
        font-weight: 600;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
        color: #0066cc;
        background-color: #ffffff;
    }
    QListWidget, QTreeWidget {
        background-color: #ffffff;
        border: 1px solid #e3e8ef;
        border-radius: 6px;
        padding: 4px;
        outline: none;
        selection-background-color: #e8f0fe;
        selection-color: #0066cc;
    }
    QListWidget::item {
        padding: 6px 8px;
        border-radius: 4px;
    }
    QListWidget::item:hover {
        background-color: #f0f4fa;
    }
    QScrollBar:vertical {
        background: transparent;
        width: 10px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #cbd5e0;
        border-radius: 5px;
        min-height: 30px;
        margin: 2px;
    }
    QScrollBar::handle:vertical:hover {
        background: #a0aec0;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
    QStatusBar {
        background-color: #ffffff;
        border-top: 1px solid #e3e8ef;
        color: #6b7280;
        padding: 2px 8px;
    }
    QScrollArea {
        border: none;
        background-color: transparent;
    }
    #leftPanel {
        background-color: #ffffff;
        border-right: 1px solid #e3e8ef;
    }
    QToolTip {
        background-color: #2c3e50;
        color: #ffffff;
        border: none;
        border-radius: 4px;
        padding: 6px 10px;
    }
"""


def main():
    """Точка входа приложения."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()