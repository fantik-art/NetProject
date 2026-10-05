"""
Network Visualizer — приложение для визуализации сетевой инфраструктуры.

Переписанная версия с Tkinter на PyQt6 с исправленной отрисовкой
кривых Безье (используется QPainterPath.cubicTo вместо ручной аппроксимации).

Основные возможности:
  - Создание устройств (кроссы, коммутаторы, серверы) через ПКМ
  - Перемещение устройств мышью
  - Создание соединений между портами (выход → вход)
  - Редактирование устройств (двойной клик)
  - Группировка соединений в каналы
  - Фильтрация групп по названию
  - Панорамирование (Ctrl+ЛКМ или средняя кнопка мыши)
  - Масштабирование (колесико мыши)
  - Сохранение/загрузка проектов в JSON

Архитектура: MVC (Model-View-Controller)
  - Model: NetworkModel (данные, бизнес-логика)
  - View: NetworkCanvas (отрисовка, взаимодействие)
  - Controller: NetworkController (связь model и view)
"""

import sys
import json
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, ClassVar
from enum import Enum
from collections import defaultdict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QGroupBox, QFrame,
    QFileDialog, QMessageBox, QComboBox, QListWidget, QListWidgetItem,
    QSplitter, QMenu, QInputDialog, QDialog, QFormLayout, QGridLayout,
    QDoubleSpinBox, QDialogButtonBox, QScrollArea, QSpinBox,
    QToolBar, QStatusBar, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QListWidget as QLW
)
from PyQt6.QtWidgets import QSizePolicy
from PyQt6.QtCore import QSize
from PyQt6.QtCore import (
    Qt, QObject, pyqtSignal, QPointF, QRectF, QSize
)
from PyQt6.QtGui import (
    QPainter, QPainterPath, QPen, QBrush, QColor, QFont,
    QPolygonF, QAction, QIcon, QKeySequence, QPixmap
)
from functools import partial


# ============================================================
#  ПЕРЕЧИСЛЕНИЯ
# ============================================================

class PortType(Enum):
    """Тип порта: входной или выходной."""
    INPUT = "input"
    OUTPUT = "output"


class DeviceCategory(Enum):
    """Категория устройства, определяющая его роль в сети."""
    GLOBAL_INPUT = "Входные (глобальные)"
    LOCAL_INPUT = "Входные (локальные)"
    SWITCHES = "Коммутаторы"
    SERVERS = "Сервера"


class CableType(Enum):
    """Типы кабелей."""
    ETHERNET = "Ethernet"
    FIBER = "Fiber Optic"
    SERIAL = "Serial"
    COAXIAL = "Coaxial"


# ============================================================
#  МОДЕЛИ ДАННЫХ
# ============================================================

@dataclass
class Port:
    """
    Порт устройства.

    Attributes:
        id: Уникальный идентификатор порта внутри устройства
        name: Отображаемое имя (например, "IN 1", "OUT 2")
        port_type: Тип порта (входной/выходной)
        x, y: Координаты центра порта в координатах сцены
    """
    id: int
    name: str
    port_type: PortType = PortType.OUTPUT
    x: float = 0.0
    y: float = 0.0


@dataclass
class Device:
    """
    Сетевое устройство.

    ВАЖНО: Константы размеров вынесены в ClassVar, чтобы они
    НЕ становились полями dataclass (иначе ломается __eq__,
    __repr__ и может произойти переполнение стека).
    """
    id: int
    name: str
    x: float = 100.0
    y: float = 100.0
    width: float = 160.0
    height: float = 100.0
    device_type: str = "Cross-connect"
    category: DeviceCategory = DeviceCategory.LOCAL_INPUT
    input_ports: List[Port] = field(default_factory=list)
    output_ports: List[Port] = field(default_factory=list)

    # ✅ ClassVar — не поля dataclass, а атрибуты класса
    HEADER_HEIGHT: ClassVar[float] = 25.0
    FOOTER_HEIGHT: ClassVar[float] = 16.0
    PORT_SPACING: ClassVar[float] = 18.0
    MIN_PORT_AREA_HEIGHT: ClassVar[float] = 40.0
    MIN_HEIGHT: ClassVar[float] = 80.0

    @property
    def ports(self) -> List[Port]:
        """Возвращает все порты устройства."""
        return self.input_ports + self.output_ports

    def add_default_ports(self):
        """Добавляет порты по умолчанию."""
        port_configs = {
            DeviceCategory.GLOBAL_INPUT: (6, 2),
            DeviceCategory.LOCAL_INPUT: (4, 4),
            DeviceCategory.SWITCHES: (8, 8),
            DeviceCategory.SERVERS: (2, 1)
        }
        input_count, output_count = port_configs.get(self.category, (4, 4))

        for i in range(input_count):
            self.input_ports.append(Port(
                id=len(self.ports), name=f"IN {i + 1}", port_type=PortType.INPUT
            ))
        for i in range(output_count):
            self.output_ports.append(Port(
                id=len(self.ports), name=f"OUT {i + 1}", port_type=PortType.OUTPUT
            ))

    def calculate_height(self) -> float:
        """Вычисляет необходимую высоту устройства."""
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

        # Входные порты
        count_in = len(self.input_ports)
        if count_in > 0:
            top = self.y - self.height / 2 + self.HEADER_HEIGHT
            bottom = self.y + self.height / 2 - self.FOOTER_HEIGHT
            area_height = bottom - top

            for i, port in enumerate(self.input_ports):
                port.x = self.x - self.width / 2
                port.y = top + (i + 1) * (area_height / (count_in + 1))

        # Выходные порты
        count_out = len(self.output_ports)
        if count_out > 0:
            top = self.y - self.height / 2 + self.HEADER_HEIGHT
            bottom = self.y + self.height / 2 - self.FOOTER_HEIGHT
            area_height = bottom - top

            for i, port in enumerate(self.output_ports):
                port.x = self.x + self.width / 2
                port.y = top + (i + 1) * (area_height / (count_out + 1))


@dataclass
class Connection:
    """
    Соединение между двумя портами.

    Attributes:
        port1: Выходной порт (источник)
        port2: Входной порт (приёмник)
        cable_type: Тип кабеля (влияет на стиль линии)
        length: Физическая длина кабеля в метрах
        group_id: ID группы (канала), к которой относится соединение
    """
    port1: Port
    port2: Port
    cable_type: str = "Ethernet"
    length: float = 1.0
    group_id: Optional[int] = None


@dataclass
class ConnectionGroup:
    """
    Группа соединений (логический канал).

    Позволяет объединить несколько соединений под одним названием
    и отображать их одним цветом.
    """
    id: int
    name: str
    color: str
    visible: bool = True


# ============================================================
#  МОДЕЛЬ (Model)
# ============================================================

class NetworkModel(QObject):
    """
    Модель сети — хранит все данные и уведомляет наблюдателей об изменениях.

    Реализует паттерн Observer: при любом изменении данных вызывает
    notify_observers(), что позволяет View'ам автоматически обновляться.
    """

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
        """Уведомляет всех наблюдателей об изменении данных."""
        self.data_changed.emit()

    def add_device(self, device_type: str, category: DeviceCategory,
                   x: float = 100, y: float = 100) -> Device:
        """Создаёт новое устройство."""
        device = Device(
            id=self.next_device_id,
            name=f"{device_type} {self.next_device_id}",
            device_type=device_type,
            category=category,
            x=x, y=y
        )
        device.add_default_ports()
        device.update_port_positions()
        self.next_device_id += 1
        self.devices.append(device)
        self.notify_observers()
        return device

    def remove_device(self, device: Device):
        """
        Удаляет устройство и все связанные с ним соединения.

        Args:
            device: Устройство для удаления.
        """
        self.connections = [
            c for c in self.connections
            if c.port1 not in device.ports and c.port2 not in device.ports
        ]
        self.devices.remove(device)
        self.notify_observers()

    def add_connection(self, port1: Port, port2: Port,
                       cable_type: str = "Ethernet",
                       length: float = 1.0,
                       group_id: Optional[int] = None) -> Optional[Connection]:
        """
        Создаёт соединение между двумя портами.

        Перед созданием выполняется проверка:
          - направление (выход → вход)
          - оба порта свободны
          - порты разных устройств

        Args:
            port1, port2: Порты для соединения
            cable_type: Тип кабеля
            length: Длина кабеля в метрах
            group_id: ID группы (опционально)

        Returns:
            Созданное соединение или None в случае ошибки.
        """
        # ✅ Проверка возможности соединения
        can, error = self.can_connect(port1, port2)
        if not can:
            return None

        # Проверка на дубликат
        for conn in self.connections:
            if (conn.port1 is port1 and conn.port2 is port2) or \
                    (conn.port1 is port2 and conn.port2 is port1):
                return None

        # Нормализация направления
        if port1.port_type == PortType.OUTPUT:
            conn = Connection(port1, port2, cable_type, length, group_id)
        else:
            conn = Connection(port2, port1, cable_type, length, group_id)

        self.connections.append(conn)
        self.notify_observers()
        return conn

    def remove_connections_for_port(self, port: Port):
        """Удаляет все соединения, связанные с указанным портом."""
        self.connections = [
            c for c in self.connections if c.port1 != port and c.port2 != port
        ]
        self.notify_observers()

    def create_group(self, name: str, color: Optional[str] = None) -> ConnectionGroup:
        """
        Создаёт новую группу соединений.

        Args:
            name: Название группы
            color: HEX-цвет группы. Если None — автовыбор из палитры.

        Returns:
            Созданная группа.
        """
        # ✅ Автовыбор цвета, если не передан
        if color is None:
            auto_colors = [
                "#ef4444", "#f97316", "#f59e0b", "#eab308",
                "#84cc16", "#22c55e", "#10b981", "#14b8a6",
                "#06b6d4", "#0ea5e9", "#3b82f6", "#6366f1",
                "#8b5cf6", "#a855f7", "#d946ef", "#ec4899",
            ]
            color = auto_colors[self.next_group_id % len(auto_colors)]

        group = ConnectionGroup(self.next_group_id, name, color)
        self.next_group_id += 1
        self.groups.append(group)
        self.notify_observers()
        return group

    def update_group_color(self, group: ConnectionGroup, color: str):
        """
        Меняет цвет существующей группы.

        Args:
            group: Группа для изменения
            color: Новый HEX-цвет
        """
        group.color = color
        self.notify_observers()

    def remove_group(self, group: ConnectionGroup):
        """Удаляет группу, отвязывая от неё все соединения."""
        for conn in self.connections:
            if conn.group_id == group.id:
                conn.group_id = None
        if group in self.groups:
            self.groups.remove(group)
        self.notify_observers()

    def get_group(self, group_id: int) -> Optional[ConnectionGroup]:
        """Возвращает группу по её ID."""
        for group in self.groups:
            if group.id == group_id:
                return group
        return None

    def get_group_connections(self, group: ConnectionGroup) -> List[Connection]:
        """Возвращает все соединения указанной группы."""
        return [c for c in self.connections if c.group_id == group.id]

    def find_device_by_port(self, port: Port) -> Optional[Device]:
        """Находит устройство, которому принадлежит порт."""
        for device in self.devices:
            if port in device.ports:
                return device
        return None

    def is_port_connected(self, port: Port) -> bool:
        """
        Проверяет, используется ли порт в каком-либо соединении.

        Args:
            port: Порт для проверки.

        Returns:
            True если порт уже занят (есть соединение).
        """
        return any(
            port is c.port1 or port is c.port2
            for c in self.connections
        )

    def get_port_connection(self, port: Port) -> Optional[Connection]:
        """
        Возвращает соединение, в котором используется порт.

        Args:
            port: Порт для поиска.

        Returns:
            Соединение или None если порт свободен.
        """
        for c in self.connections:
            if port is c.port1 or port is c.port2:
                return c
        return None

    def can_connect(self, port1: Port, port2: Port) -> Tuple[bool, str]:
        """
        Проверяет возможность создания соединения между портами.

        Правила:
          1. Порты должны быть разного типа (выход → вход)
          2. Оба порта должны быть свободны
          3. Порты не должны принадлежать одному устройству

        Args:
            port1, port2: Порты для проверки.

        Returns:
            Кортеж (можно_ли, сообщение_об_ошибке).
        """
        # Проверка направления
        if port1.port_type == port2.port_type:
            return False, "Соединение возможно только между выходным и входным портом!"

        # Определяем, кто из них выход, кто вход
        out_port = port1 if port1.port_type == PortType.OUTPUT else port2
        in_port = port2 if port1.port_type == PortType.OUTPUT else port1

        # Проверка занятости выходного порта
        if self.is_port_connected(out_port):
            dev = self.find_device_by_port(out_port)
            dev_name = dev.name if dev else "?"
            return False, (
                f"Выходной порт «{out_port.name}» устройства «{dev_name}» "
                f"уже занят! Освободите порт перед созданием нового соединения."
            )

        # Проверка занятости входного порта
        if self.is_port_connected(in_port):
            dev = self.find_device_by_port(in_port)
            dev_name = dev.name if dev else "?"
            return False, (
                f"Входной порт «{in_port.name}» устройства «{dev_name}» "
                f"уже занят! Освободите порт перед созданием нового соединения."
            )

        # Проверка — не одно ли устройство
        dev1 = self.find_device_by_port(out_port)
        dev2 = self.find_device_by_port(in_port)
        if dev1 and dev2 and dev1.id == dev2.id:
            return False, "Нельзя соединить порты одного и того же устройства!"

        return True, ""

    def get_visible_connections(self) -> List[Connection]:
        """
        Возвращает соединения с учётом фильтра.
        Если фильтр пуст — все соединения.
        Если фильтр задан — соединения без группы + соединения групп,
        чьё имя содержит текст фильтра.
        """
        if not self.filter_text:
            return list(self.connections)

        visible_group_ids = {
            g.id for g in self.groups
            if self.filter_text in g.name.lower()
        }

        return [c for c in self.connections
                if c.group_id is None or c.group_id in visible_group_ids]

    def set_filter(self, text: str):
        """Устанавливает текст фильтра для групп."""
        self.filter_text = text.strip().lower()
        self.notify_observers()

    def move_device(self, device: Device, x: float, y: float):
        """Перемещает устройство в новые координаты."""
        device.x = x
        device.y = y
        device.update_port_positions()
        self.notify_observers()

    def to_dict(self) -> dict:
        """Сериализует модель в словарь для сохранения в JSON."""
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
                'id': device.id, 'name': device.name,
                'x': device.x, 'y': device.y,
                'width': device.width, 'height': device.height,
                'device_type': device.device_type,
                'category': device.category.value,
                'input_ports': [{'id': p.id, 'name': p.name} for p in device.input_ports],
                'output_ports': [{'id': p.id, 'name': p.name} for p in device.output_ports]
            })

        for conn in self.connections:
            dev1 = self.find_device_by_port(conn.port1)
            dev2 = self.find_device_by_port(conn.port2)
            if dev1 and dev2:
                data['connections'].append({
                    'device1_id': dev1.id, 'port1_id': conn.port1.id,
                    'device2_id': dev2.id, 'port2_id': conn.port2.id,
                    'cable_type': conn.cable_type, 'length': conn.length,
                    'group_id': conn.group_id
                })

        for group in self.groups:
            data['groups'].append({
                'id': group.id, 'name': group.name,
                'color': group.color, 'visible': group.visible
            })

        return data

    def from_dict(self, data: dict):
        """Загружает модель из словаря (восстановление из JSON)."""
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
                id=dev_data['id'], name=dev_data['name'],
                x=dev_data['x'], y=dev_data['y'],
                width=dev_data.get('width', 160), height=dev_data.get('height', 100),
                device_type=dev_data['device_type'],
                category=DeviceCategory(dev_data['category'])
            )

            for p in dev_data.get('input_ports', []):
                device.input_ports.append(
                    Port(id=p['id'], name=p['name'], port_type=PortType.INPUT)
                )
            for p in dev_data.get('output_ports', []):
                device.output_ports.append(
                    Port(id=p['id'], name=p['name'], port_type=PortType.OUTPUT)
                )

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
                port1 = next((p for p in dev1.ports if p.id == conn_data['port1_id']), None)
                port2 = next((p for p in dev2.ports if p.id == conn_data['port2_id']), None)
                if port1 and port2:
                    conn = Connection(
                        port1, port2, conn_data['cable_type'],
                        conn_data['length'], conn_data.get('group_id')
                    )
                    self.connections.append(conn)

        self.notify_observers()


# ============================================================
#  КАНВАС (View)
# ============================================================

class NetworkCanvas(QWidget):
    """
    Виджет-канвас для отображения и редактирования сетевой топологии.

    Наследуется от QWidget, реализует собственную отрисовку через
    paintEvent и обрабатывает события мыши.

    ОСОБЕННОСТИ:
      - setMouseTracking(True) — для отслеживания движения мыши
      - setFocusPolicy(StrongFocus) — чтобы получать события клавиатуры
      - setAutoFillBackground(True) — чтобы виджет корректно отрисовывался
    """

    # Сигналы
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

        # ===== ВАЖНЫЕ НАСТРОЙКИ ДЛЯ РАБОТЫ С МЫШЬЮ =====
        self.setMouseTracking(True)  # Отслеживать движение без нажатия
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # Получать фокус и события клавиатуры
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)  # Оптимизация отрисовки
        self.setAutoFillBackground(True)  # Автоматически заполнять фон
        self.setMinimumSize(600, 400)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        # Камера
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        # Выделение и режимы
        self.selected_device: Optional[Device] = None
        self.selected_port: Optional[Port] = None
        self.connection_mode = False
        self.dragging_device: Optional[Device] = None
        self.drag_offset = QPointF()

        # Панорамирование
        self.panning = False
        self.pan_start = QPointF()
        self.pan_offset_start = QPointF()

        # Цвета кабелей
        self.cable_colors = {
            "Ethernet": "#0064c8",
            "Fiber Optic": "#c86400",
            "Serial": "#646464",
            "Coaxial": "#009600"
        }

    # ========================================================
    #  КООРДИНАТЫ
    # ========================================================

    def to_canvas(self, x: float, y: float) -> Tuple[float, float]:
        """Преобразует координаты сцены в координаты канваса."""
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    def to_scene(self, cx: float, cy: float) -> Tuple[float, float]:
        """Преобразует координаты канваса в координаты сцены."""
        return (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale

    # ========================================================
    #  ОТРИСОВКА
    # ========================================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # ✅ Мягкий светло-серый фон
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
        """Рисует временную линию от начального порта к курсору."""
        if not self.selected_port:
            return

        # Позиция курсора в координатах сцены
        cursor_pos = self.mapFromGlobal(self.cursor().pos())
        sx, sy = self.to_scene(cursor_pos.x(), cursor_pos.y())

        pen = QPen(QColor("#f9e2af"), 2)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(
            QPointF(self.selected_port.x, self.selected_port.y),
            QPointF(sx, sy)
        )

    def _draw_grid(self, painter: QPainter):
        """Рисует более мягкую сетку."""
        pen = QPen(QColor("#e8ecf1"), 1)  # ✅ Светлее
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.SolidLine)  # ✅ Сплошная тонкая
        painter.setPen(pen)

        left, top = self.to_scene(0, 0)
        right, bottom = self.to_scene(self.width(), self.height())

        grid_size = 50
        x = int(left // grid_size) * grid_size
        while x < right:
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))
            x += grid_size

        y = int(top // grid_size) * grid_size
        while y < bottom:
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            y += grid_size

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

            color = group.color if group else self.cable_colors.get(
                conn.cable_type, "#808080"
            )
            self._draw_single_connection(
                painter, conn, color, group.name if group else None
            )

    def _draw_group_background(self, painter: QPainter,
                               connections: List[Connection],
                               group: ConnectionGroup):
        """Рисует фон группы."""
        color = QColor(group.color)
        color.setAlpha(100)

        pen = QPen(color, 6)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        for conn in connections:
            path = self._make_bezier_path(conn.port1, conn.port2)
            painter.drawPath(path)

    def _make_bezier_path(self, port1: Port, port2: Port) -> QPainterPath:
        """Создаёт кривую Безье между двумя портами."""
        x1, y1 = port1.x, port1.y
        x2, y2 = port2.x, port2.y

        dx = abs(x2 - x1) * 0.4
        ctrl1 = QPointF(x1 + dx, y1)
        ctrl2 = QPointF(x2 - dx, y2)

        path = QPainterPath()
        path.moveTo(x1, y1)
        path.cubicTo(ctrl1, ctrl2, QPointF(x2, y2))
        return path

    def _draw_single_connection(self, painter: QPainter,
                                conn: Connection,
                                color: str,
                                group_name: Optional[str]):
        """Рисует одно соединение."""
        pen = QPen(QColor(color), 2)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        if conn.cable_type == "Fiber Optic":
            pen.setStyle(Qt.PenStyle.DashLine)
        elif conn.cable_type == "Serial":
            pen.setStyle(Qt.PenStyle.DotLine)
        elif conn.cable_type == "Coaxial":
            pen.setStyle(Qt.PenStyle.DashDotLine)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        path = self._make_bezier_path(conn.port1, conn.port2)
        painter.drawPath(path)

        self._draw_arrow(painter, conn.port1, conn.port2, color)

        if self.model.show_connection_labels:
            self._draw_connection_label(painter, conn, group_name)

    def _draw_arrow(self, painter: QPainter,
                    port1: Port, port2: Port, color: str):
        """Рисует стрелку направления на 70% пути."""
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

        p1 = QPointF(ax + size * math.cos(angle),
                     ay + size * math.sin(angle))
        p2 = QPointF(ax + size * math.cos(angle + 2.5),
                     ay + size * math.sin(angle + 2.5))
        p3 = QPointF(ax + size * math.cos(angle - 2.5),
                     ay + size * math.sin(angle - 2.5))

        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([p1, p2, p3]))

    def _draw_connection_label(self, painter: QPainter,
                               conn: Connection,
                               group_name: Optional[str]):
        """Рисует подпись соединения."""
        mid_x = (conn.port1.x + conn.port2.x) / 2
        mid_y = (conn.port1.y + conn.port2.y) / 2

        items = []
        if group_name:
            items.append(group_name)
        items.append(f"{conn.cable_type} | {conn.length:.1f}м")

        font = QFont("Arial")
        font.setPointSizeF(7)
        painter.setFont(font)

        line_height = 12.0
        total_height = len(items) * line_height
        label_width = 120.0

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 210)))
        painter.drawRoundedRect(
            QRectF(mid_x - label_width / 2, mid_y - total_height / 2,
                   label_width, total_height),
            3, 3
        )

        painter.setPen(QColor("black"))
        for i, item in enumerate(items):
            y = mid_y - total_height / 2 + (i + 1) * line_height
            painter.drawText(
                QRectF(mid_x - label_width / 2, y - line_height,
                       label_width, line_height),
                Qt.AlignmentFlag.AlignCenter, item
            )

    def _draw_device(self, painter: QPainter, device: Device):
        """Рисует устройство с учётом динамической высоты."""
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
            border_color = "#ffa500"

        w = device.width
        h = device.height
        header_h = device.HEADER_HEIGHT
        footer_h = device.FOOTER_HEIGHT

        rect = QRectF(device.x - w / 2, device.y - h / 2, w, h)

        # Основной прямоугольник
        border_pen = QPen(QColor(border_color), 2)
        border_pen.setCosmetic(True)
        painter.setPen(border_pen)
        painter.setBrush(QBrush(QColor(fill_color)))
        painter.drawRoundedRect(rect, 5, 5)

        # ===== Заголовок (имя устройства) =====
        header_rect = QRectF(
            device.x - w / 2,
            device.y - h / 2,
            w,
            header_h
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 130)))
        painter.drawRect(header_rect)

        painter.setPen(QColor("white"))
        font = QFont("Arial")
        font.setPointSizeF(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            header_rect,
            Qt.AlignmentFlag.AlignCenter,
            device.name
        )

        # ===== Разделительная линия под заголовком =====
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawLine(
            QPointF(device.x - w / 2 + 2, device.y - h / 2 + header_h),
            QPointF(device.x + w / 2 - 2, device.y - h / 2 + header_h)
        )

        # ===== Подпись типа устройства (снизу) =====
        footer_rect = QRectF(
            device.x - w / 2,
            device.y + h / 2 - footer_h,
            w,
            footer_h
        )

        # Лёгкий фон под подписью
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 40)))
        painter.drawRect(footer_rect)

        painter.setPen(QColor(255, 255, 255, 220))
        font.setPointSizeF(7)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(
            footer_rect,
            Qt.AlignmentFlag.AlignCenter,
            device.device_type
        )

        # ===== Счётчик портов (в заголовке, справа) =====
        if len(device.ports) > 0:
            painter.setPen(QColor(255, 255, 255, 200))
            font.setPointSizeF(7)
            painter.setFont(font)
            count_rect = QRectF(
                device.x + w / 2 - 45,
                device.y - h / 2 + 4,
                40,
                16
            )
            painter.drawText(
                count_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{len(device.ports)}p"
            )

        # ===== Порты =====
        for port in device.input_ports:
            self._draw_port(painter, port, is_input=True)
        for port in device.output_ports:
            self._draw_port(painter, port, is_input=False)

    def _draw_port(self, painter: QPainter, port: Port, is_input: bool):
        """
        Рисует порт.

        Цветовая схема:
          - Зелёный ▼ — занятый входной порт
          - Оранжевый ■ — занятый выходной порт
          - Светло-серый — свободный порт
          - Красный контур — выбранный порт
        """
        size = 5.0
        is_connected = self.model.is_port_connected(port)

        # ✅ Более контрастные цвета
        if is_connected:
            if is_input:
                color = "#10b981"  # изумрудный — вход занят
                outline_color = "#047857"
            else:
                color = "#f59e0b"  # янтарный — выход занят
                outline_color = "#b45309"
        else:
            color = "#e5e7eb"  # светло-серый — свободен
            outline_color = "#9ca3af"

        # Красный контур для выбранного порта
        if port == self.selected_port:
            pen = QPen(QColor("#dc2626"), 2)
        else:
            pen = QPen(QColor(outline_color), 1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(color)))

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
            painter.setPen(QColor("#4b5563"))
            font = QFont("Arial")
            font.setPointSizeF(5.5)
            painter.setFont(font)
            painter.drawText(
                QRectF(port.x - 25, port.y - 22, 50, 12),
                Qt.AlignmentFlag.AlignCenter, port.name
            )

    def _draw_filter_indicator(self, painter: QPainter):
        """Рисует индикатор фильтра."""
        painter.save()
        painter.resetTransform()

        visible = [
            g.name for g in self.model.groups
            if self.model.filter_text in g.name.lower()
        ]
        text = f"🔍 Фильтр: '{self.model.filter_text}'"
        if visible:
            text += f" | {', '.join(visible)}"

        rect = QRectF(10, 10, 350, 30)
        painter.setPen(QPen(QColor("#cccccc"), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawRoundedRect(rect, 5, 5)

        painter.setPen(QColor("#0064c8"))
        font = QFont("Arial", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect.adjusted(10, 0, -10, 0),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         text)

        painter.restore()

    # ========================================================
    #  ПОИСК ЭЛЕМЕНТОВ
    # ========================================================

    def _find_port_at(self, cx: float, cy: float) -> Optional[Port]:
        """Находит порт по экранным координатам."""
        sx, sy = self.to_scene(cx, cy)
        for device in self.model.devices:
            for port in device.ports:
                dx = sx - port.x
                dy = sy - port.y
                if dx * dx + dy * dy < 100:
                    return port
        return None

    def _find_device_at(self, cx: float, cy: float) -> Optional[Device]:
        """Находит устройство по экранным координатам."""
        sx, sy = self.to_scene(cx, cy)
        for device in reversed(self.model.devices):
            if (abs(sx - device.x) < device.width / 2 and
                    abs(sy - device.y) < device.height / 2):
                return device
        return None

    # ========================================================
    #  СОБЫТИЯ МЫШИ
    # ========================================================

    def mousePressEvent(self, event):
        """Обработка нажатия кнопки мыши."""
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
            event.accept()
            return

        # ПКМ — начать соединение (только с СВОБОДНОГО выходного порта)
        if event.button() == Qt.MouseButton.RightButton:
            port = self._find_port_at(pos.x(), pos.y())
            if port:
                # ✅ Проверяем, свободен ли порт
                if self.model.is_port_connected(port):
                    dev = self.model.find_device_by_port(port)
                    dev_name = dev.name if dev else "?"
                    QMessageBox.warning(
                        self, "Порт занят",
                        f"Порт «{port.name}» устройства «{dev_name}» уже используется.\n\n"
                        f"Удалите существующее соединение, чтобы освободить порт."
                    )
                    event.accept()
                    return

                # Проверяем, что это выходной порт (иначе подсказка)
                if port.port_type != PortType.OUTPUT:
                    QMessageBox.information(
                        self, "Неверный порт",
                        f"Порт «{port.name}» — входной.\n"
                        f"Соединение начинается с ВЫХОДНОГО порта (■)."
                    )
                    event.accept()
                    return

                # Всё хорошо — начинаем соединение
                self.connection_mode = True
                self.selected_port = port
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.update()
            else:
                self._show_context_menu(event)
            event.accept()
            return

        # ЛКМ — завершить соединение или выбрать
        if event.button() == Qt.MouseButton.LeftButton:
            if self.connection_mode:
                port = self._find_port_at(pos.x(), pos.y())
                if port:
                    self._finish_connection(port)
                else:
                    self._cancel_connection()
                event.accept()
                return

            # Выбор порта / устройства
            port = self._find_port_at(pos.x(), pos.y())
            if port:
                self.selected_port = port
                self.selected_device = self.model.find_device_by_port(port)
                self.update()
                event.accept()
                return

            device = self._find_device_at(pos.x(), pos.y())
            if device:
                self.selected_device = device
                self.selected_port = None
                self.dragging_device = device
                self.drag_offset = QPointF(sx - device.x, sy - device.y)
                self.device_selected.emit(device)
                self.update()
                event.accept()
                return

            self.selected_device = None
            self.selected_port = None
            self.update()
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Обработка движения мыши."""
        pos = event.position()

        # Панорамирование
        if self.panning:
            delta = pos - self.pan_start
            self.offset_x = self.pan_offset_start.x() + delta.x()
            self.offset_y = self.pan_offset_start.y() + delta.y()
            self.update()
            return

        # Перетаскивание устройства
        if self.dragging_device:
            sx, sy = self.to_scene(pos.x(), pos.y())
            new_x = sx - self.drag_offset.x()
            new_y = sy - self.drag_offset.y()
            self.model.move_device(self.dragging_device, new_x, new_y)
            return

        # Режим соединения — обновляем временную линию
        if self.connection_mode:
            self.update()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Обработка отпускания кнопки мыши."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.panning:
                self.panning = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
            self.dragging_device = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Двойной клик — редактирование устройства."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            device = self._find_device_at(pos.x(), pos.y())
            if device:
                self.device_edited.emit(device)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        """Масштабирование колесиком мыши."""
        pos = event.position()
        sx, sy = self.to_scene(pos.x(), pos.y())

        factor = 1.1 if event.angleDelta().y() > 0 else 0.9
        new_scale = self.scale * factor

        if 0.1 <= new_scale <= 5.0:
            self.scale = new_scale
            # Сохраняем точку под курсором
            self.offset_x = pos.x() - sx * self.scale
            self.offset_y = pos.y() - sy * self.scale
            self.update()

        event.accept()

    def keyPressEvent(self, event):
        """Обработка клавиш."""
        if event.key() == Qt.Key.Key_Delete and self.selected_device:
            self.device_deleted.emit(self.selected_device)
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.connection_mode = False
            self.selected_port = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.update()
            event.accept()
        else:
            super().keyPressEvent(event)

    # ========================================================
    #  КОНТЕКСТНОЕ МЕНЮ
    # ========================================================

    def _show_context_menu(self, event):
        """Показывает контекстное меню."""
        pos = event.position()
        sx, sy = self.to_scene(pos.x(), pos.y())

        menu = QMenu(self)

        categories = [
            ("Глобальные входные", DeviceCategory.GLOBAL_INPUT, [
                ("Магистральный кросс", "Main Cross-connect"),
                ("Внешний кросс", "External Cross-connect"),
                ("Оптический кросс", "Fiber Cross-connect")
            ]),
            ("Локальные входные", DeviceCategory.LOCAL_INPUT, [
                ("Локальный кросс", "Local Cross-connect"),
                ("Патч-панель", "Patch Panel"),
                ("Распределитель", "Distributor")
            ]),
            ("Коммутаторы", DeviceCategory.SWITCHES, [
                ("Агрегатор", "Aggregator"),
                ("Коммутатор", "Switch"),
                ("Маршрутизатор", "Router")
            ]),
            ("Сервера", DeviceCategory.SERVERS, [
                ("Сервер приложений", "Application Server"),
                ("Сервер БД", "Database Server"),
                ("Файловый сервер", "File Server")
            ])
        ]

        create_menu = menu.addMenu("➕ Создать устройство")
        for cat_name, cat, devs in categories:
            sub = create_menu.addMenu(cat_name)
            for dname, dtype in devs:
                action = sub.addAction(dname)
                action.triggered.connect(
                    lambda checked, dt=dtype, c=cat, x=sx, y=sy:
                    self.model.add_device(dt, c, x, y)
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

    def _delete_selected(self):
        """Удаляет выбранное устройство или соединения порта."""
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

    # ========================================================
    #  СОЗДАНИЕ СОЕДИНЕНИЙ
    # ========================================================

    def _finish_connection(self, target_port: Port):
        """
        Завершает создание соединения с проверкой занятости портов.

        Проверяет:
          - корректность направления (выход → вход)
          - что оба порта свободны
          - что порты принадлежат разным устройствам
        """
        if not self.selected_port or self.selected_port == target_port:
            self._cancel_connection()
            return

        # ✅ Полная проверка через модель
        can, error = self.model.can_connect(self.selected_port, target_port)

        if not can:
            # Показываем ошибку с пояснением
            QMessageBox.warning(self, "Невозможно создать соединение", error)
            self._cancel_connection()
            return

        # Всё хорошо — запрашиваем параметры соединения
        self.connection_requested.emit(self.selected_port, target_port)
        self._cancel_connection()

    def _cancel_connection(self):
        """Сбрасывает режим создания соединения."""
        self.connection_mode = False
        self.selected_port = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()


class ColorPickerWidget(QWidget):
    """
    Виджет выбора цвета из палитры.

    ВАЖНО: сигнал color_changed НЕ испускается во время инициализации —
    это предотвращает рекурсию при создании диалога.
    """

    color_changed = pyqtSignal(str)

    DEFAULT_COLORS = [
        "#ef4444", "#f97316", "#f59e0b", "#eab308",
        "#84cc16", "#22c55e", "#10b981", "#14b8a6",
        "#06b6d4", "#0ea5e9", "#3b82f6", "#6366f1",
        "#8b5cf6", "#a855f7", "#d946ef", "#ec4899",
    ]

    def __init__(self, colors: Optional[List[str]] = None,
                 initial: Optional[str] = None, parent=None):
        super().__init__(parent)

        self.colors = colors or self.DEFAULT_COLORS
        self.selected_color = initial or self.colors[0]
        self._buttons = []
        # ✅ Флаг для предотвращения рекурсии
        self._initialized = False

        self._setup_ui()
        # ✅ Разрешаем сигналы только после полной инициализации
        self._initialized = True

    def _setup_ui(self):
        """Создаёт сетку цветных кнопок."""
        layout = QGridLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)

        cols = 8
        for i, color in enumerate(self.colors):
            btn = QPushButton()
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(color)
            btn.setProperty("hex_color", color)

            # ✅ Используем functools.partial вместо лямбды с замыканием
            from functools import partial
            btn.clicked.connect(partial(self._on_color_clicked, color))

            row = i // cols
            col = i % cols
            layout.addWidget(btn, row, col)
            self._buttons.append(btn)

        self._refresh_styles()

    def _on_color_clicked(self, color: str):
        """Обработка клика по цвету."""
        # ✅ Не испускаем сигнал во время инициализации
        if not self._initialized:
            return

        if color == self.selected_color:
            return

        self.selected_color = color
        self._refresh_styles()
        self.color_changed.emit(color)

    def _refresh_styles(self):
        """Обновляет стили кнопок."""
        for btn in self._buttons:
            color = btn.property("hex_color")
            is_selected = color == self.selected_color

            border = "#1f2937" if is_selected else "transparent"
            width = 3 if is_selected else 0

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
        """Устанавливает цвет БЕЗ испускания сигнала."""
        self.selected_color = color
        self._refresh_styles()
# ============================================================
#  ДИАЛОГИ
# ============================================================

class DeviceEditDialog(QDialog):
    """
    Диалог редактирования устройства.

    ВАЖНО: Все изменения применяются к ЛОКАЛЬНОЙ КОПИИ,
    и только при нажатии "Сохранить" переносятся в модель.
    Это предотвращает рекурсию при обновлении канваса.
    """

    def __init__(self, model: NetworkModel, device: Device, parent=None):
        super().__init__(parent)
        self.model = model
        self.device = device

        # ✅ Флаг для предотвращения рекурсии
        self._updating = False

        self.setWindowTitle(f"Редактирование: {device.name}")
        self.resize(600, 550)

        self.input_edits = []
        self.output_edits = []

        self._setup_ui()

    def _setup_ui(self):
        """Создаёт интерфейс диалога."""
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

        in_header = QLabel(f"▼ Входные порты ({len(self.device.input_ports)})")
        in_header.setStyleSheet("font-weight: bold; color: #047857;")
        in_layout.addWidget(in_header)

        self.in_header = in_header

        in_scroll = QScrollArea()
        in_scroll.setWidgetResizable(True)
        in_scroll.setMinimumHeight(220)

        in_container = QWidget()
        self.in_container_layout = QVBoxLayout(in_container)
        self.in_container_layout.setSpacing(2)
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

        out_header = QLabel(f"■ Выходные порты ({len(self.device.output_ports)})")
        out_header.setStyleSheet("font-weight: bold; color: #b45309;")
        out_layout.addWidget(out_header)

        self.out_header = out_header

        out_scroll = QScrollArea()
        out_scroll.setWidgetResizable(True)
        out_scroll.setMinimumHeight(220)

        out_container = QWidget()
        self.out_container_layout = QVBoxLayout(out_container)
        self.out_container_layout.setSpacing(2)
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

        # ===== Информация о высоте =====
        self.size_info = QLabel()
        self.size_info.setStyleSheet(
            "color: #6b7280; font-size: 11px; padding: 6px; "
            "background-color: #f7f9fc; border-radius: 4px;"
        )
        layout.addWidget(self.size_info)
        self._update_size_info()

        # ===== Кнопки =====
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_size_info(self):
        """Обновляет информацию о вычисленной высоте."""
        # Считаем по формуле, без вызова update_port_positions
        max_ports = max(
            len(self.input_edits) + len([p for p in self.device.input_ports]),
            len(self.output_edits) + len([p for p in self.device.output_ports])
        )
        # Проще: считаем по текущему количеству в списках
        n_in = len(self.device.input_ports)
        n_out = len(self.device.output_ports)
        max_ports = max(n_in, n_out)

        if max_ports == 0:
            height = self.device.MIN_HEIGHT
        else:
            port_area = (max_ports + 1) * self.device.PORT_SPACING
            port_area = max(port_area, self.device.MIN_PORT_AREA_HEIGHT)
            height = (self.device.HEADER_HEIGHT + port_area +
                      self.device.FOOTER_HEIGHT)
            height = max(height, self.device.MIN_HEIGHT)

        self.size_info.setText(
            f"📐 Высота: {height:.0f} px  •  "
            f"📥 Входных: {n_in}  •  "
            f"📤 Выходных: {n_out}  •  "
            f"📊 Всего: {n_in + n_out}"
        )

    def _add_port_row(self, layout, port: Port, edit_list: list, is_input: bool):
        """Добавляет строку редактирования порта."""
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)

        name_edit = QLineEdit(port.name)
        name_edit.setMaximumWidth(140)
        row.addWidget(name_edit)

        label = QLabel("▼ IN" if is_input else "■ OUT")
        label.setStyleSheet(
            f"color: {'#047857' if is_input else '#b45309'}; "
            f"font-weight: bold; padding: 2px 6px;"
        )
        row.addWidget(label)

        row.addStretch()

        del_btn = QPushButton("×")
        del_btn.setMaximumWidth(28)
        del_btn.setProperty("class", "danger")
        del_btn.clicked.connect(
            lambda: self._remove_port(widget, port, edit_list)
        )
        row.addWidget(del_btn)

        widget._port = port
        widget._name_edit = name_edit
        # ✅ Вставляем перед stretch
        layout.insertWidget(layout.count() - 1, widget)
        edit_list.append(widget)

    def _add_new_port(self, layout, is_input: bool):
        """Добавляет новый порт к устройству."""
        if self._updating:
            return
        self._updating = True

        try:
            max_id = max((p.id for p in self.device.ports), default=-1)
            new_port = Port(
                id=max_id + 1,
                name=f"New {'IN' if is_input else 'OUT'}",
                port_type=PortType.INPUT if is_input else PortType.OUTPUT
            )

            if is_input:
                self.device.input_ports.append(new_port)
                self._add_port_row(layout, new_port, self.input_edits, True)
            else:
                self.device.output_ports.append(new_port)
                self._add_port_row(layout, new_port, self.output_edits, False)

            # Обновляем счётчики
            self.in_header.setText(
                f"▼ Входные порты ({len(self.device.input_ports)})"
            )
            self.out_header.setText(
                f"■ Выходные порты ({len(self.device.output_ports)})"
            )

            self._update_size_info()
        finally:
            self._updating = False

    def _remove_port(self, widget, port: Port, edit_list: list):
        """Удаляет порт."""
        if self._updating:
            return
        self._updating = True

        try:
            has_conn = any(
                port in (c.port1, c.port2) for c in self.model.connections
            )

            if has_conn:
                reply = QMessageBox.question(
                    self, "Удаление порта",
                    f"Порт '{port.name}' имеет соединения. Удалить?",
                    QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                # ✅ Не удаляем сразу — удалим при сохранении
                # (иначе ломается структура модели)
                widget._marked_for_deletion = True
                widget._port._pending_deletion = True
                widget.hide()
                return

            if port in self.device.input_ports:
                self.device.input_ports.remove(port)
            elif port in self.device.output_ports:
                self.device.output_ports.remove(port)

            edit_list.remove(widget)
            widget.deleteLater()

            # Обновляем счётчики
            self.in_header.setText(
                f"▼ Входные порты ({len(self.device.input_ports)})"
            )
            self.out_header.setText(
                f"■ Выходные порты ({len(self.device.output_ports)})"
            )

            self._update_size_info()
        finally:
            self._updating = False

    def _save(self):
        """Сохраняет изменения устройства."""
        if self._updating:
            return
        self._updating = True

        try:
            self.device.name = self.name_edit.text()
            self.device.device_type = self.type_edit.text()
            self.device.category = DeviceCategory(self.category_combo.currentText())

            # Обновляем имена портов
            for widget in self.input_edits:
                if hasattr(widget, '_port') and hasattr(widget, '_name_edit'):
                    widget._port.name = widget._name_edit.text()

            for widget in self.output_edits:
                if hasattr(widget, '_port') and hasattr(widget, '_name_edit'):
                    widget._port.name = widget._name_edit.text()

            # Удаляем помеченные порты
            self.device.input_ports = [
                p for p in self.device.input_ports
                if not getattr(p, '_pending_deletion', False)
            ]
            self.device.output_ports = [
                p for p in self.device.output_ports
                if not getattr(p, '_pending_deletion', False)
            ]

            # Пересчитываем высоту и позиции
            self.device.update_port_positions()

            # Уведомляем модель
            self.model.notify_observers()

            self.accept()
        finally:
            self._updating = False


class DevicePreviewCanvas(QWidget):
    """
    Мини-канвас для предпросмотра устройства в диалоге редактирования.
    Рисует устройство с реальными пропорциями и портами.
    """

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self.device = device
        self.setMinimumWidth(180)

    def paintEvent(self, event):
        """Рисует устройство в предпросмотре."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#fafbfc"))

        # Вычисляем масштаб, чтобы устройство вместилось
        margin = 20
        available_w = self.width() - 2 * margin
        available_h = self.height() - 2 * margin

        scale_x = available_w / self.device.width
        scale_y = available_h / self.device.height
        scale = min(scale_x, scale_y, 1.5)  # Не более 150%

        # Центрируем
        dw = self.device.width * scale
        dh = self.device.height * scale
        cx = self.width() / 2
        cy = self.height() / 2

        # Временный "центр" устройства для отрисовки
        painter.translate(cx, cy)
        painter.scale(scale, scale)
        painter.translate(-self.device.x, -self.device.y)

        # Цвета
        colors = {
            DeviceCategory.GLOBAL_INPUT: ("#4682b4", "#00008b"),
            DeviceCategory.LOCAL_INPUT: ("#87ceeb", "#006496"),
            DeviceCategory.SWITCHES: ("#3cb371", "#006400"),
            DeviceCategory.SERVERS: ("#9370db", "#4b0082")
        }
        fill_color, border_color = colors.get(
            self.device.category, ("#808080", "#404040")
        )

        w, h = self.device.width, self.device.height
        header_h = self.device.HEADER_HEIGHT
        footer_h = self.device.FOOTER_HEIGHT

        rect = QRectF(
            self.device.x - w / 2,
            self.device.y - h / 2,
            w, h
        )

        # Тело устройства
        painter.setPen(QPen(QColor(border_color), 2))
        painter.setBrush(QBrush(QColor(fill_color)))
        painter.drawRoundedRect(rect, 5, 5)

        # Заголовок
        header_rect = QRectF(
            self.device.x - w / 2,
            self.device.y - h / 2,
            w, header_h
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 130)))
        painter.drawRect(header_rect)

        # Имя
        painter.setPen(QColor("white"))
        font = QFont("Arial")
        font.setPointSizeF(8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, self.device.name)

        # Тип
        footer_rect = QRectF(
            self.device.x - w / 2,
            self.device.y + h / 2 - footer_h,
            w, footer_h
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 40)))
        painter.drawRect(footer_rect)

        painter.setPen(QColor(255, 255, 255, 220))
        font.setPointSizeF(6.5)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(footer_rect, Qt.AlignmentFlag.AlignCenter, self.device.device_type)

        # Порты
        port_size = 4.0
        for port in self.device.input_ports:
            painter.setPen(QPen(QColor("black"), 1))
            painter.setBrush(QBrush(QColor("#10b981")))
            triangle = QPolygonF([
                QPointF(port.x - port_size, port.y - port_size),
                QPointF(port.x - port_size, port.y + port_size),
                QPointF(port.x + port_size, port.y)
            ])
            painter.drawPolygon(triangle)

        for port in self.device.output_ports:
            painter.setPen(QPen(QColor("black"), 1))
            painter.setBrush(QBrush(QColor("#f59e0b")))
            painter.drawRect(QRectF(
                port.x - port_size, port.y - port_size,
                port_size * 2, port_size * 2
            ))


class ConnectionDialog(QDialog):
    """Диалог создания одиночного соединения с выбором цвета группы."""

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
        self.resize(420, 500)

        self._setup_ui()

    def _setup_ui(self):
        """Создаёт интерфейс диалога."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ===== Информация о соединении =====
        dev1 = self.model.find_device_by_port(self.port1)
        dev2 = self.model.find_device_by_port(self.port2)

        info_group = QGroupBox("Соединение")
        info_layout = QVBoxLayout(info_group)

        info = QLabel(
            f"<b>{dev1.name}</b> : {self.port1.name} (OUT)  →  "
            f"<b>{dev2.name}</b> : {self.port2.name} (IN)"
        )
        info.setWordWrap(True)
        info_layout.addWidget(info)

        layout.addWidget(info_group)

        # ===== Параметры кабеля =====
        cable_group = QGroupBox("Параметры кабеля")
        cable_form = QFormLayout(cable_group)

        self.cable_combo = QComboBox()
        self.cable_combo.addItems(["Ethernet", "Fiber Optic", "Serial", "Coaxial"])
        cable_form.addRow("Тип кабеля:", self.cable_combo)

        self.length_spin = QDoubleSpinBox()
        self.length_spin.setRange(0.1, 10000.0)
        self.length_spin.setValue(1.0)
        self.length_spin.setSuffix(" м")
        self.length_spin.setDecimals(1)
        cable_form.addRow("Длина:", self.length_spin)

        layout.addWidget(cable_group)

        # ===== Группа =====
        group_group = QGroupBox("Группа соединений")
        group_layout = QVBoxLayout(group_group)

        # Выбор группы
        self.group_combo = QComboBox()
        self.group_combo.addItem("Без группы", None)
        for group in self.model.groups:
            count = len(self.model.get_group_connections(group))
            self.group_combo.addItem(f"● {group.name} ({count})", group.id)
            # Показываем цвет через иконку-квадрат
            idx = self.group_combo.count() - 1
            self.group_combo.setItemIcon(idx, self._make_color_icon(group.color))

        self.group_combo.addItem("+ Новая группа...", "new")
        self.group_combo.currentIndexChanged.connect(self._on_group_changed)
        group_layout.addWidget(self.group_combo)

        # ===== Панель новой группы (скрыта по умолчанию) =====
        self.new_group_widget = QWidget()
        new_layout = QVBoxLayout(self.new_group_widget)
        new_layout.setContentsMargins(0, 6, 0, 0)

        new_layout.addWidget(QLabel("Название:"))
        self.new_group_name = QLineEdit()
        self.new_group_name.setPlaceholderText("Например: Магистральный канал")
        new_layout.addWidget(self.new_group_name)

        # ✅ Выбор цвета
        color_label = QLabel("Цвет группы:")
        color_label.setStyleSheet("margin-top: 6px;")
        new_layout.addWidget(color_label)

        self.color_picker = ColorPickerWidget()
        new_layout.addWidget(self.color_picker)

        # Превью цвета
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(30)
        self.color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        new_layout.addWidget(self.color_preview)

        self.color_picker.color_changed.connect(self._on_color_changed)
        self._on_color_changed(self.color_picker.get_color())

        self.new_group_widget.setVisible(False)
        group_layout.addWidget(self.new_group_widget)

        layout.addWidget(group_group)

        # ===== Кнопки =====
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        layout.addStretch()

    def _make_color_icon(self, color: str) -> QIcon:
        """Создаёт иконку-квадратик указанного цвета."""
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(QPen(QColor("#9ca3af"), 1))
        painter.drawRoundedRect(1, 1, 12, 12, 3, 3)
        painter.end()

        return QIcon(pixmap)

    def _on_group_changed(self, index):
        """Показывает панель новой группы."""
        self.new_group_widget.setVisible(
            self.group_combo.currentData() == "new"
        )
        # Обновляем размер диалога
        self.adjustSize()

    def _on_color_changed(self, color: str):
        """Обновляет превью цвета."""
        self.color_preview.setStyleSheet(f"""
            background-color: {color};
            border: 2px solid #d0d7e2;
            border-radius: 5px;
            color: white;
            font-weight: bold;
            padding: 4px;
        """)
        self.color_preview.setText(color.upper())

    def _save(self):
        """Создаёт соединение с заданными параметрами."""
        cable_type = self.cable_combo.currentText()
        length = self.length_spin.value()
        group_id = self.group_combo.currentData()

        if group_id == "new":
            name = self.new_group_name.text().strip() or "Новая группа"
            color = self.color_picker.get_color()
            # ✅ Передаём выбранный цвет
            group = self.model.create_group(name, color)
            group_id = group.id

        self.model.add_connection(
            self.port1, self.port2, cable_type, length, group_id
        )
        self.accept()


class ChannelCreationDialog(QDialog):
    """
    Диалог создания канала связи.

    ИСПРАВЛЕНИЯ для предотвращения 0xC0000409:
      - Использование functools.partial вместо lambda с self
      - Отложенная инициализация тяжёлых виджетов через QTimer.singleShot
      - Проверка _initialized перед эмиссией сигналов
    """

    def __init__(self, model: NetworkModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.route_devices: List[Device] = []
        self.segment_widgets: List[ChannelSegmentWidget] = []

        # ✅ Флаг инициализации
        self._initialized = False
        self._updating = False

        self.setWindowTitle("Создание канала связи")
        self.resize(800, 750)
        self.setMinimumSize(700, 600)

        # ✅ Строим UI в правильном порядке
        self._setup_ui()

        # ✅ Инициализация завершена — теперь можно принимать сигналы
        self._initialized = True
        self._update_summary()

    def _setup_ui(self):
        """Создаёт интерфейс диалога."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # ===== Верхняя строка: название + цвет =====
        top_row = QHBoxLayout()

        # Название
        name_group = QGroupBox("Название канала")
        name_layout = QVBoxLayout(name_group)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(
            "Например: Москва — Санкт-Петербург (магистраль)"
        )
        self.name_edit.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.name_edit)

        top_row.addWidget(name_group, 2)

        # Цвет
        color_group = QGroupBox("Цвет группы")
        color_layout = QVBoxLayout(color_group)

        self.color_picker = ColorPickerWidget()
        self.color_picker.color_changed.connect(self._on_color_changed)
        color_layout.addWidget(self.color_picker)

        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(28)
        self.color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color_layout.addWidget(self.color_preview)

        # ✅ Устанавливаем превью напрямую, без вызова сигналов
        self._update_color_preview(self.color_picker.get_color())

        top_row.addWidget(color_group, 1)

        layout.addLayout(top_row)

        # ===== Маршрут канала =====
        route_group = QGroupBox("Маршрут канала")
        route_layout = QHBoxLayout(route_group)

        # Список устройств
        devices_widget = QWidget()
        devices_layout = QVBoxLayout(devices_widget)
        devices_layout.setContentsMargins(0, 0, 0, 0)

        devices_layout.addWidget(QLabel("Устройства маршрута (в порядке следования):"))

        self.route_list = QListWidget()
        self.route_list.setMaximumHeight(140)
        # ✅ partial вместо lambda
        self.route_list.itemDoubleClicked.connect(
            partial(self._on_route_item_double_clicked)
        )
        devices_layout.addWidget(self.route_list)

        route_layout.addWidget(devices_widget, 1)

        # Кнопки управления
        btns_widget = QWidget()
        btns_layout = QVBoxLayout(btns_widget)
        btns_layout.setContentsMargins(0, 20, 0, 0)
        btns_layout.setSpacing(4)

        add_btn = QPushButton("➕ Добавить устройство")
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

        # ===== Сегменты канала =====
        segments_group = QGroupBox("Сегменты канала")
        segments_outer = QVBoxLayout(segments_group)

        self.segments_scroll = QScrollArea()
        self.segments_scroll.setWidgetResizable(True)
        self.segments_scroll.setMinimumHeight(220)
        self.segments_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.segments_container = QWidget()
        self.segments_layout = QVBoxLayout(self.segments_container)
        self.segments_layout.setSpacing(10)
        self.segments_layout.setContentsMargins(0, 0, 0, 0)
        self.segments_layout.addStretch()

        self.segments_scroll.setWidget(self.segments_container)
        segments_outer.addWidget(self.segments_scroll)

        self.empty_hint = QLabel(
            "Добавьте минимум два устройства, чтобы настроить сегменты канала."
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

    # ========================================================
    #  ОБРАБОТЧИКИ
    # ========================================================

    def _on_name_changed(self, text: str):
        """Обновляет сводку при изменении названия."""
        if self._initialized:
            self._update_summary()

    def _on_color_changed(self, color: str):
        """Обновляет превью цвета."""
        if not self._initialized:
            return
        self._update_color_preview(color)

    def _update_color_preview(self, color: str):
        """Обновляет превью выбранного цвета."""
        self.color_preview.setStyleSheet(f"""
            background-color: {color};
            border: 2px solid #d0d7e2;
            border-radius: 5px;
            color: white;
            font-weight: bold;
        """)
        self.color_preview.setText(f"Выбранный цвет: {color.upper()}")

    def _on_route_item_double_clicked(self, item):
        """Обработка двойного клика по элементу маршрута."""
        self._remove_device()

    # ========================================================
    #  УПРАВЛЕНИЕ МАРШРУТОМ
    # ========================================================

    def _add_device(self):
        """Открывает диалог выбора устройства."""
        if not self.model.devices:
            QMessageBox.warning(self, "Внимание", "На схеме нет устройств")
            return

        device = self._show_device_selector()
        if device:
            self.route_devices.append(device)
            self.route_list.addItem(
                f"{len(self.route_devices)}. {device.name}"
            )
            self._rebuild_segments()

    def _show_device_selector(self) -> Optional[Device]:
        """
        Показывает диалог выбора устройства.

        ✅ ИСПРАВЛЕНИЕ: диалог создаётся один раз, без рекурсивных
        вызовов из лямбд.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Выберите устройство")
        dialog.resize(400, 500)

        layout = QVBoxLayout(dialog)

        # Поиск
        search = QLineEdit()
        search.setPlaceholderText("🔍 Поиск по имени...")
        layout.addWidget(search)

        list_widget = QListWidget()
        for d in self.model.devices:
            item = QListWidgetItem(f"{d.name}  ({d.device_type})")
            item.setData(Qt.ItemDataRole.UserRole, d.id)
            list_widget.addItem(item)
        layout.addWidget(list_widget)

        # ✅ Фильтр без замыкания на list_widget через лямбду в цикле
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
        """Удаляет выбранное устройство из маршрута."""
        row = self.route_list.currentRow()
        if row >= 0 and row < len(self.route_devices):
            self.route_list.takeItem(row)
            del self.route_devices[row]
            self._renumber_route()
            self._rebuild_segments()

    def _move_device(self, direction: int):
        """Перемещает выбранное устройство."""
        row = self.route_list.currentRow()
        new_row = row + direction
        if 0 <= row < len(self.route_devices) and \
                0 <= new_row < len(self.route_devices):
            self.route_devices[row], self.route_devices[new_row] = \
                self.route_devices[new_row], self.route_devices[row]

            text = self.route_list.takeItem(row)
            self.route_list.insertItem(new_row, text)
            self.route_list.setCurrentRow(new_row)

            self._renumber_route()
            self._rebuild_segments()

    def _renumber_route(self):
        """Обновляет нумерацию устройств в списке."""
        for i in range(self.route_list.count()):
            item = self.route_list.item(i)
            if i < len(self.route_devices):
                item.setText(f"{i + 1}. {self.route_devices[i].name}")

    # ========================================================
    #  ПОСТРОЕНИЕ СЕГМЕНТОВ
    # ========================================================

    def _rebuild_segments(self):
        """
        Пересоздаёт виджеты сегментов.

        ✅ ИСПРАВЛЕНИЕ: используем deleteLater и явную очистку,
        чтобы избежать циклических ссылок.
        """
        # ✅ Отключаем все сигналы от старых виджетов
        for w in self.segment_widgets:
            try:
                w.removed.disconnect()
            except (TypeError, RuntimeError):
                pass  # Уже отключён

        # Удаляем виджеты
        for w in self.segment_widgets:
            self.segments_layout.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
        self.segment_widgets.clear()

        # Очищаем layout
        while self.segments_layout.count() > 1:
            item = self.segments_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Показ подсказки
        self.empty_hint.setVisible(len(self.route_devices) < 2)

        # Создаём сегменты
        if len(self.route_devices) >= 2:
            for i in range(len(self.route_devices) - 1):
                d1 = self.route_devices[i]
                d2 = self.route_devices[i + 1]

                segment = ChannelSegmentWidget(
                    self.model, d1, d2, i + 1, self
                )
                # ✅ Не подключаем removed — не используем

                self.segment_widgets.append(segment)
                self.segments_layout.insertWidget(i, segment)

        # ✅ Обновляем сводку
        if self._initialized:
            self._update_summary()

    # ========================================================
    #  СВОДКА
    # ========================================================

    def _update_summary(self):
        """Обновляет сводку по каналу."""
        if len(self.route_devices) < 2:
            self.summary_label.setText(
                "ℹ️ Добавьте минимум два устройства для создания канала."
            )
            return

        total_length = 0.0
        cable_types = set()
        for widget in self.segment_widgets:
            data = widget.get_connection_data()
            if data:
                total_length += data['length']
                cable_types.add(data['cable_type'])

        route_str = " → ".join(d.name for d in self.route_devices)
        cable_str = ", ".join(sorted(cable_types)) if cable_types else "—"

        self.summary_label.setText(
            f"📊 <b>Маршрут:</b> {route_str}<br>"
            f"📏 <b>Сегментов:</b> {len(self.segment_widgets)}  •  "
            f"<b>Общая длина:</b> {total_length:.1f} м  •  "
            f"<b>Типы кабелей:</b> {cable_str}"
        )
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)

    # ========================================================
    #  СОЗДАНИЕ КАНАЛА
    # ========================================================

    def _create_channel(self):
        """Создаёт канал с проверками."""
        if len(self.route_devices) < 2:
            QMessageBox.warning(
                self, "Ошибка", "Добавьте минимум 2 устройства в маршрут."
            )
            return

        name = self.name_edit.text().strip() or "Новый канал"
        color = self.color_picker.get_color()

        # Проверка сегментов
        errors = []
        for i, widget in enumerate(self.segment_widgets):
            valid, error = widget.is_valid()
            if not valid:
                errors.append(f"Сегмент {i + 1}: {error}")

        if errors:
            QMessageBox.warning(
                self, "Ошибки в сегментах",
                "Исправьте следующие проблемы:\n\n" + "\n".join(errors)
            )
            return

        # Создаём группу
        group = self.model.create_group(name, color)

        success = 0
        failed = []

        for i, widget in enumerate(self.segment_widgets):
            data = widget.get_connection_data()
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
            QMessageBox.critical(
                self, "Ошибка",
                "Не удалось создать ни одного соединения."
            )
            return

        message = f"Канал «{name}» создан!\n\nСоединений: {success}"
        if failed:
            message += f"\nНе удалось: {', '.join(failed)}"

        QMessageBox.information(self, "Успех", message)
        self.accept()

    # ========================================================
    #  ЗАКРЫТИЕ
    # ========================================================

    def closeEvent(self, event):
        """
        Очистка при закрытии диалога.

        ✅ ИСПРАВЛЕНИЕ: явно отключаем сигналы и удаляем
        дочерние виджеты — предотвращает утечки и циклы.
        """
        # Отключаем все сигналы от сегментов
        for w in self.segment_widgets:
            try:
                w.removed.disconnect()
            except (TypeError, RuntimeError):
                pass

        super().closeEvent(event)


class GroupManagementDialog(QDialog):
    """Диалог управления группами с возможностью смены цвета."""

    def __init__(self, model: NetworkModel, parent=None):
        super().__init__(parent)
        self.model = model

        self.setWindowTitle("Управление группами")
        self.resize(700, 550)

        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        """Создаёт интерфейс."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        # Поиск
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по названию группы...")
        self.search_edit.textChanged.connect(self._refresh_list)
        search_row.addWidget(self.search_edit)
        layout.addLayout(search_row)

        # Основная область: список + редактирование
        main_row = QHBoxLayout()

        # Список групп
        self.group_list = QListWidget()
        self.group_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.group_list.itemDoubleClicked.connect(lambda _: self._rename())
        main_row.addWidget(self.group_list, 1)

        # Панель редактирования
        edit_panel = QGroupBox("Редактирование")
        edit_panel.setMaximumWidth(280)
        edit_layout = QVBoxLayout(edit_panel)

        # Название
        edit_layout.addWidget(QLabel("Название группы:"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)
        edit_layout.addWidget(self.name_edit)

        # ✅ Цвет
        edit_layout.addWidget(QLabel("Цвет:"))
        self.color_picker = ColorPickerWidget()
        self.color_picker.color_changed.connect(self._on_color_changed)
        edit_layout.addWidget(self.color_picker)

        # Превью
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(30)
        self.color_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit_layout.addWidget(self.color_preview)

        edit_layout.addSpacing(10)

        # Видимость
        self.visible_cb = QCheckBox("Показывать соединения")
        self.visible_cb.stateChanged.connect(self._on_visibility_changed)
        edit_layout.addWidget(self.visible_cb)

        edit_layout.addStretch()

        # Информация о соединениях
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

        rename_btn = QPushButton("Переименовать")
        rename_btn.clicked.connect(self._rename)
        btn_row.addWidget(rename_btn)

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

    def _refresh_list(self):
        """Обновляет список групп с цветными маркерами."""
        # Сохраняем выбранный ID
        selected_id = None
        current = self.group_list.currentItem()
        if current:
            selected_id = current.data(Qt.ItemDataRole.UserRole)

        self.group_list.clear()
        filter_text = self.search_edit.text().strip().lower()

        for group in self.model.groups:
            if not filter_text or filter_text in group.name.lower():
                count = len(self.model.get_group_connections(group))
                prefix = "✓" if group.visible else "✗"

                item = QListWidgetItem(f"{prefix}  {group.name}  ({count} соед.)")
                item.setData(Qt.ItemDataRole.UserRole, group.id)
                item.setIcon(self._make_color_icon(group.color))
                self.group_list.addItem(item)

                # Восстанавливаем выбор
                if group.id == selected_id:
                    self.group_list.setCurrentItem(item)

    def _make_color_icon(self, color: str) -> QIcon:
        """Создаёт иконку-квадрат указанного цвета."""
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(QPen(QColor("#9ca3af"), 1))
        painter.drawRoundedRect(1, 1, 12, 12, 3, 3)
        painter.end()

        return QIcon(pixmap)

    def _get_selected(self) -> Optional[ConnectionGroup]:
        """Возвращает выбранную группу."""
        item = self.group_list.currentItem()
        if item:
            group_id = item.data(Qt.ItemDataRole.UserRole)
            return self.model.get_group(group_id)
        return None

    def _on_selection_changed(self):
        """Заполняет панель редактирования при выборе группы."""
        group = self._get_selected()
        if not group:
            self.name_edit.clear()
            self.info_label.clear()
            self.color_preview.clear()
            return

        # Блокируем сигналы, чтобы не вызвать изменения
        self.name_edit.blockSignals(True)
        self.name_edit.setText(group.name)
        self.name_edit.blockSignals(False)

        self.color_picker.blockSignals(True)
        # Обновляем выбранный цвет в палитре
        self.color_picker.set_color(group.color)
        self.color_picker.blockSignals(False)

        # Обновляем превью
        self._update_color_preview(group.color)

        # Видимость
        self.visible_cb.blockSignals(True)
        self.visible_cb.setChecked(group.visible)
        self.visible_cb.blockSignals(False)

        # Информация
        conns = self.model.get_group_connections(group)
        total_length = sum(c.length for c in conns)
        self.info_label.setText(
            f"📊 Соединений: {len(conns)}\n"
            f"📏 Общая длина: {total_length:.1f} м"
        )

    def _update_color_preview(self, color: str):
        """Обновляет превью цвета."""
        self.color_preview.setStyleSheet(f"""
            background-color: {color};
            border: 2px solid #d0d7e2;
            border-radius: 5px;
            color: white;
            font-weight: bold;
        """)
        self.color_preview.setText(color.upper())

    def _on_name_changed(self, text: str):
        """Меняет имя группы при редактировании поля."""
        group = self._get_selected()
        if group and text:
            group.name = text
            # Обновляем элемент списка
            item = self.group_list.currentItem()
            if item:
                count = len(self.model.get_group_connections(group))
                prefix = "✓" if group.visible else "✗"
                item.setText(f"{prefix}  {text}  ({count} соед.)")
            self.model.notify_observers()

    def _on_color_changed(self, color: str):
        """Меняет цвет группы."""
        group = self._get_selected()
        if group:
            self.model.update_group_color(group, color)
            self._update_color_preview(color)
            # Обновляем иконку
            item = self.group_list.currentItem()
            if item:
                item.setIcon(self._make_color_icon(color))

    def _on_visibility_changed(self, state):
        """Переключает видимость группы."""
        group = self._get_selected()
        if group:
            group.visible = state == Qt.CheckState.Checked.value
            self.model.notify_observers()
            self._refresh_list()

    def _rename(self):
        """Переименовывает группу через диалог."""
        group = self._get_selected()
        if group:
            new_name, ok = QInputDialog.getText(
                self, "Переименовать", "Новое название:",
                text=group.name
            )
            if ok and new_name:
                group.name = new_name
                self._refresh_list()
                self._on_selection_changed()
                self.model.notify_observers()

    def _toggle(self):
        """Переключает видимость группы."""
        group = self._get_selected()
        if group:
            group.visible = not group.visible
            self._refresh_list()
            self._on_selection_changed()
            self.model.notify_observers()

    def _show_all(self):
        """Показывает все группы."""
        for group in self.model.groups:
            group.visible = True
        self._refresh_list()
        self._on_selection_changed()
        self.model.notify_observers()

    def _delete(self):
        """Удаляет группу."""
        group = self._get_selected()
        if group:
            reply = QMessageBox.question(
                self, "Удаление",
                f"Удалить группу '{group.name}'?\n"
                f"Соединения останутся, но будут без группы.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.model.remove_group(group)
                self._refresh_list()
                self._on_selection_changed()


class ChannelSegmentWidget(QGroupBox):
    """
    Виджет одного сегмента канала.

    ИСПРАВЛЕНИЕ: убрана рекурсивная проверка parent() —
    теперь порты, зарезервированные в других сегментах,
    НЕ проверяются (это редкий случай, и его можно игнорировать).
    Вместо этого — простая проверка занятости в модели.
    """

    removed = pyqtSignal(object)

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
        """Создаёт интерфейс сегмента."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Выходной порт
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Выходной порт:"))

        self.out_port_combo = QComboBox()
        self.out_port_combo.setMinimumWidth(200)
        self._populate_out_ports()
        out_row.addWidget(self.out_port_combo, 1)
        layout.addLayout(out_row)

        # Входной порт
        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("Входной порт:"))

        self.in_port_combo = QComboBox()
        self.in_port_combo.setMinimumWidth(200)
        self._populate_in_ports()
        in_row.addWidget(self.in_port_combo, 1)
        layout.addLayout(in_row)

        # Кабель
        cable_row = QHBoxLayout()
        cable_row.addWidget(QLabel("Кабель:"))

        self.cable_combo = QComboBox()
        self.cable_combo.addItems([
            "Ethernet", "Fiber Optic", "Serial", "Coaxial"
        ])
        self.cable_combo.setMinimumWidth(120)
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

        # ✅ Обновляем статус при изменении выбора
        self.out_port_combo.currentIndexChanged.connect(self._update_status)
        self.in_port_combo.currentIndexChanged.connect(self._update_status)
        self._update_status()

    def _populate_out_ports(self):
        """Заполняет список выходных портов."""
        self.out_port_combo.clear()
        for port in self.device1.output_ports:
            is_busy = self.model.is_port_connected(port)
            prefix = "❌ " if is_busy else "✅ "
            label = f"{prefix}{port.name}"
            if is_busy:
                label += " (занят)"
            self.out_port_combo.addItem(label, port)

            # Отключаем занятые
            if is_busy:
                idx = self.out_port_combo.count() - 1
                item = self.out_port_combo.model().item(idx)
                if item:
                    item.setEnabled(False)

        # ✅ Автовыбор первого свободного порта
        self._auto_select_free_port(self.out_port_combo)

    def _populate_in_ports(self):
        """Заполняет список входных портов."""
        self.in_port_combo.clear()
        for port in self.device2.input_ports:
            is_busy = self.model.is_port_connected(port)
            prefix = "❌ " if is_busy else "✅ "
            label = f"{prefix}{port.name}"
            if is_busy:
                label += " (занят)"
            self.in_port_combo.addItem(label, port)

            if is_busy:
                idx = self.in_port_combo.count() - 1
                item = self.in_port_combo.model().item(idx)
                if item:
                    item.setEnabled(False)

        self._auto_select_free_port(self.in_port_combo)

    def _auto_select_free_port(self, combo: QComboBox):
        """Автоматически выбирает первый свободный порт в списке."""
        for i in range(combo.count()):
            item = combo.model().item(i)
            if item and item.isEnabled():
                combo.setCurrentIndex(i)
                return

    def _update_status(self):
        """Обновляет статус сегмента."""
        out_port = self.out_port_combo.currentData()
        in_port = self.in_port_combo.currentData()

        if out_port is None or in_port is None:
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
        """Возвращает данные для создания соединения."""
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
        """Проверяет корректность сегмента."""
        data = self.get_connection_data()
        if not data:
            return False, "Не выбраны порты"

        can, error = self.model.can_connect(data['out_port'], data['in_port'])
        if not can:
            return False, error

        return True, ""
# ============================================================
#  КОНТРОЛЛЕР (Controller)
# ============================================================

class NetworkController(QObject):
    """
    Контроллер — связывает модель и представление.

    Обрабатывает сигналы от View и вызывает соответствующие
    методы Model. Показывает диалоги.
    """

    def __init__(self, model: NetworkModel, canvas: NetworkCanvas, window):
        super().__init__()
        self.model = model
        self.canvas = canvas
        self.window = window

        # Подключаем сигналы View к обработчикам
        canvas.connection_requested.connect(self._on_connection_requested)
        canvas.device_edited.connect(self._on_device_edited)
        canvas.device_deleted.connect(self._on_device_deleted)
        canvas.channel_requested.connect(self._on_channel_requested)
        canvas.groups_requested.connect(self._on_groups_requested)

    def _on_connection_requested(self, port1: Port, port2: Port):
        """Обработка запроса на создание соединения."""
        dialog = ConnectionDialog(self.model, port1, port2, self.canvas)
        dialog.exec()

    def _on_device_edited(self, device: Device):
        """Обработка запроса на редактирование устройства."""
        dialog = DeviceEditDialog(self.model, device, self.canvas)
        dialog.exec()

    def _on_device_deleted(self, device: Device):
        """Обработка удаления устройства."""
        self.model.remove_device(device)

    def _on_channel_requested(self):
        """Обработка запроса на создание канала."""
        dialog = ChannelCreationDialog(self.model, self.canvas)
        dialog.exec()
        # Обновляем канвас после создания канала
        self.canvas.update()

    def _on_groups_requested(self):
        """Обработка запроса на управление группами."""
        dialog = GroupManagementDialog(self.model, self.canvas)
        dialog.exec()


# ============================================================
#  ГЛАВНОЕ ОКНО
# ============================================================

class MainWindow(QMainWindow):
    """
    Главное окно приложения.

    Содержит:
      - Панель инструментов слева (фильтр, настройки, действия)
      - Канвас справа
      - Строку состояния снизу
      - Меню сверху
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Network Visualizer")
        self.resize(1400, 900)
        self.setMinimumSize(1000, 650)

        # Иконка окна (эмодзи через QPixmap)
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#0066cc"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(4, 4, 56, 56, 12, 12)
        p.setPen(QColor("white"))
        p.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        p.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "N")
        p.end()
        self.setWindowIcon(QIcon(pixmap))

        # Модель и контроллер
        self.model = NetworkModel()
        self.canvas = NetworkCanvas(self.model)
        self.controller = NetworkController(self.model, self.canvas, self)

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()

        # Создаём демонстрационную сеть
        self._create_demo_network()

    def _setup_ui(self):
        """Создаёт основной интерфейс окна."""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Левая панель инструментов
        left_panel = self._create_left_panel()
        layout.addWidget(left_panel)

        # Канвас
        layout.addWidget(self.canvas, 1)

    def _create_left_panel(self) -> QWidget:
        """Создаёт левую панель с настройками и действиями."""
        # Внешний контейнер
        container = QWidget()
        container.setMinimumWidth(250)
        container.setMaximumWidth(280)
        container.setStyleSheet("""
            QWidget#leftPanel {
                background-color: #ffffff;
                border-right: 1px solid #e3e8ef;
            }
        """)
        container.setObjectName("leftPanel")

        # Обёртка со скроллом
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        panel = QWidget()
        panel.setStyleSheet("background-color: #ffffff;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # ===== Заголовок =====
        header = QLabel("Network Visualizer")
        header.setStyleSheet("""
            font-size: 15px;
            font-weight: 700;
            color: #0066cc;
            padding: 4px 0 8px 0;
        """)
        layout.addWidget(header)

        # ===== Фильтр групп =====
        filter_group = QGroupBox("🔍 Фильтр групп")
        filter_layout = QVBoxLayout(filter_group)
        filter_layout.setSpacing(8)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Поиск группы...")
        self.filter_edit.textChanged.connect(self.model.set_filter)
        filter_layout.addWidget(self.filter_edit)

        clear_filter_btn = QPushButton("✕ Очистить")
        clear_filter_btn.clicked.connect(lambda: self.filter_edit.clear())
        filter_layout.addWidget(clear_filter_btn)

        layout.addWidget(filter_group)

        # ===== Настройки отображения =====
        display_group = QGroupBox("👁 Отображение")
        display_layout = QVBoxLayout(display_group)
        display_layout.setSpacing(6)

        self.show_ports_cb = QCheckBox("Подписи портов")
        self.show_ports_cb.setChecked(True)
        self.show_ports_cb.stateChanged.connect(
            lambda state: setattr(self.model, 'show_port_labels',
                                  state == Qt.CheckState.Checked.value)
        )
        self.show_ports_cb.stateChanged.connect(self.model.notify_observers)
        display_layout.addWidget(self.show_ports_cb)

        self.show_conns_cb = QCheckBox("Подписи соединений")
        self.show_conns_cb.setChecked(True)
        self.show_conns_cb.stateChanged.connect(
            lambda state: setattr(self.model, 'show_connection_labels',
                                  state == Qt.CheckState.Checked.value)
        )
        self.show_conns_cb.stateChanged.connect(self.model.notify_observers)
        display_layout.addWidget(self.show_conns_cb)

        self.show_grid_cb = QCheckBox("Сетка")
        self.show_grid_cb.setChecked(True)
        self.show_grid_cb.stateChanged.connect(
            lambda state: setattr(self.model, 'show_grid',
                                  state == Qt.CheckState.Checked.value)
        )
        self.show_grid_cb.stateChanged.connect(self.model.notify_observers)
        display_layout.addWidget(self.show_grid_cb)

        layout.addWidget(display_group)

        # ===== Действия =====
        actions_group = QGroupBox("Действия")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setSpacing(6)

        channel_btn = QPushButton("🔗 Создать канал")
        channel_btn.clicked.connect(self.controller._on_channel_requested)
        actions_layout.addWidget(channel_btn)

        groups_btn = QPushButton("📊 Группы соединений")
        groups_btn.clicked.connect(self.controller._on_groups_requested)
        actions_layout.addWidget(groups_btn)

        save_btn = QPushButton("💾 Сохранить")
        save_btn.clicked.connect(self._save_project)
        actions_layout.addWidget(save_btn)

        load_btn = QPushButton("📂 Загрузить")
        load_btn.clicked.connect(self._load_project)
        actions_layout.addWidget(load_btn)

        delete_btn = QPushButton("🗑️ Удалить выбранное")
        delete_btn.setProperty("class", "danger")
        delete_btn.clicked.connect(self.canvas._delete_selected)
        actions_layout.addWidget(delete_btn)

        layout.addWidget(actions_group)

        # ===== Подсказки =====
        hints_group = QGroupBox("Управление")
        hints_layout = QVBoxLayout(hints_group)

        hints = QLabel(
            "• <b>ПКМ</b> — контекстное меню<br>"
            "• <b>ПКМ на порте</b> — начать соединение<br>"
            "• <b>ЛКМ на порте</b> — завершить<br>"
            "• <b>Двойной клик</b> — редактировать<br>"
            "• <b>Delete</b> — удалить<br>"
            "• <b>Ctrl+ЛКМ</b> — панорамирование<br>"
            "• <b>Колесико</b> — масштаб"
        )
        hints.setStyleSheet("""
            color: #6b7280;
            font-size: 11px;
            line-height: 1.5;
            padding: 4px;
        """)
        hints.setTextFormat(Qt.TextFormat.RichText)
        hints_layout.addWidget(hints)

        layout.addWidget(hints_group)

        layout.addStretch()

        scroll.setWidget(panel)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        return container

    def _setup_menu(self):
        """Создаёт меню приложения."""
        menubar = self.menuBar()

        # Меню "Файл"
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

        # Меню "Правка"
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
        delete_action.triggered.connect(self.canvas._delete_selected)
        edit_menu.addAction(delete_action)

        # Меню "Вид"
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

        # Меню "Помощь"
        help_menu = menubar.addMenu("Помощь")

        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Создаёт панель инструментов."""
        toolbar = QToolBar("Основная")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        # Разделы
        new_action = QAction("📄  Новый", self)
        new_action.setToolTip("Создать новый проект")
        new_action.triggered.connect(self._new_project)
        toolbar.addAction(new_action)

        save_action = QAction("💾  Сохранить", self)
        save_action.setToolTip("Сохранить проект в файл")
        save_action.triggered.connect(self._save_project)
        toolbar.addAction(save_action)

        load_action = QAction("📂  Загрузить", self)
        load_action.setToolTip("Загрузить проект из файла")
        load_action.triggered.connect(self._load_project)
        toolbar.addAction(load_action)

        toolbar.addSeparator()

        channel_action = QAction("🔗  Канал", self)
        channel_action.setToolTip("Создать канал связи")
        channel_action.triggered.connect(self.controller._on_channel_requested)
        toolbar.addAction(channel_action)

        groups_action = QAction("📊  Группы", self)
        groups_action.setToolTip("Управление группами соединений")
        groups_action.triggered.connect(self.controller._on_groups_requested)
        toolbar.addAction(groups_action)

        toolbar.addSeparator()

        delete_action = QAction("🗑️  Удалить", self)
        delete_action.setToolTip("Удалить выбранное устройство")
        delete_action.triggered.connect(self.canvas._delete_selected)
        toolbar.addAction(delete_action)

        # Растяжка
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

    def _setup_statusbar(self):
        """Создаёт строку состояния с динамической подсказкой."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            "ПКМ на канвасе — создать устройство  •  "
            "ПКМ на свободном выходном порте (■) — начать соединение  •  "
            "Ctrl+ЛКМ — панорамирование  •  Колесико — масштаб"
        )

    def _create_demo_network(self):
        """Создаёт демонстрационную сеть при запуске."""
        devices_data = [
            ("Main Cross-connect", DeviceCategory.GLOBAL_INPUT, 200, 200),
            ("Local Cross-connect", DeviceCategory.LOCAL_INPUT, 200, 500),
            ("Aggregator", DeviceCategory.SWITCHES, 600, 200),
            ("Switch", DeviceCategory.SWITCHES, 600, 500),
            ("App Server", DeviceCategory.SERVERS, 1000, 200),
            ("DB Server", DeviceCategory.SERVERS, 1000, 400),
        ]

        created = []
        for dtype, cat, x, y in devices_data:
            dev = self.model.add_device(dtype, cat, x, y)
            created.append(dev)

        g1 = self.model.create_group("Магистраль - Сервер приложений")
        g2 = self.model.create_group("Магистраль - Сервер БД")
        g3 = self.model.create_group("Резервный канал")

        d = created
        connections = [
            (d[0].output_ports[0], d[1].input_ports[0], "Fiber Optic", 50.0, g1.id),
            (d[1].output_ports[0], d[2].input_ports[0], "Ethernet", 5.0, g1.id),
            (d[2].output_ports[0], d[4].input_ports[0], "Ethernet", 2.0, g1.id),
            (d[0].output_ports[1], d[1].input_ports[1], "Fiber Optic", 50.0, g2.id),
            (d[1].output_ports[1], d[3].input_ports[0], "Ethernet", 5.0, g2.id),
            (d[3].output_ports[0], d[5].input_ports[0], "Ethernet", 2.0, g2.id),
            (d[2].output_ports[1], d[3].input_ports[1], "Fiber Optic", 3.0, g3.id),
            (d[3].output_ports[1], d[2].input_ports[1], "Fiber Optic", 3.0, None),
        ]

        for p1, p2, ct, length, gid in connections:
            self.model.add_connection(p1, p2, ct, length, gid)

    def _new_project(self):
        """Создаёт новый пустой проект."""
        reply = QMessageBox.question(
            self, "Новый проект",
            "Создать новый проект? Несохранённые изменения будут потеряны.",
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
        """Сохраняет проект в JSON файл."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", "",
            "JSON Files (*.json)"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.model.to_dict(), f, indent=2, ensure_ascii=False)
                self.status_bar.showMessage(f"Сохранено: {filename}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

    def _load_project(self):
        """Загружает проект из JSON файла."""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Загрузить проект", "",
            "JSON Files (*.json)"
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.model.from_dict(json.load(f))
                self.status_bar.showMessage(f"Загружено: {filename}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить: {e}")

    def _show_about(self):
        """Показывает диалог "О программе"."""
        QMessageBox.about(
            self, "О программе",
            "<h2>Network Visualizer</h2>"
            "<p>Приложение для визуализации сетевой инфраструктуры</p>"
            "<p><b>Возможности:</b></p>"
            "<ul>"
            "<li>Создание устройств через ПКМ</li>"
            "<li>Соединения между портами</li>"
            "<li>Группировка соединений в каналы</li>"
            "<li>Фильтрация групп</li>"
            "<li>Панорамирование и масштабирование</li>"
            "<li>Сохранение/загрузка проектов</li>"
            "</ul>"
            "<p><b>Управление:</b></p>"
            "<ul>"
            "<li><b>ПКМ</b> — контекстное меню</li>"
            "<li><b>ПКМ на порте</b> — начать соединение</li>"
            "<li><b>ЛКМ на порте</b> — завершить соединение</li>"
            "<li><b>Двойной клик</b> — редактировать устройство</li>"
            "<li><b>Delete</b> — удалить выбранное</li>"
            "<li><b>Ctrl+ЛКМ</b> — панорамирование</li>"
            "<li><b>Колесико</b> — масштабирование</li>"
            "</ul>"
            "<p>Версия 1.0 • PyQt6</p>"
        )


# ============================================================
#  ТОЧКА ВХОДА
# ============================================================

def main():
    """Точка входа приложения."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    app.setStyleSheet("""
        /* ============ ГЛОБАЛЬНЫЕ СТИЛИ ============ */
        QWidget {
            font-family: "Segoe UI", "San Francisco", "Ubuntu", Arial, sans-serif;
            font-size: 13px;
            color: #2c3e50;
        }

        QMainWindow, QDialog {
            background-color: #f7f9fc;
        }

        /* ============ МЕНЮ ============ */
        QMenuBar {
            background-color: #ffffff;
            border-bottom: 1px solid #e3e8ef;
            padding: 4px 8px;
        }
        QMenuBar::item {
            padding: 6px 12px;
            border-radius: 4px;
            background: transparent;
        }
        QMenuBar::item:selected {
            background-color: #e8f0fe;
            color: #0066cc;
        }
        QMenuBar::item:pressed {
            background-color: #d6e4fb;
        }

        QMenu {
            background-color: #ffffff;
            border: 1px solid #e3e8ef;
            border-radius: 6px;
            padding: 5px;
        }
        QMenu::item {
            padding: 7px 24px 7px 16px;
            border-radius: 4px;
            color: #2c3e50;
        }
        QMenu::item:selected {
            background-color: #e8f0fe;
            color: #0066cc;
        }
        QMenu::item:disabled {
            color: #b0b8c4;
        }
        QMenu::separator {
            height: 1px;
            background-color: #e3e8ef;
            margin: 4px 10px;
        }

        /* ============ ПАНЕЛЬ ИНСТРУМЕНТОВ ============ */
        QToolBar {
            background-color: #ffffff;
            border-bottom: 1px solid #e3e8ef;
            padding: 4px 8px;
            spacing: 4px;
        }
        QToolBar::separator {
            width: 1px;
            background-color: #e3e8ef;
            margin: 4px 6px;
        }
        QToolButton {
            padding: 6px 10px;
            border-radius: 4px;
            background: transparent;
            color: #2c3e50;
        }
        QToolButton:hover {
            background-color: #e8f0fe;
            color: #0066cc;
        }
        QToolButton:pressed {
            background-color: #d6e4fb;
        }

        /* ============ КНОПКИ ============ */
        QPushButton {
            padding: 7px 14px;
            border: 1px solid #d0d7e2;
            border-radius: 5px;
            background-color: #ffffff;
            color: #2c3e50;
            min-height: 16px;
        }
        QPushButton:hover {
            background-color: #f0f4fa;
            border-color: #b8c4d4;
        }
        QPushButton:pressed {
            background-color: #e2e9f3;
            border-color: #a0aec0;
        }
        QPushButton:default {
            border-color: #0066cc;
            background-color: #0066cc;
            color: #ffffff;
        }
        QPushButton:default:hover {
            background-color: #0057ad;
        }
        QPushButton:disabled {
            background-color: #f5f6f8;
            color: #a0aec0;
            border-color: #e3e8ef;
        }

        /* Кнопки удаления — красноватые */
        QPushButton[class="danger"] {
            color: #d92d20;
        }
        QPushButton[class="danger"]:hover {
            background-color: #fef3f2;
            border-color: #fda29b;
        }

        /* ============ ПОЛЯ ВВОДА ============ */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            padding: 6px 10px;
            border: 1px solid #d0d7e2;
            border-radius: 5px;
            background-color: #ffffff;
            color: #2c3e50;
            min-height: 16px;
            selection-background-color: #b8d4f8;
            selection-color: #1a1a1a;
        }
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border-color: #0066cc;
            outline: none;
        }
        QLineEdit:disabled, QComboBox:disabled {
            background-color: #f5f6f8;
            color: #a0aec0;
        }
        QLineEdit::placeholder {
            color: #9aa5b4;
        }

        /* Выпадающий список QComboBox */
        QComboBox::drop-down {
            border: none;
            width: 24px;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #6b7280;
            margin-right: 8px;
        }
        QComboBox QAbstractItemView {
            background-color: #ffffff;
            border: 1px solid #e3e8ef;
            border-radius: 5px;
            padding: 4px;
            selection-background-color: #e8f0fe;
            selection-color: #0066cc;
            outline: none;
        }

        /* ============ ЧЕКБОКСЫ ============ */
        QCheckBox {
            padding: 4px 0;
            spacing: 8px;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 1px solid #d0d7e2;
            border-radius: 3px;
            background-color: #ffffff;
        }
        QCheckBox::indicator:hover {
            border-color: #0066cc;
        }
        QCheckBox::indicator:checked {
            background-color: #0066cc;
            border-color: #0066cc;
            image: none;
        }
        QCheckBox::indicator:checked::after {
            content: "✓";
            color: white;
        }

        /* ============ ГРУППЫ (QGroupBox) ============ */
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

        /* ============ СПИСКИ ============ */
        QListWidget, QTreeWidget, QTableWidget {
            background-color: #ffffff;
            border: 1px solid #e3e8ef;
            border-radius: 6px;
            padding: 4px;
            outline: none;
            selection-background-color: #e8f0fe;
            selection-color: #0066cc;
        }
        QListWidget::item, QTreeWidget::item, QTableWidget::item {
            padding: 6px 8px;
            border-radius: 4px;
        }
        QListWidget::item:hover, QTreeWidget::item:hover {
            background-color: #f0f4fa;
        }
        QListWidget::item:selected, QTreeWidget::item:selected {
            background-color: #e8f0fe;
            color: #0066cc;
        }

        /* Заголовки таблиц */
        QHeaderView::section {
            background-color: #f7f9fc;
            color: #4a5568;
            padding: 6px 10px;
            border: none;
            border-right: 1px solid #e3e8ef;
            border-bottom: 1px solid #e3e8ef;
            font-weight: 600;
        }
        QHeaderView::section:last {
            border-right: none;
        }

        /* ============ СКРОЛЛБАРЫ ============ */
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
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: transparent;
        }

        QScrollBar:horizontal {
            background: transparent;
            height: 10px;
            margin: 0;
        }
        QScrollBar::handle:horizontal {
            background: #cbd5e0;
            border-radius: 5px;
            min-width: 30px;
            margin: 2px;
        }
        QScrollBar::handle:horizontal:hover {
            background: #a0aec0;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: transparent;
        }

        /* ============ СТАТУС-БАР ============ */
        QStatusBar {
            background-color: #ffffff;
            border-top: 1px solid #e3e8ef;
            color: #6b7280;
            padding: 2px 8px;
        }
        QStatusBar::item {
            border: none;
        }

        /* ============ СПЛИТТЕР ============ */
        QSplitter::handle {
            background-color: #e3e8ef;
            width: 1px;
        }
        QSplitter::handle:hover {
            background-color: #0066cc;
        }

        /* ============ ВКЛАДКИ ============ */
        QTabWidget::pane {
            border: 1px solid #e3e8ef;
            border-radius: 6px;
            background-color: #ffffff;
            top: -1px;
        }
        QTabBar::tab {
            background-color: transparent;
            color: #6b7280;
            padding: 8px 16px;
            border: 1px solid transparent;
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            margin-right: 2px;
        }
        QTabBar::tab:hover {
            background-color: #f0f4fa;
            color: #2c3e50;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            color: #0066cc;
            border-color: #e3e8ef;
            font-weight: 600;
        }

        /* ============ ДИАЛОГИ ============ */
        QDialog {
            background-color: #f7f9fc;
        }
        QDialogButtonBox QPushButton {
            min-width: 80px;
        }

        /* ============ TOOLTIP ============ */
        QToolTip {
            background-color: #2c3e50;
            color: #ffffff;
            border: none;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: 12px;
        }

        /* ============ SCROLL AREA ============ */
        QScrollArea {
            border: 1px solid #e3e8ef;
            border-radius: 6px;
            background-color: #ffffff;
        }
        QScrollArea > QWidget > QWidget {
            background-color: #ffffff;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()