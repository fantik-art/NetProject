"""
Network Visualizer - Многопользовательский редактор сетевой инфраструктуры
Версия: Tkinter (без сервера, локальный прототип)

Основные механики:
  - Добавление устройств через контекстное меню (ПКМ на канвасе)
  - Перемещение устройств перетаскиванием (ЛКМ)
  - Создание соединений между портами (ПКМ на выходе -> ЛКМ на входе)
  - Редактирование устройств (двойной клик)
  - Удаление устройств (клавиша Delete)
  - Панорамирование канваса (Ctrl+ЛКМ или средняя кнопка мыши)
  - Масштабирование (колесико мыши)
  - Сохранение и загрузка проектов в JSON
  - Группировка соединений в каналы
  - Фильтрация групп через поиск
  - Настройки отображения (сетка, подписи портов, подписи соединений)
  - Демонстрационная сеть при запуске

Визуальные элементы:
  - Устройства: цветные прямоугольники с названием и типом
  - Входные порты: треугольники ▼ слева (зеленые если подключены)
  - Выходные порты: квадраты ■ справа (оранжевые если подключены)
  - Соединения: кривые Безье со стрелками направления
  - Фоновая сетка для ориентации
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import math
import random
from typing import Optional, List, Dict, Tuple
from collections import defaultdict


# ============================================================
# МОДЕЛЬ ДАННЫХ
# Хранит все устройства, соединения, группы и настройки
# ============================================================

class NetworkModel:
    """
    Центральное хранилище данных сети.
    Содержит списки устройств, соединений и групп.
    Управляет созданием, удалением и поиском элементов.
    """

    def __init__(self):
        # Основные данные
        self.devices: List[dict] = []  # Список всех устройств
        self.connections: List[dict] = []  # Список всех соединений
        self.groups: List[dict] = []  # Список групп соединений (каналов)

        # Счетчики для генерации уникальных ID
        self.next_device_id = 1
        self.next_group_id = 1

        # Настройки отображения
        self.show_grid = True  # Показывать фоновую сетку
        self.show_port_labels = True  # Показывать подписи портов
        self.show_connection_labels = True  # Показывать подписи соединений

        # Фильтр для поиска групп
        self.filter_text = ""  # Текст фильтра (пустой = показать всё)

        # Список наблюдателей для обновления UI при изменениях
        self._observers = []

    # ========================================================
    # УСТРОЙСТВА
    # ========================================================

    def add_device(self, name: str, device_type: str, category: str,
                   x: float = 100, y: float = 100) -> dict:
        """
        Создает новое устройство с автоматической генерацией портов.

        Аргументы:
            name - название устройства (например "Коммутатор 1")
            device_type - тип устройства (например "Switch")
            category - категория: GLOBAL_INPUT, LOCAL_INPUT, SWITCHES, SERVERS
            x, y - координаты на канвасе

        Возвращает созданное устройство (словарь).
        """
        # Определяем количество портов в зависимости от категории
        port_configs = {
            'GLOBAL_INPUT': (6, 2),  # 6 входных, 2 выходных
            'LOCAL_INPUT': (4, 4),  # 4 входных, 4 выходных
            'SWITCHES': (8, 8),  # 8 входных, 8 выходных
            'SERVERS': (2, 1)  # 2 входных, 1 выходной
        }
        input_count, output_count = port_configs.get(category, (4, 4))

        # Создаем устройство
        device = {
            'id': self.next_device_id,
            'name': name,
            'type': device_type,
            'category': category,
            'x': x, 'y': y,
            'width': 160, 'height': 100,
            'input_ports': [],  # Входные порты (треугольники ▼)
            'output_ports': []  # Выходные порты (квадраты ■)
        }

        # Генерируем входные порты
        for i in range(input_count):
            device['input_ports'].append({
                'id': i,
                'name': f'IN {i + 1}',
                'type': 'input',
                'x': 0, 'y': 0  # Позиции обновятся в update_port_positions
            })

        # Генерируем выходные порты
        for i in range(output_count):
            device['output_ports'].append({
                'id': i,
                'name': f'OUT {i + 1}',
                'type': 'output',
                'x': 0, 'y': 0
            })

        self.next_device_id += 1
        self.devices.append(device)
        self.update_port_positions(device)  # Рассчитываем позиции портов
        self._notify()  # Уведомляем UI об изменениях
        return device

    def remove_device(self, device: dict):
        """
        Удаляет устройство и все связанные с ним соединения.
        """
        # Удаляем соединения, где участвует это устройство
        self.connections = [
            c for c in self.connections
            if c['dev1_id'] != device['id'] and c['dev2_id'] != device['id']
        ]
        # Удаляем само устройство
        self.devices.remove(device)
        self._notify()

    def update_port_positions(self, device: dict):
        """
        Пересчитывает позиции портов при перемещении устройства.
        Входные порты равномерно распределяются по левой стороне,
        выходные - по правой.
        """
        x, y = device['x'], device['y']
        w, h = device['width'], device['height']

        # Входные порты (левая сторона)
        for i, port in enumerate(device['input_ports']):
            port['x'] = x - w / 2
            n = len(device['input_ports'])
            port['y'] = y - h / 2 + (i + 1) * (h / (n + 1)) if n > 1 else y

        # Выходные порты (правая сторона)
        for i, port in enumerate(device['output_ports']):
            port['x'] = x + w / 2
            n = len(device['output_ports'])
            port['y'] = y - h / 2 + (i + 1) * (h / (n + 1)) if n > 1 else y

    # ========================================================
    # СОЕДИНЕНИЯ
    # ========================================================

    def add_connection(self, dev1: dict, port1: dict,
                       dev2: dict, port2: dict,
                       cable_type: str = 'Ethernet',
                       length: float = 1.0,
                       group_id: int = None) -> bool:
        """
        Создает соединение между выходным портом dev1 и входным портом dev2.

        Аргументы:
            dev1 - устройство-источник (выход)
            port1 - порт источника (должен быть output)
            dev2 - устройство-приемник (вход)
            port2 - порт приемника (должен быть input)
            cable_type - тип кабеля (Ethernet, Fiber Optic, Serial, Coaxial)
            length - физическая длина кабеля в метрах
            group_id - ID группы соединений (None = без группы)

        Возвращает True если соединение создано, False если дубликат.
        """
        # Проверяем, нет ли уже такого соединения
        for conn in self.connections:
            if (conn['dev1_id'] == dev1['id'] and conn['port1_id'] == port1['id'] and
                    conn['dev2_id'] == dev2['id'] and conn['port2_id'] == port2['id']):
                return False

        # Создаем соединение
        self.connections.append({
            'dev1_id': dev1['id'],
            'port1_id': port1['id'],
            'dev2_id': dev2['id'],
            'port2_id': port2['id'],
            'cable_type': cable_type,
            'length': length,
            'group_id': group_id
        })
        self._notify()
        return True

    def remove_connections_for_port(self, device: dict, port: dict):
        """
        Удаляет все соединения, связанные с указанным портом.
        Используется при удалении порта.
        """
        self.connections = [
            c for c in self.connections
            if not ((c['dev1_id'] == device['id'] and c['port1_id'] == port['id']) or
                    (c['dev2_id'] == device['id'] and c['port2_id'] == port['id']))
        ]
        self._notify()

    # ========================================================
    # ГРУППЫ СОЕДИНЕНИЙ
    # ========================================================

    def create_group(self, name: str) -> dict:
        """
        Создает новую группу соединений (канал) со случайным цветом.
        Группы позволяют объединять несколько соединений в логический канал
        (например "Магистраль Москва - Санкт-Петербург").
        """
        colors = ['#ff6464', '#64ff64', '#6464ff', '#ffff64',
                  '#ff64ff', '#64ffff', '#c89664', '#96c864']
        color = colors[self.next_group_id % len(colors)]

        group = {
            'id': self.next_group_id,
            'name': name,
            'color': color,
            'visible': True
        }

        self.next_group_id += 1
        self.groups.append(group)
        self._notify()
        return group

    def get_group_connections(self, group: dict) -> List[dict]:
        """
        Возвращает все соединения, принадлежащие указанной группе.
        """
        return [c for c in self.connections if c['group_id'] == group['id']]

    def get_visible_connections(self) -> List[dict]:
        """
        Возвращает соединения с учетом фильтра.
        Если фильтр пустой - возвращает все соединения.
        Если фильтр задан - только соединения из групп, чье имя содержит фильтр,
        плюс соединения без группы.
        """
        if not self.filter_text:
            return self.connections

        # Находим ID групп, соответствующих фильтру
        visible_group_ids = set()
        for group in self.groups:
            if self.filter_text.lower() in group['name'].lower():
                visible_group_ids.add(group['id'])

        # Фильтруем соединения
        return [
            c for c in self.connections
            if c['group_id'] is None or c['group_id'] in visible_group_ids
        ]

    # ========================================================
    # ПОИСК
    # ========================================================

    def find_device(self, device_id: int) -> Optional[dict]:
        """
        Находит устройство по его ID.
        Возвращает устройство или None если не найдено.
        """
        for d in self.devices:
            if d['id'] == device_id:
                return d
        return None

    def find_port(self, device: dict, port_id: int, port_type: str) -> Optional[dict]:
        """
        Находит порт в устройстве по ID и типу.
        port_type: 'input' или 'output'
        """
        ports = device['input_ports'] if port_type == 'input' else device['output_ports']
        for p in ports:
            if p['id'] == port_id:
                return p
        return None

    def find_device_by_port(self, port: dict) -> Optional[dict]:
        """
        Находит устройство, которому принадлежит указанный порт.
        """
        for dev in self.devices:
            if port in dev['input_ports'] or port in dev['output_ports']:
                return dev
        return None

    # ========================================================
    # ФИЛЬТРАЦИЯ
    # ========================================================

    def set_filter(self, text: str):
        """
        Устанавливает текст фильтра для групп.
        Пустая строка = показать все соединения.
        """
        self.filter_text = text.strip()
        self._notify()

    # ========================================================
    # СЕРИАЛИЗАЦИЯ (сохранение/загрузка)
    # ========================================================

    def to_dict(self) -> dict:
        """
        Сериализует всю модель в словарь для сохранения в JSON.
        """
        return {
            'devices': self.devices,
            'connections': self.connections,
            'groups': self.groups,
            'next_device_id': self.next_device_id,
            'next_group_id': self.next_group_id,
            'settings': {
                'show_grid': self.show_grid,
                'show_port_labels': self.show_port_labels,
                'show_connection_labels': self.show_connection_labels
            }
        }

    def from_dict(self, data: dict):
        """
        Загружает модель из словаря (восстановление из JSON).
        """
        self.devices = data.get('devices', [])
        self.connections = data.get('connections', [])
        self.groups = data.get('groups', [])
        self.next_device_id = data.get('next_device_id', 1)
        self.next_group_id = data.get('next_group_id', 1)

        settings = data.get('settings', {})
        self.show_grid = settings.get('show_grid', True)
        self.show_port_labels = settings.get('show_port_labels', True)
        self.show_connection_labels = settings.get('show_connection_labels', True)

        self._notify()

    # ========================================================
    # НАБЛЮДАТЕЛИ (паттерн Observer)
    # ========================================================

    def add_observer(self, callback):
        """
        Добавляет функцию-наблюдателя, которая будет вызываться
        при любых изменениях в модели.
        """
        self._observers.append(callback)

    def _notify(self):
        """
        Уведомляет всех наблюдателей об изменениях.
        Вызывается после каждой операции, меняющей данные.
        """
        for callback in self._observers:
            callback()


# ============================================================
# КАНВАС (холст для отрисовки сетевой топологии)
# ============================================================

class NetworkCanvas(tk.Canvas):
    """
    Главный виджет для отображения и редактирования сети.
    Наследуется от tk.Canvas.

    Отвечает за:
    - Отрисовку устройств, портов, соединений
    - Обработку событий мыши и клавиатуры
    - Контекстные меню
    - Панорамирование и масштабирование
    """

    def __init__(self, parent, model: NetworkModel, **kwargs):
        super().__init__(parent, bg='#1e1e2e', highlightthickness=0, **kwargs)
        self.model = model

        # ===== КАМЕРА =====
        self.scale = 1.0  # Текущий масштаб (1.0 = 100%)
        self.offset_x = 0  # Смещение канваса по X (панорамирование)
        self.offset_y = 0  # Смещение канваса по Y

        # ===== СОСТОЯНИЕ ИНТЕРФЕЙСА =====
        self.selected_device = None  # Выбранное устройство (подсвечивается)
        self.connection_start_port = None  # Порт-источник при создании соединения
        self.connection_start_dev = None  # Устройство-источник при создании соединения

        # ===== ПЕРЕТАСКИВАНИЕ =====
        self.drag_device = None  # Перетаскиваемое устройство
        self.drag_start_x = 0  # Начальная позиция мыши при перетаскивании
        self.drag_start_y = 0
        self.is_dragging = False  # Флаг: идет перетаскивание

        # ===== ПАНОРАМИРОВАНИЕ =====
        self.is_panning = False  # Флаг: режим панорамирования
        self.pan_start_x = 0  # Начальная позиция мыши при панорамировании
        self.pan_start_y = 0
        self.pan_offset_x = 0  # Сохраненное смещение при начале панорамирования
        self.pan_offset_y = 0

        # ===== ЦВЕТОВАЯ СХЕМА =====
        self.colors = {
            # Устройства по категориям
            'GLOBAL_INPUT': '#4682b4',  # Стальной синий (внешние кроссы)
            'LOCAL_INPUT': '#87ceeb',  # Голубой (локальные кроссы)
            'SWITCHES': '#3cb371',  # Зеленый (коммутаторы)
            'SERVERS': '#9370db',  # Фиолетовый (серверы)
            # Порты
            'port_free': '#585b70',  # Серый (свободный порт)
            'port_in_used': '#00c800',  # Зеленый (подключенный вход)
            'port_out_used': '#c89600',  # Оранжевый (подключенный выход)
            # Соединения
            'Ethernet': '#0064c8',  # Синий
            'Fiber Optic': '#c86400',  # Оранжевый
            'Serial': '#646464',  # Серый
            'Coaxial': '#009600',  # Темно-зеленый
            # Интерфейс
            'grid': '#313244',  # Сетка
            'text': '#cdd6f4',  # Основной текст
            'text_dim': '#a6adc8',  # Второстепенный текст
            'selection': '#f9e2af',  # Подсветка выбранного
            'header_bg': '#000000',  # Фон заголовка устройства
        }

        # ===== ПРИВЯЗКА СОБЫТИЙ =====
        self.bind('<Button-1>', self._on_left_click)  # ЛКМ
        self.bind('<Button-2>', self._on_middle_click)  # Средняя кнопка мыши
        self.bind('<Button-3>', self._on_right_click)  # ПКМ (контекстное меню)
        self.bind('<B1-Motion>', self._on_left_drag)  # Перетаскивание ЛКМ
        self.bind('<B2-Motion>', self._on_pan_drag)  # Панорамирование (средняя)
        self.bind('<B3-Motion>', self._on_pan_drag)  # Панорамирование (правая)
        self.bind('<Double-Button-1>', self._on_double_click)  # Двойной клик
        self.bind('<MouseWheel>', self._on_wheel)  # Колесико мыши
        self.bind('<Button-4>', self._on_wheel_up)  # Колесико вверх (Linux)
        self.bind('<Button-5>', self._on_wheel_down)  # Колесико вниз (Linux)
        self.bind('<Control-Button-1>', self._on_ctrl_click)  # Ctrl+ЛКМ
        self.bind('<Delete>', self._on_delete)  # Клавиша Delete
        self.bind('<Escape>', self._on_escape)  # Клавиша Escape

        # Для обработки клавиатуры
        self.focus_set()

        # Подписываемся на изменения модели
        self.model.add_observer(self.redraw)

    # ========================================================
    # КООРДИНАТЫ (преобразование экран <-> сцена)
    # ========================================================

    def _to_canvas(self, x: float, y: float) -> Tuple[float, float]:
        """
        Переводит координаты сцены (где находятся устройства)
        в координаты канваса (пиксели на экране) с учетом камеры.
        """
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    def _to_scene(self, cx: float, cy: float) -> Tuple[float, float]:
        """
        Переводит координаты канваса (пиксели на экране)
        в координаты сцены (где находятся устройства).
        """
        return (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale

    def _find_device_at(self, sx: float, sy: float) -> Optional[dict]:
        """
        Ищет устройство по координатам сцены.
        Проверяет попадание точки в прямоугольник устройства.
        Просматривает список с конца, чтобы верхние устройства имели приоритет.
        """
        for dev in reversed(self.model.devices):
            if abs(sx - dev['x']) < dev['width'] / 2 and \
                    abs(sy - dev['y']) < dev['height'] / 2:
                return dev
        return None

    def _find_port_at(self, sx: float, sy: float) -> Optional[Tuple[dict, dict]]:
        """
        Ищет порт по координатам сцены.
        Сначала проверяет выходные порты (приоритет для начала соединения),
        затем входные.
        Возвращает кортеж (порт, устройство) или None.
        """
        for dev in self.model.devices:
            # Проверяем выходные порты (квадраты ■)
            for port in dev['output_ports']:
                if abs(sx - port['x']) < 8 and abs(sy - port['y']) < 8:
                    return port, dev
            # Проверяем входные порты (треугольники ▼)
            for port in dev['input_ports']:
                if abs(sx - port['x']) < 8 and abs(sy - port['y']) < 8:
                    return port, dev
        return None

    # ========================================================
    # ОТРИСОВКА (вызывается при любых изменениях)
    # ========================================================

    def redraw(self):
        """
        Полная перерисовка канваса.
        Удаляет все элементы и рисует заново в порядке:
        сетка -> соединения -> временная линия -> устройства.
        """
        self.delete('all')  # Очищаем канвас

        # 1. Фоновая сетка (если включена в настройках)
        if self.model.show_grid:
            self._draw_grid()

        # 2. Соединения (рисуются ПОД устройствами)
        for conn in self.model.get_visible_connections():
            self._draw_connection(conn)

        # 3. Временная линия при создании соединения
        if self.connection_start_port:
            self._draw_temp_connection()

        # 4. Устройства (рисуются НАД соединениями)
        for device in self.model.devices:
            self._draw_device(device)

        # 5. Индикатор фильтра (если активен)
        if self.model.filter_text:
            self._draw_filter_indicator()

    def _draw_grid(self):
        """Рисует фоновую сетку для визуальной ориентации"""
        grid_size = 50  # Размер ячейки сетки в единицах сцены

        # Определяем видимую область с запасом
        w = int(self.winfo_width() / self.scale) + grid_size * 2
        h = int(self.winfo_height() / self.scale) + grid_size * 2

        # Рисуем вертикальные линии
        for x in range(0, w, grid_size):
            cx, _ = self._to_canvas(x, 0)
            self.create_line(cx, 0, cx, self.winfo_height(),
                             fill=self.colors['grid'], width=1, tags='grid')

        # Рисуем горизонтальные линии
        for y in range(0, h, grid_size):
            _, cy = self._to_canvas(0, y)
            self.create_line(0, cy, self.winfo_width(), cy,
                             fill=self.colors['grid'], width=1, tags='grid')

    def _draw_device(self, dev: dict):
        """
        Рисует одно устройство:
        - Цветной прямоугольник с закругленными углами
        - Темный заголовок с названием
        - Тип устройства снизу
        - Порты: треугольники ▼ (вход) и квадраты ■ (выход)
        - Желтая рамка если устройство выбрано
        """
        # Координаты на канвасе
        x, y = self._to_canvas(dev['x'], dev['y'])
        w = dev['width'] * self.scale
        h = dev['height'] * self.scale

        # Цвет устройства зависит от категории
        category = dev.get('category', 'SWITCHES')
        device_color = self.colors.get(category, '#808080')

        # Цвет рамки: желтый если выбрано, иначе темнее основного
        if dev == self.selected_device:
            border_color = self.colors['selection']
            border_width = 3
        else:
            border_color = self._darken_color(device_color)
            border_width = 2

        # Основной прямоугольник устройства
        self.create_rectangle(
            x - w / 2, y - h / 2, x + w / 2, y + h / 2,
            fill=device_color,
            outline=border_color,
            width=border_width,
            tags=('device', f"dev_{dev['id']}")
        )

        # Заголовок устройства (темная полоса сверху)
        header_h = 22 * self.scale
        self.create_rectangle(
            x - w / 2, y - h / 2, x + w / 2, y - h / 2 + header_h,
            fill=self.colors['header_bg'],
            stipple='gray50',  # Полупрозрачность через штриховку
            outline='',
            tags=('device', f"dev_{dev['id']}")
        )

        # Название устройства (белый текст в заголовке)
        font_size = max(8, int(9 * self.scale))
        self.create_text(
            x, y - h / 2 + header_h / 2,
            text=dev['name'],
            fill=self.colors['text'],
            font=('Arial', font_size, 'bold'),
            tags=('device', f"dev_{dev['id']}")
        )

        # Тип устройства (снизу)
        font_size = max(6, int(7 * self.scale))
        self.create_text(
            x, y + h / 2 - 10 * self.scale,
            text=dev['type'],
            fill=self.colors['text_dim'],
            font=('Arial', font_size),
            tags=('device', f"dev_{dev['id']}")
        )

        # Рисуем порты
        for port in dev['input_ports']:
            self._draw_port(port, is_input=True)
        for port in dev['output_ports']:
            self._draw_port(port, is_input=False)

    def _draw_port(self, port: dict, is_input: bool):
        """
        Рисует порт:
        - Входной: треугольник ▼ (слева устройства)
        - Выходной: квадрат ■ (справа устройства)
        - Цвет: зеленый/оранжевый если подключен, серый если свободен
        - Подпись с названием порта (если включено в настройках)
        """
        px, py = self._to_canvas(port['x'], port['y'])
        size = max(3, int(5 * self.scale))  # Размер порта

        # Проверяем, подключен ли порт
        connected = self._is_port_connected(port)

        # Определяем цвет порта
        if connected:
            color = self.colors['port_in_used'] if is_input else self.colors['port_out_used']
        else:
            color = self.colors['port_free']

        # Рисуем форму порта
        if is_input:
            # Треугольник (входной порт) - острием вправо
            self.create_polygon(
                px - size, py - size,  # Верхний левый угол
                px - size, py + size,  # Нижний левый угол
                px + size, py,  # Острие справа
                fill=color,
                outline=self.colors['text_dim'],
                width=1,
                tags=('port', f"port_{port['id']}")
            )
        else:
            # Квадрат (выходной порт)
            self.create_rectangle(
                px - size, py - size,
                px + size, py + size,
                fill=color,
                outline=self.colors['text_dim'],
                width=1,
                tags=('port', f"port_{port['id']}")
            )

        # Подпись порта (если включена)
        if self.model.show_port_labels:
            font_size = max(5, int(6 * self.scale))
            self.create_text(
                px, py - 12 * self.scale,
                text=port['name'],
                fill=self.colors['text_dim'],
                font=('Arial', font_size),
                tags=('port_label',)
            )

    def _draw_connection(self, conn: dict):
        """
        Рисует соединение между двумя портами:
        - Кривая Безье (плавная изогнутая линия)
        - Стрелка направления (на 70% пути)
        - Подпись с типом кабеля и длиной (если включено)
        - Если соединение в группе - используется цвет группы
        """
        # Находим устройства и порты
        dev1 = self.model.find_device(conn['dev1_id'])
        dev2 = self.model.find_device(conn['dev2_id'])
        if not dev1 or not dev2:
            return

        port1 = self.model.find_port(dev1, conn['port1_id'], 'output')
        port2 = self.model.find_port(dev2, conn['port2_id'], 'input')
        if not port1 or not port2:
            return

        # Координаты на канвасе
        x1, y1 = self._to_canvas(port1['x'], port1['y'])
        x2, y2 = self._to_canvas(port2['x'], port2['y'])

        # Цвет соединения: из группы или по типу кабеля
        cable_color = self.colors.get(conn['cable_type'], '#808080')
        if conn['group_id']:
            group = self._find_group(conn['group_id'])
            if group:
                cable_color = group['color']

        # Рисуем кривую Безье
        # Контрольные точки смещены по горизонтали для плавного изгиба
        dx = abs(x2 - x1) * 0.4

        # Аппроксимируем кривую ломаной линией (20 сегментов)
        points = []
        for i in range(21):
            t = i / 20.0
            # Формула кубической кривой Безье
            px = (1 - t) ** 3 * x1 + 3 * (1 - t) ** 2 * t * (x1 + dx) + \
                 3 * (1 - t) * t ** 2 * (x2 - dx) + t ** 3 * x2
            py = (1 - t) ** 3 * y1 + 3 * (1 - t) ** 2 * t * y1 + \
                 3 * (1 - t) * t ** 2 * y2 + t ** 3 * y2
            points.extend([px, py])

        self.create_line(
            *points,
            fill=cable_color,
            width=2,
            smooth=True,
            tags=('connection',)
        )

        # Рисуем стрелку направления (на 70% длины)
        self._draw_arrow(x1, y1, x2, y2, dx, cable_color)

        # Подпись соединения (если включена)
        if self.model.show_connection_labels:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            label = f"{conn['cable_type']} | {conn['length']}м"

            # Фон подписи
            self.create_rectangle(
                mx - 45, my - 12, mx + 45, my + 12,
                fill='#1e1e2e',
                outline='#45475a',
                tags=('conn_label',)
            )
            # Текст подписи
            self.create_text(
                mx, my,
                text=label,
                fill=self.colors['text'],
                font=('Arial', 7),
                tags=('conn_label',)
            )

    def _draw_arrow(self, x1, y1, x2, y2, dx, color):
        """
        Рисует стрелку направления на кривой Безье.
        Стрелка находится на 70% пути от начала к концу.
        """
        t = 0.7  # Позиция стрелки (70% пути)

        # Вычисляем точку на кривой Безье
        ax = (1 - t) ** 3 * x1 + 3 * (1 - t) ** 2 * t * (x1 + dx) + 3 * (1 - t) * t ** 2 * (x2 - dx) + t ** 3 * x2
        ay = (1 - t) ** 3 * y1 + 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3 * y2

        # Угол направления
        angle = math.atan2(y2 - y1, x2 - x1)
        sz = max(4, int(7 * self.scale))

        # Рисуем треугольник стрелки
        self.create_polygon(
            ax + sz * math.cos(angle), ay + sz * math.sin(angle),
            ax + sz * math.cos(angle + 2.5), ay + sz * math.sin(angle + 2.5),
            ax + sz * math.cos(angle - 2.5), ay + sz * math.sin(angle - 2.5),
            fill=color,
            outline=color,
            tags=('arrow',)
        )

    def _draw_temp_connection(self):
        """
        Рисует временную пунктирную линию при создании соединения.
        От порта-источника до текущей позиции курсора.
        """
        if not self.connection_start_port:
            return

        # Начало линии - порт-источник
        x1, y1 = self._to_canvas(
            self.connection_start_port['x'],
            self.connection_start_port['y']
        )

        # Конец линии - позиция курсора на канвасе
        x2 = self.winfo_pointerx() - self.winfo_rootx()
        y2 = self.winfo_pointery() - self.winfo_rooty()

        self.create_line(
            x1, y1, x2, y2,
            fill='#f9e2af',
            width=2,
            dash=(5, 5),  # Пунктирная линия
            tags=('temp_conn',)
        )

    def _draw_filter_indicator(self):
        """
        Рисует индикатор активного фильтра в левом верхнем углу.
        Показывает текст фильтра и названия видимых групп.
        """
        visible_groups = [
            g['name'] for g in self.model.groups
            if self.model.filter_text.lower() in g['name'].lower()
        ]

        text = f"🔍 Фильтр: '{self.model.filter_text}'"
        if visible_groups:
            text += f" | Группы: {', '.join(visible_groups)}"

        # Полупрозрачный фон
        self.create_rectangle(5, 5, 350, 35, fill='#1e1e2e',
                              outline='#45475a', tags='filter')
        self.create_text(10, 20, text=text, anchor='w',
                         fill='#89b4fa', font=('Arial', 10, 'bold'),
                         tags='filter')

    # ========================================================
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ========================================================

    def _is_port_connected(self, port: dict) -> bool:
        """Проверяет, подключен ли порт (есть ли соединения)"""
        dev = self.model.find_device_by_port(port)
        if not dev:
            return False
        return any(
            (c['dev1_id'] == dev['id'] and c['port1_id'] == port['id']) or
            (c['dev2_id'] == dev['id'] and c['port2_id'] == port['id'])
            for c in self.model.connections
        )

    def _find_group(self, group_id: int) -> Optional[dict]:
        """Находит группу по ID"""
        for g in self.model.groups:
            if g['id'] == group_id:
                return g
        return None

    def _darken_color(self, color: str, factor: float = 0.7) -> str:
        """
        Затемняет цвет для рамки устройства.
        Простая реализация через уменьшение RGB компонентов.
        """
        # Убираем # и конвертируем в RGB
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        # Затемняем
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)

        return f'#{r:02x}{g:02x}{b:02x}'

    # ========================================================
    # ОБРАБОТКА СОБЫТИЙ МЫШИ
    # ========================================================

    def _on_left_click(self, event):
        """
        Обработка левого клика мыши.
        - В режиме соединения: завершает соединение на входном порту
        - На устройстве: выбирает его и начинает перетаскивание
        - На пустом месте: снимает выделение
        """
        sx, sy = self._to_scene(event.x, event.y)

        # Если мы в режиме создания соединения
        if self.connection_start_port:
            result = self._find_port_at(sx, sy)
            if result:
                port, dev = result
                # Принимаем только входные порты
                if port['type'] == 'input':
                    # Показываем диалог настройки соединения
                    self._show_connection_dialog(
                        self.connection_start_dev, self.connection_start_port,
                        dev, port
                    )
            # Выходим из режима соединения
            self.connection_start_port = None
            self.connection_start_dev = None
            self.config(cursor='')
            self.redraw()
            return

        # Проверяем, кликнули ли по порту (для выбора)
        result = self._find_port_at(sx, sy)
        if result:
            port, dev = result
            self.selected_device = dev
            self.redraw()
            return

        # Проверяем устройство
        dev = self._find_device_at(sx, sy)
        if dev:
            self.selected_device = dev
            # Начинаем перетаскивание
            self.is_dragging = True
            self.drag_device = dev
            self.drag_start_x = sx - dev['x']  # Смещение от центра устройства
            self.drag_start_y = sy - dev['y']
            self.redraw()
            return

        # Клик по пустому месту
        self.selected_device = None
        self.redraw()

    def _on_right_click(self, event):
        """
        Обработка правого клика мыши.
        - На выходном порту: начинает создание соединения
        - На устройстве: показывает меню устройства
        - На пустом месте: показывает меню добавления устройств
        """
        sx, sy = self._to_scene(event.x, event.y)

        # Проверяем порты (приоритет - выходные для начала соединения)
        result = self._find_port_at(sx, sy)
        if result:
            port, dev = result
            if port['type'] == 'output':
                # Начинаем создание соединения
                self.connection_start_port = port
                self.connection_start_dev = dev
                self.config(cursor='cross')
                self.redraw()
                return

        # Проверяем устройства
        dev = self._find_device_at(sx, sy)
        if dev:
            self.selected_device = dev
            self.redraw()
            self._show_device_menu(event, dev)
            return

        # Пустое место - меню добавления устройств
        self._show_add_menu(event, sx, sy)

    def _on_middle_click(self, event):
        """
        Средняя кнопка мыши - начало панорамирования.
        Сохраняем текущее смещение для расчета дельты.
        """
        self.is_panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.pan_offset_x = self.offset_x
        self.pan_offset_y = self.offset_y
        self.config(cursor='fleur')  # Курсор "перемещение"

    def _on_ctrl_click(self, event):
        """Ctrl+ЛКМ - тоже панорамирование (альтернативный способ)"""
        self._on_middle_click(event)

    def _on_left_drag(self, event):
        """
        Перетаскивание левой кнопкой мыши.
        - В режиме панорамирования: двигает канвас
        - В режиме перетаскивания: двигает устройство
        """
        if self.is_panning:
            # Панорамирование: смещаем канвас
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.offset_x = self.pan_offset_x + dx
            self.offset_y = self.pan_offset_y + dy
            self.redraw()
            return

        if self.is_dragging and self.drag_device:
            # Перемещение устройства
            sx, sy = self._to_scene(event.x, event.y)
            self.drag_device['x'] = sx - self.drag_start_x
            self.drag_device['y'] = sy - self.drag_start_y
            self.model.update_port_positions(self.drag_device)
            self.redraw()

    def _on_pan_drag(self, event):
        """Панорамирование средней или правой кнопкой"""
        if self.is_panning:
            dx = event.x - self.pan_start_x
            dy = event.y - self.pan_start_y
            self.offset_x = self.pan_offset_x + dx
            self.offset_y = self.pan_offset_y + dy
            self.redraw()

    def _on_double_click(self, event):
        """
        Двойной клик по устройству - открывает диалог редактирования.
        Можно изменить название, тип, категорию и порты.
        """
        sx, sy = self._to_scene(event.x, event.y)
        dev = self._find_device_at(sx, sy)
        if dev:
            self._edit_device(dev)

    def _on_wheel(self, event):
        """
        Колесико мыши (Windows) - масштабирование.
        delta > 0 = увеличение, delta < 0 = уменьшение.
        """
        self._zoom(event.delta / 120, event.x, event.y)

    def _on_wheel_up(self, event):
        """Колесико вверх (Linux) - увеличение"""
        self._zoom(1, event.x, event.y)

    def _on_wheel_down(self, event):
        """Колесико вниз (Linux) - уменьшение"""
        self._zoom(-1, event.x, event.y)

    def _zoom(self, direction: int, cx: int, cy: int):
        """
        Масштабирование относительно позиции курсора.
        Курсор остается на том же месте сцены при изменении масштаба.
        """
        factor = 1.1 if direction > 0 else 0.9
        new_scale = self.scale * factor

        if 0.1 <= new_scale <= 5.0:  # Ограничение масштаба
            # Корректируем смещение, чтобы точка под курсором осталась на месте
            self.offset_x = cx - (cx - self.offset_x) * factor
            self.offset_y = cy - (cy - self.offset_y) * factor
            self.scale = new_scale
            self.redraw()

    def _on_delete(self, event):
        """
        Клавиша Delete - удаляет выбранное устройство
        и все его соединения.
        """
        if self.selected_device:
            if messagebox.askyesno("Удаление",
                                   f"Удалить устройство '{self.selected_device['name']}'?"):
                self.model.remove_device(self.selected_device)
                self.selected_device = None
                self.redraw()

    def _on_escape(self, event):
        """
        Клавиша Escape - отменяет создание соединения.
        """
        if self.connection_start_port:
            self.connection_start_port = None
            self.connection_start_dev = None
            self.config(cursor='')
            self.redraw()

    # ========================================================
    # ДИАЛОГИ И МЕНЮ
    # ========================================================

    def _show_add_menu(self, event, sx: float, sy: float):
        """
        Показывает контекстное меню для добавления новых устройств.
        Устройства сгруппированы по категориям.
        """
        menu = tk.Menu(self, tearoff=0, bg='#313244', fg='#cdd6f4',
                       activebackground='#45475a', activeforeground='#ffffff')

        # Подменю для каждой категории
        categories = [
            ("Глобальные входные", [
                ("🌐 Магистральный кросс", "Main Cross-connect", "GLOBAL_INPUT"),
                ("🔗 Внешний кросс", "External Cross-connect", "GLOBAL_INPUT"),
            ]),
            ("Локальные входные", [
                ("🔌 Локальный кросс", "Local Cross-connect", "LOCAL_INPUT"),
                ("📋 Патч-панель", "Patch Panel", "LOCAL_INPUT"),
            ]),
            ("Коммутаторы", [
                ("⚡ Агрегатор", "Aggregator", "SWITCHES"),
                ("🔀 Коммутатор", "Switch", "SWITCHES"),
                ("🌍 Маршрутизатор", "Router", "SWITCHES"),
            ]),
            ("Серверы", [
                ("🖥 Сервер приложений", "Application Server", "SERVERS"),
                ("🗄 Сервер БД", "Database Server", "SERVERS"),
                ("📁 Файловый сервер", "File Server", "SERVERS"),
            ]),
        ]

        for cat_name, devices in categories:
            submenu = tk.Menu(menu, tearoff=0, bg='#313244', fg='#cdd6f4',
                              activebackground='#45475a')
            for name, dtype, cat in devices:
                submenu.add_command(
                    label=name,
                    command=lambda n=name, t=dtype, c=cat:
                    self.model.add_device(n, t, c, sx, sy)
                )
            menu.add_cascade(label=cat_name, menu=submenu)

        menu.post(event.x_root, event.y_root)

    def _show_device_menu(self, event, dev: dict):
        """
        Показывает контекстное меню для выбранного устройства.
        Позволяет редактировать, удалять устройство.
        """
        menu = tk.Menu(self, tearoff=0, bg='#313244', fg='#cdd6f4',
                       activebackground='#45475a', activeforeground='#ffffff')

        menu.add_command(
            label="✏️ Редактировать устройство",
            command=lambda: self._edit_device(dev)
        )
        menu.add_separator()
        menu.add_command(
            label="🗑️ Удалить устройство",
            command=lambda: (
                self.model.remove_device(dev),
                setattr(self, 'selected_device', None)
            )
        )
        menu.add_separator()
        menu.add_command(
            label="🔌 Добавить порт",
            command=lambda: self._add_port_dialog(dev)
        )

        menu.post(event.x_root, event.y_root)

    def _show_connection_dialog(self, dev1, port1, dev2, port2):
        """
        Показывает диалог настройки соединения.
        Позволяет выбрать тип кабеля, длину и группу.
        """
        dialog = tk.Toplevel(self, bg='#1e1e2e')
        dialog.title("Создание соединения")
        dialog.geometry("400x350")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Информация о соединении
        info = tk.Label(dialog,
                        text=f"Соединение:\n{dev1['name']}:{port1['name']}\n↓\n{dev2['name']}:{port2['name']}",
                        bg='#1e1e2e', fg='#cdd6f4', font=('Arial', 10))
        info.pack(pady=10)

        # Тип кабеля
        tk.Label(dialog, text="Тип кабеля:", bg='#1e1e2e', fg='#cdd6f4').pack()
        cable_var = tk.StringVar(value='Ethernet')
        cable_combo = ttk.Combobox(dialog, textvariable=cable_var,
                                   values=['Ethernet', 'Fiber Optic', 'Serial', 'Coaxial'],
                                   state='readonly')
        cable_combo.pack(pady=5)

        # Длина
        tk.Label(dialog, text="Длина (м):", bg='#1e1e2e', fg='#cdd6f4').pack()
        length_var = tk.DoubleVar(value=1.0)
        tk.Spinbox(dialog, textvariable=length_var, from_=0.1, to=1000.0,
                   increment=0.5).pack(pady=5)

        # Группа
        tk.Label(dialog, text="Группа:", bg='#1e1e2e', fg='#cdd6f4').pack(pady=(10, 0))
        group_var = tk.StringVar(value='Без группы')
        groups = ['Без группы'] + [g['name'] for g in self.model.groups] + ['+ Новая группа...']
        group_combo = ttk.Combobox(dialog, textvariable=group_var,
                                   values=groups, state='readonly')
        group_combo.pack(pady=5)

        # Поле для названия новой группы
        new_group_frame = tk.Frame(dialog, bg='#1e1e2e')
        new_group_var = tk.StringVar()
        tk.Entry(new_group_frame, textvariable=new_group_var, bg='#313244',
                 fg='#cdd6f4', insertbackground='#cdd6f4').pack(fill='x', padx=10)

        def on_group_change(*args):
            if group_var.get() == '+ Новая группа...':
                new_group_frame.pack(pady=5)
            else:
                new_group_frame.pack_forget()

        group_var.trace('w', on_group_change)

        # Кнопки
        btn_frame = tk.Frame(dialog, bg='#1e1e2e')
        btn_frame.pack(pady=15)

        def create():
            cable = cable_var.get()
            length = length_var.get()
            gs = group_var.get()

            if gs == '+ Новая группа...':
                name = new_group_var.get() or 'Новая группа'
                group = self.model.create_group(name)
                gid = group['id']
            elif gs == 'Без группы':
                gid = None
            else:
                group = next((g for g in self.model.groups if g['name'] == gs), None)
                gid = group['id'] if group else None

            self.model.add_connection(dev1, port1, dev2, port2, cable, length, gid)
            dialog.destroy()

        tk.Button(btn_frame, text="Создать", command=create,
                  bg='#89b4fa', fg='#1e1e2e', padx=20).pack(side='left', padx=5)
        tk.Button(btn_frame, text="Отмена", command=dialog.destroy,
                  bg='#45475a', fg='#cdd6f4', padx=20).pack(side='left', padx=5)

        self.wait_window(dialog)

    def _edit_device(self, dev: dict):
        """
        Диалог редактирования устройства.
        Позволяет изменить название, тип, категорию.
        """
        dialog = tk.Toplevel(self, bg='#1e1e2e')
        dialog.title(f"Редактирование: {dev['name']}")
        dialog.geometry("400x300")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        # Название
        tk.Label(dialog, text="Название:", bg='#1e1e2e', fg='#cdd6f4').pack(pady=(10, 0))
        name_var = tk.StringVar(value=dev['name'])
        tk.Entry(dialog, textvariable=name_var, bg='#313244', fg='#cdd6f4',
                 insertbackground='#cdd6f4').pack(fill='x', padx=20, pady=5)

        # Тип
        tk.Label(dialog, text="Тип устройства:", bg='#1e1e2e', fg='#cdd6f4').pack(pady=(10, 0))
        type_var = tk.StringVar(value=dev['type'])
        tk.Entry(dialog, textvariable=type_var, bg='#313244', fg='#cdd6f4',
                 insertbackground='#cdd6f4').pack(fill='x', padx=20, pady=5)

        # Категория
        tk.Label(dialog, text="Категория:", bg='#1e1e2e', fg='#cdd6f4').pack(pady=(10, 0))
        cat_var = tk.StringVar(value=dev.get('category', 'SWITCHES'))
        cat_combo = ttk.Combobox(dialog, textvariable=cat_var,
                                 values=['GLOBAL_INPUT', 'LOCAL_INPUT', 'SWITCHES', 'SERVERS'],
                                 state='readonly')
        cat_combo.pack(pady=5)

        # Кнопки
        btn_frame = tk.Frame(dialog, bg='#1e1e2e')
        btn_frame.pack(pady=15)

        def save():
            dev['name'] = name_var.get()
            dev['type'] = type_var.get()
            dev['category'] = cat_var.get()
            dialog.destroy()
            self.redraw()

        tk.Button(btn_frame, text="Сохранить", command=save,
                  bg='#89b4fa', fg='#1e1e2e', padx=20).pack(side='left', padx=5)
        tk.Button(btn_frame, text="Отмена", command=dialog.destroy,
                  bg='#45475a', fg='#cdd6f4', padx=20).pack(side='left', padx=5)

        self.wait_window(dialog)

    def _add_port_dialog(self, dev: dict):
        """
        Диалог добавления нового порта к устройству.
        Можно добавить входной или выходной порт.
        """
        dialog = tk.Toplevel(self, bg='#1e1e2e')
        dialog.title(f"Добавить порт к {dev['name']}")
        dialog.geometry("300x200")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        tk.Label(dialog, text="Тип порта:", bg='#1e1e2e', fg='#cdd6f4').pack(pady=(10, 0))
        port_type_var = tk.StringVar(value='input')
        ttk.Combobox(dialog, textvariable=port_type_var,
                     values=['input', 'output'], state='readonly').pack(pady=5)

        tk.Label(dialog, text="Название:", bg='#1e1e2e', fg='#cdd6f4').pack(pady=(10, 0))
        name_var = tk.StringVar(value=f"New {'IN' if port_type_var.get() == 'input' else 'OUT'}")
        tk.Entry(dialog, textvariable=name_var, bg='#313244', fg='#cdd6f4',
                 insertbackground='#cdd6f4').pack(fill='x', padx=20, pady=5)

        btn_frame = tk.Frame(dialog, bg='#1e1e2e')
        btn_frame.pack(pady=15)

        def add():
            port_type = port_type_var.get()
            port_name = name_var.get()
            port_id = len(dev['input_ports']) if port_type == 'input' else len(dev['output_ports'])

            new_port = {'id': port_id, 'name': port_name, 'type': port_type, 'x': 0, 'y': 0}

            if port_type == 'input':
                dev['input_ports'].append(new_port)
            else:
                dev['output_ports'].append(new_port)

            self.model.update_port_positions(dev)
            dialog.destroy()
            self.redraw()

        tk.Button(btn_frame, text="Добавить", command=add,
                  bg='#89b4fa', fg='#1e1e2e', padx=20).pack(side='left', padx=5)
        tk.Button(btn_frame, text="Отмена", command=dialog.destroy,
                  bg='#45475a', fg='#cdd6f4', padx=20).pack(side='left', padx=5)

        self.wait_window(dialog)


# ============================================================
# ПАНЕЛЬ ИНСТРУМЕНТОВ (левая панель)
# ============================================================

class ToolPanel(tk.Frame):
    """
    Левая панель с инструментами:
    - Поиск и фильтрация групп
    - Настройки отображения
    - Действия (сохранить, загрузить, создать канал)
    - Информация о выбранном элементе
    """

    def __init__(self, parent, model: NetworkModel, canvas: NetworkCanvas):
        super().__init__(parent, bg='#11111b', width=250)
        self.model = model
        self.canvas = canvas

        # Заголовок
        title = tk.Label(self, text="Панель инструментов", bg='#11111b', fg='#cdd6f4',
                         font=('Arial', 12, 'bold'))
        title.pack(pady=10)

        # ===== ФИЛЬТР ГРУПП =====
        filter_frame = tk.LabelFrame(self, text="🔍 Фильтр групп", bg='#1e1e2e', fg='#cdd6f4',
                                     font=('Arial', 10, 'bold'))
        filter_frame.pack(fill='x', padx=10, pady=5)

        self.filter_var = tk.StringVar()
        self.filter_var.trace('w', lambda *args: self.model.set_filter(self.filter_var.get()))
        tk.Entry(filter_frame, textvariable=self.filter_var, bg='#313244', fg='#cdd6f4',
                 insertbackground='#cdd6f4').pack(fill='x', padx=5, pady=5)

        self.filter_status = tk.Label(filter_frame, text="Показаны все соединения",
                                      bg='#1e1e2e', fg='#a6adc8', font=('Arial', 8))
        self.filter_status.pack(padx=5)

        tk.Button(filter_frame, text="✕ Очистить", bg='#45475a', fg='#cdd6f4',
                  command=lambda: self.filter_var.set('')).pack(pady=5)

        # ===== НАСТРОЙКИ ОТОБРАЖЕНИЯ =====
        display_frame = tk.LabelFrame(self, text="👁 Отображение", bg='#1e1e2e', fg='#cdd6f4',
                                      font=('Arial', 10, 'bold'))
        display_frame.pack(fill='x', padx=10, pady=5)

        self.show_grid_var = tk.BooleanVar(value=True)
        tk.Checkbutton(display_frame, text="Сетка", variable=self.show_grid_var,
                       bg='#1e1e2e', fg='#cdd6f4', selectcolor='#313244',
                       command=lambda: setattr(self.model, 'show_grid', self.show_grid_var.get())
                       ).pack(anchor='w', padx=10)

        self.show_ports_var = tk.BooleanVar(value=True)
        tk.Checkbutton(display_frame, text="Подписи портов", variable=self.show_ports_var,
                       bg='#1e1e2e', fg='#cdd6f4', selectcolor='#313244',
                       command=lambda: setattr(self.model, 'show_port_labels', self.show_ports_var.get())
                       ).pack(anchor='w', padx=10)

        self.show_conns_var = tk.BooleanVar(value=True)
        tk.Checkbutton(display_frame, text="Подписи соединений", variable=self.show_conns_var,
                       bg='#1e1e2e', fg='#cdd6f4', selectcolor='#313244',
                       command=lambda: setattr(self.model, 'show_connection_labels', self.show_conns_var.get())
                       ).pack(anchor='w', padx=10)

        # ===== ДЕЙСТВИЯ =====
        actions_frame = tk.LabelFrame(self, text="Действия", bg='#1e1e2e', fg='#cdd6f4',
                                      font=('Arial', 10, 'bold'))
        actions_frame.pack(fill='x', padx=10, pady=5)

        tk.Button(actions_frame, text="📊 Группы соединений", bg='#313244', fg='#cdd6f4',
                  command=self._show_groups_dialog).pack(fill='x', padx=5, pady=2)

        tk.Button(actions_frame, text="💾 Сохранить проект", bg='#313244', fg='#cdd6f4',
                  command=self._save_project).pack(fill='x', padx=5, pady=2)

        tk.Button(actions_frame, text="📂 Загрузить проект", bg='#313244', fg='#cdd6f4',
                  command=self._load_project).pack(fill='x', padx=5, pady=2)

        # ===== ИНФОРМАЦИЯ =====
        self.info_frame = tk.LabelFrame(self, text="Информация", bg='#1e1e2e', fg='#cdd6f4',
                                        font=('Arial', 10, 'bold'))
        self.info_frame.pack(fill='x', padx=10, pady=5)

        self.info_label = tk.Label(self.info_frame,
                                   text="ПКМ на канвасе - создать устройство\n"
                                        "Ctrl+ЛКМ - перемещать канвас\n"
                                        "ПКМ на порте - создать соединение",
                                   bg='#1e1e2e', fg='#a6adc8', font=('Arial', 8),
                                   justify='left')
        self.info_label.pack(padx=5, pady=5)

    def _show_groups_dialog(self):
        """Показывает диалог управления группами соединений"""
        dialog = tk.Toplevel(self, bg='#1e1e2e')
        dialog.title("Управление группами")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()

        # Поиск
        search_frame = tk.Frame(dialog, bg='#1e1e2e')
        search_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(search_frame, text="🔍 Поиск:", bg='#1e1e2e', fg='#cdd6f4').pack(side='left')
        search_var = tk.StringVar()
        tk.Entry(search_frame, textvariable=search_var, bg='#313244', fg='#cdd6f4',
                 insertbackground='#cdd6f4').pack(side='left', fill='x', expand=True, padx=5)

        # Список групп
        groups_frame = tk.Frame(dialog, bg='#1e1e2e')
        groups_frame.pack(fill='both', expand=True, padx=10)

        scrollbar = tk.Scrollbar(groups_frame)
        scrollbar.pack(side='right', fill='y')

        groups_list = tk.Listbox(groups_frame, bg='#313244', fg='#cdd6f4',
                                 yscrollcommand=scrollbar.set, font=('Arial', 10))
        groups_list.pack(fill='both', expand=True)
        scrollbar.config(command=groups_list.yview)

        def refresh_list():
            groups_list.delete(0, 'end')
            ft = search_var.get().lower()
            for g in self.model.groups:
                if not ft or ft in g['name'].lower():
                    conns = self.model.get_group_connections(g)
                    prefix = "✓" if g['visible'] else "✗"
                    groups_list.insert('end', f"{prefix} {g['name']} ({len(conns)} соед.)")

        search_var.trace('w', lambda *args: refresh_list())

        # Кнопки управления
        btn_frame = tk.Frame(dialog, bg='#1e1e2e')
        btn_frame.pack(fill='x', padx=10, pady=10)

        def toggle_visibility():
            sel = groups_list.curselection()
            if sel:
                text = groups_list.get(sel[0])
                name = text[2:].split(' (')[0]
                for g in self.model.groups:
                    if g['name'] == name:
                        g['visible'] = not g['visible']
                        refresh_list()
                        self.canvas.redraw()
                        break

        tk.Button(btn_frame, text="Скрыть/Показать", bg='#45475a', fg='#cdd6f4',
                  command=toggle_visibility).pack(side='left', padx=2)

        tk.Button(btn_frame, text="Удалить группу", bg='#f44336', fg='#ffffff',
                  command=lambda: self._delete_group(groups_list)).pack(side='left', padx=2)

        tk.Button(btn_frame, text="Закрыть", bg='#45475a', fg='#cdd6f4',
                  command=dialog.destroy).pack(side='right', padx=2)

        refresh_list()
        self.wait_window(dialog)

    def _delete_group(self, groups_list):
        """Удаление выбранной группы"""
        sel = groups_list.curselection()
        if sel:
            text = groups_list.get(sel[0])
            name = text[2:].split(' (')[0]
            for g in self.model.groups:
                if g['name'] == name:
                    if messagebox.askyesno("Удаление", f"Удалить группу '{name}'?"):
                        # Отвязываем соединения
                        for conn in self.model.connections:
                            if conn['group_id'] == g['id']:
                                conn['group_id'] = None
                        self.model.groups.remove(g)
                        self.canvas.redraw()
                        groups_list.delete(sel[0])
                    break

    def _save_project(self):
        """Сохранение проекта в JSON файл"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.model.to_dict(), f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Успех", "Проект сохранен")

    def _load_project(self):
        """Загрузка проекта из JSON файла"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.model.from_dict(json.load(f))
                messagebox.showinfo("Успех", "Проект загружен")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить: {e}")


# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================

class MainWindow(tk.Tk):
    """
    Главное окно приложения.
    Содержит панель инструментов слева и канвас справа.
    """

    def __init__(self):
        super().__init__()
        self.title("Network Visualizer")
        self.geometry("1400x900")
        self.configure(bg='#1e1e2e')

        # Модель данных
        self.model = NetworkModel()

        # Основной контейнер
        main_frame = tk.Frame(self, bg='#1e1e2e')
        main_frame.pack(fill='both', expand=True)

        # Панель инструментов (слева)
        self.canvas = NetworkCanvas(main_frame, self.model)
        self.tool_panel = ToolPanel(main_frame, self.model, self.canvas)
        self.tool_panel.pack(side='left', fill='y')

        # Канвас (справа)
        self.canvas.pack(side='left', fill='both', expand=True)

        # Статус бар
        status = tk.Label(self, text="ПКМ - меню | ПКМ на ■ + ЛКМ на ▼ = соединение | "
                                     "Ctrl+ЛКМ = панорама | Колесико = масштаб | Del = удалить",
                          bg='#313244', fg='#a6adc8', anchor='w', padx=10, pady=3)
        status.pack(side='bottom', fill='x')

        # Создаем демонстрационную сеть
        self._create_demo()

    def _create_demo(self):
        """
        Создает демонстрационную сеть с устройствами, соединениями и группами.
        """
        # Устройства
        main_cross = self.model.add_device("Магистральный кросс", "Main Cross-connect",
                                           "GLOBAL_INPUT", 200, 200)
        local_cross = self.model.add_device("Локальный кросс", "Local Cross-connect",
                                            "LOCAL_INPUT", 200, 500)
        switch1 = self.model.add_device("Агрегатор 1", "Aggregator", "SWITCHES", 600, 200)
        switch2 = self.model.add_device("Коммутатор 1", "Switch", "SWITCHES", 600, 500)
        server1 = self.model.add_device("Сервер приложений", "Application Server", "SERVERS", 1000, 150)
        server2 = self.model.add_device("Сервер БД", "Database Server", "SERVERS", 1000, 350)

        # Группы соединений
        g1 = self.model.create_group("Магистраль - Сервер приложений")
        g2 = self.model.create_group("Магистраль - Сервер БД")
        g3 = self.model.create_group("Резервный канал")

        # Соединения
        self.model.add_connection(main_cross, main_cross['output_ports'][0],
                                  local_cross, local_cross['input_ports'][0],
                                  'Fiber Optic', 50.0, g1['id'])
        self.model.add_connection(local_cross, local_cross['output_ports'][0],
                                  switch1, switch1['input_ports'][0],
                                  'Ethernet', 5.0, g1['id'])
        self.model.add_connection(switch1, switch1['output_ports'][0],
                                  server1, server1['input_ports'][0],
                                  'Ethernet', 2.0, g1['id'])

        self.model.add_connection(main_cross, main_cross['output_ports'][1],
                                  local_cross, local_cross['input_ports'][1],
                                  'Fiber Optic', 50.0, g2['id'])
        self.model.add_connection(local_cross, local_cross['output_ports'][1],
                                  switch2, switch2['input_ports'][0],
                                  'Ethernet', 5.0, g2['id'])
        self.model.add_connection(switch2, switch2['output_ports'][0],
                                  server2, server2['input_ports'][0],
                                  'Ethernet', 2.0, g2['id'])

        self.model.add_connection(switch1, switch1['output_ports'][1],
                                  switch2, switch2['input_ports'][1],
                                  'Fiber Optic', 3.0, g3['id'])

        self.canvas.redraw()


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == '__main__':
    app = MainWindow()
    app.mainloop()