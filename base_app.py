import sys
import json
import math
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from collections import defaultdict
import random


# ============== ENUMS ==============

class PortType(Enum):
    INPUT = "input"
    OUTPUT = "output"


class DeviceCategory(Enum):
    GLOBAL_INPUT = "Входные (глобальные)"
    LOCAL_INPUT = "Входные (локальные)"
    SWITCHES = "Коммутаторы"
    SERVERS = "Сервера"


# ============== DATA CLASSES ==============

@dataclass
class Port:
    id: int
    name: str
    port_type: PortType = PortType.OUTPUT
    x: float = 0.0
    y: float = 0.0


@dataclass
class Device:
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

    @property
    def ports(self) -> List[Port]:
        return self.input_ports + self.output_ports

    def add_default_ports(self):
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

    def update_port_positions(self):
        for i, port in enumerate(self.input_ports):
            port.x = self.x - self.width / 2
            count = len(self.input_ports)
            port.y = self.y - self.height / 2 + (i + 1) * (self.height / (count + 1)) if count > 1 else self.y

        for i, port in enumerate(self.output_ports):
            port.x = self.x + self.width / 2
            count = len(self.output_ports)
            port.y = self.y - self.height / 2 + (i + 1) * (self.height / (count + 1)) if count > 1 else self.y


@dataclass
class Connection:
    port1: Port
    port2: Port
    cable_type: str = "Ethernet"
    length: float = 1.0
    group_id: Optional[int] = None


@dataclass
class ConnectionGroup:
    id: int
    name: str
    color: str
    visible: bool = True


# ============== MODEL ==============

class NetworkModel:
    def __init__(self):
        self.devices: List[Device] = []
        self.connections: List[Connection] = []
        self.groups: List[ConnectionGroup] = []
        self.next_device_id = 0
        self.next_group_id = 0
        self.filter_text = ""
        self.show_port_labels = True
        self.show_connection_labels = True
        self.show_grid = True
        self._observers = []

    def add_observer(self, observer):
        self._observers.append(observer)

    def notify_observers(self):
        for obs in self._observers:
            obs()

    def add_device(self, device_type: str, category: DeviceCategory,
                   x: float = 100, y: float = 100) -> Device:
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
        self.connections = [
            c for c in self.connections
            if c.port1 not in device.ports and c.port2 not in device.ports
        ]
        self.devices.remove(device)
        self.notify_observers()

    def add_connection(self, port1: Port, port2: Port, cable_type: str = "Ethernet",
                       length: float = 1.0, group_id: Optional[int] = None) -> Optional[Connection]:
        for conn in self.connections:
            if (conn.port1 == port1 and conn.port2 == port2) or \
               (conn.port1 == port2 and conn.port2 == port1):
                return None

        if port1.port_type == PortType.OUTPUT and port2.port_type == PortType.INPUT:
            conn = Connection(port1, port2, cable_type, length, group_id)
        elif port2.port_type == PortType.OUTPUT and port1.port_type == PortType.INPUT:
            conn = Connection(port2, port1, cable_type, length, group_id)
        else:
            return None

        self.connections.append(conn)
        self.notify_observers()
        return conn

    def remove_connections_for_port(self, port: Port):
        self.connections = [c for c in self.connections if c.port1 != port and c.port2 != port]
        self.notify_observers()

    def create_group(self, name: str) -> ConnectionGroup:
        colors = ["#ff6464", "#64ff64", "#6464ff", "#ffff64", "#ff64ff", "#64ffff",
                  "#c89664", "#96c864", "#6496c8"]
        color = colors[self.next_group_id % len(colors)]
        group = ConnectionGroup(self.next_group_id, name, color)
        self.next_group_id += 1
        self.groups.append(group)
        self.notify_observers()
        return group

    def remove_group(self, group: ConnectionGroup):
        for conn in self.connections:
            if conn.group_id == group.id:
                conn.group_id = None
        if group in self.groups:
            self.groups.remove(group)
        self.notify_observers()

    def get_group(self, group_id: int) -> Optional[ConnectionGroup]:
        for group in self.groups:
            if group.id == group_id:
                return group
        return None

    def get_group_connections(self, group: ConnectionGroup) -> List[Connection]:
        return [c for c in self.connections if c.group_id == group.id]

    def find_device_by_port(self, port: Port) -> Optional[Device]:
        for device in self.devices:
            if port in device.ports:
                return device
        return None

    def get_visible_connections(self) -> List[Connection]:
        if not self.filter_text:
            return list(self.connections)

        visible_group_ids = set()
        for group in self.groups:
            if self.filter_text in group.name.lower():
                visible_group_ids.add(group.id)

        return [c for c in self.connections
                if c.group_id is None or c.group_id in visible_group_ids]

    def set_filter(self, text: str):
        self.filter_text = text.strip().lower()
        self.notify_observers()

    def move_device(self, device: Device, x: float, y: float):
        device.x = x
        device.y = y
        device.update_port_positions()
        self.notify_observers()

    def to_dict(self) -> dict:
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
            dev_data = {
                'id': device.id, 'name': device.name,
                'x': device.x, 'y': device.y,
                'width': device.width, 'height': device.height,
                'device_type': device.device_type,
                'category': device.category.value,
                'input_ports': [{'id': p.id, 'name': p.name} for p in device.input_ports],
                'output_ports': [{'id': p.id, 'name': p.name} for p in device.output_ports]
            }
            data['devices'].append(dev_data)

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
                device.input_ports.append(Port(id=p['id'], name=p['name'], port_type=PortType.INPUT))
            for p in dev_data.get('output_ports', []):
                device.output_ports.append(Port(id=p['id'], name=p['name'], port_type=PortType.OUTPUT))

            device.update_port_positions()
            self.devices.append(device)
            device_map[device.id] = device
            self.next_device_id = max(self.next_device_id, device.id + 1)

        for group_data in data.get('groups', []):
            group = ConnectionGroup(group_data['id'], group_data['name'],
                                   group_data['color'], group_data.get('visible', True))
            self.groups.append(group)
            self.next_group_id = max(self.next_group_id, group.id + 1)

        for conn_data in data['connections']:
            dev1 = device_map.get(conn_data['device1_id'])
            dev2 = device_map.get(conn_data['device2_id'])
            if dev1 and dev2:
                port1 = next((p for p in dev1.ports if p.id == conn_data['port1_id']), None)
                port2 = next((p for p in dev2.ports if p.id == conn_data['port2_id']), None)
                if port1 and port2:
                    conn = Connection(port1, port2, conn_data['cable_type'],
                                    conn_data['length'], conn_data.get('group_id'))
                    self.connections.append(conn)

        self.notify_observers()


# ============== VIEW ==============

class NetworkCanvas(tk.Canvas):
    def __init__(self, parent, model: NetworkModel, **kwargs):
        super().__init__(parent, bg='#f0f0f5', **kwargs)
        self.model = model
        self.model.add_observer(self.refresh)

        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.selected_device: Optional[Device] = None
        self.selected_port: Optional[Port] = None
        self.connection_mode = False
        self.dragging_device: Optional[Device] = None
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.drag_device_start_x = 0
        self.drag_device_start_y = 0
        self.panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.pan_offset_start_x = 0
        self.pan_offset_start_y = 0

        self._cable_colors = {
            "Ethernet": "#0064c8",
            "Fiber Optic": "#c86400",
            "Serial": "#646464",
            "Coaxial": "#009600"
        }

        self.bind("<Button-1>", self._on_click)
        self.bind("<Button-2>", self._on_middle_click)
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<B2-Motion>", self._on_pan)
        self.bind("<B3-Motion>", self._on_pan)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Control-Button-1>", self._on_ctrl_click)

    def to_canvas(self, x, y):
        return (x * self.scale + self.offset_x, y * self.scale + self.offset_y)

    def to_scene(self, cx, cy):
        return ((cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale)

    def refresh(self):
        self.delete("all")

        if self.model.show_grid:
            self._draw_grid()

        self._draw_connections()

        for device in self.model.devices:
            self._draw_device(device)

        if self.model.filter_text:
            self._draw_filter_indicator()

    def _draw_grid(self):
        grid_size = 50 * self.scale
        w, h = self.winfo_width(), self.winfo_height()

        for x in range(int(self.offset_x % grid_size), w, int(grid_size)):
            self.create_line(x, 0, x, h, fill='#dcdcdc', dash=(2, 4))
        for y in range(int(self.offset_y % grid_size), h, int(grid_size)):
            self.create_line(0, y, w, y, fill='#dcdcdc', dash=(2, 4))

    def _draw_connections(self):
        visible = self.model.get_visible_connections()

        grouped = defaultdict(list)
        for conn in visible:
            if conn.group_id is not None:
                group = self.model.get_group(conn.group_id)
                if group and group.visible:
                    grouped[conn.group_id].append(conn)

        # Draw group backgrounds
        for group_id, conns in grouped.items():
            if len(conns) > 1:
                group = self.model.get_group(group_id)
                if group:
                    self._draw_group_background(conns, group)

        # Draw connections
        for conn in visible:
            group = self.model.get_group(conn.group_id) if conn.group_id is not None else None
            if group and not group.visible:
                continue

            color = group.color if group else self._cable_colors.get(conn.cable_type, "#808080")
            self._draw_single_connection(conn, color, group.name if group else None)

    def _draw_group_background(self, connections, group):
        for conn in connections:
            x1, y1 = self.to_canvas(conn.port1.x, conn.port1.y)
            x2, y2 = self.to_canvas(conn.port2.x, conn.port2.y)
            self.create_line(x1, y1, x2, y2, fill=group.color,
                           width=5, capstyle=tk.ROUND)

    def _draw_single_connection(self, conn: Connection, color: str, group_name: Optional[str]):
        x1, y1 = self.to_canvas(conn.port1.x, conn.port1.y)
        x2, y2 = self.to_canvas(conn.port2.x, conn.port2.y)

        dash = ()
        if conn.cable_type == "Fiber Optic":
            dash = (8, 4)
        elif conn.cable_type == "Serial":
            dash = (2, 4)
        elif conn.cable_type == "Coaxial":
            dash = (8, 4, 2, 4)

        # Draw Bezier curve
        dx = abs(x2 - x1) * 0.4
        cx1, cy1 = x1 + dx, y1
        cx2, cy2 = x2 - dx, y2

        # Approximate Bezier with lines
        points = []
        for t in range(0, 21):
            t = t / 20.0
            px = (1-t)**3 * x1 + 3*(1-t)**2*t * cx1 + 3*(1-t)*t**2 * cx2 + t**3 * x2
            py = (1-t)**3 * y1 + 3*(1-t)**2*t * cy1 + 3*(1-t)*t**2 * cy2 + t**3 * y2
            points.extend([px, py])

        self.create_line(*points, fill=color, width=1, dash=dash, capstyle=tk.ROUND)

        # Arrow
        self._draw_arrow(x1, y1, x2, y2, cx1, cy1, cx2, cy2, color)

        # Label
        if self.model.show_connection_labels:
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2

            items = []
            if group_name:
                items.append(group_name)
            items.append(f"{conn.cable_type} | {conn.length:.1f}м")

            y_offset = mid_y - len(items) * 8
            for item in items:
                self.create_text(mid_x, y_offset, text=item, font=("Arial", 8),
                               fill="black", tags="label")
                y_offset += 16

    def _draw_arrow(self, x1, y1, x2, y2, cx1, cy1, cx2, cy2, color):
        t = 0.7
        ax = (1-t)**3 * x1 + 3*(1-t)**2*t * cx1 + 3*(1-t)*t**2 * cx2 + t**3 * x2
        ay = (1-t)**3 * y1 + 3*(1-t)**2*t * cy1 + 3*(1-t)*t**2 * cy2 + t**3 * y2

        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_size = 7

        p1x = ax + arrow_size * math.cos(angle)
        p1y = ay + arrow_size * math.sin(angle)
        p2x = ax + arrow_size * math.cos(angle + 2.5)
        p2y = ay + arrow_size * math.sin(angle + 2.5)
        p3x = ax + arrow_size * math.cos(angle - 2.5)
        p3y = ay + arrow_size * math.sin(angle - 2.5)

        self.create_polygon(p1x, p1y, p2x, p2y, p3x, p3y, fill=color, outline=color)

    def _draw_device(self, device: Device):
        x, y = self.to_canvas(device.x, device.y)
        w = device.width * self.scale
        h = device.height * self.scale

        colors = {
            DeviceCategory.GLOBAL_INPUT: ("#4682b4", "#00008b"),
            DeviceCategory.LOCAL_INPUT: ("#87ceeb", "#006496"),
            DeviceCategory.SWITCHES: ("#3cb371", "#006400"),
            DeviceCategory.SERVERS: ("#9370db", "#4b0082")
        }
        fill_color, border_color = colors.get(device.category, ("#808080", "#404040"))

        if device == self.selected_device:
            border_color = "#ffa500"

        # Device rectangle
        rect_id = self.create_rectangle(
            x - w/2, y - h/2, x + w/2, y + h/2,
            fill=fill_color, outline=border_color, width=2
        )

        # Title background
        self.create_rectangle(
            x - w/2, y - h/2, x + w/2, y - h/2 + 25,
            fill="#000000", stipple="gray50", outline=""
        )

        # Device name
        self.create_text(x, y - h/2 + 12, text=device.name,
                        fill="white", font=("Arial", 10, "bold"))

        # Device type
        self.create_text(x, y + h/2 - 12, text=device.device_type,
                        fill="white", font=("Arial", 7))

        # Draw ports
        for port in device.input_ports:
            self._draw_port(port, True)
        for port in device.output_ports:
            self._draw_port(port, False)

        # Store device reference
        self.tag_bind(rect_id, "<Button-1>", lambda e, d=device: self._select_device(e, d))
        self.tag_bind(rect_id, "<B1-Motion>", lambda e, d=device: self._drag_device(e, d))

    def _draw_port(self, port: Port, is_input: bool):
        px, py = self.to_canvas(port.x, port.y)
        size = 5

        is_connected = any(port in (c.port1, c.port2) for c in self.model.connections)

        if is_connected:
            color = "#00c800" if is_input else "#c89600"
        else:
            color = "#c8c8c8"

        outline = "red" if port == self.selected_port else "black"

        if is_input:
            self.create_polygon(
                px - size, py - size, px - size, py + size, px + size, py,
                fill=color, outline=outline,
                tags=("port", f"port_{port.id}")
            )
        else:
            self.create_rectangle(
                px - size, py - size, px + size, py + size,
                fill=color, outline=outline,
                tags=("port", f"port_{port.id}")
            )

        if self.model.show_port_labels:
            self.create_text(px, py - 15, text=port.name,
                           font=("Arial", 6), fill="black")

        # Bind port events
        self.tag_bind(f"port_{port.id}", "<Button-1>",
                     lambda e, p=port: self._on_port_click(e, p))
        self.tag_bind(f"port_{port.id}", "<Button-3>",
                     lambda e, p=port: self._on_port_right_click(e, p))

    def _draw_filter_indicator(self):
        visible = [g.name for g in self.model.groups if self.model.filter_text in g.name.lower()]
        text = f"🔍 Фильтр: '{self.model.filter_text}'"
        if visible:
            text += f" | {', '.join(visible)}"

        self.create_rectangle(10, 10, 310, 40, fill='white', outline='#ccc')
        self.create_text(15, 25, text=text, anchor='w', font=("Arial", 9, "bold"),
                        fill='#0064c8')

    def _find_port_at(self, cx, cy) -> Optional[Port]:
        sx, sy = self.to_scene(cx, cy)
        for device in self.model.devices:
            for port in device.ports:
                dx = sx - port.x
                dy = sy - port.y
                if dx * dx + dy * dy < 100:
                    return port
        return None

    def _find_device_at(self, cx, cy) -> Optional[Device]:
        sx, sy = self.to_scene(cx, cy)
        for device in reversed(self.model.devices):
            if abs(sx - device.x) < device.width / 2 and \
               abs(sy - device.y) < device.height / 2:
                return device
        return None

    def _on_click(self, event):
        if self.connection_mode:
            port = self._find_port_at(event.x, event.y)
            if port:
                self._finish_connection(port)
            else:
                self.connection_mode = False
                self.selected_port = None
            return

        port = self._find_port_at(event.x, event.y)
        if port:
            self.selected_port = port
            self.selected_device = self.model.find_device_by_port(port)
            self.refresh()
            return

        device = self._find_device_at(event.x, event.y)
        if device:
            self._select_device(event, device)
            return

        self.selected_device = None
        self.selected_port = None
        self.refresh()

    def _on_ctrl_click(self, event):
        self.panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.pan_offset_start_x = self.offset_x
        self.pan_offset_start_y = self.offset_y

    def _on_middle_click(self, event):
        self.panning = True
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.pan_offset_start_x = self.offset_x
        self.pan_offset_start_y = self.offset_y

    def _on_right_click(self, event):
        port = self._find_port_at(event.x, event.y)
        if port:
            self.connection_mode = True
            self.selected_port = port
            self.refresh()
            return

        self._show_context_menu(event)

    def _on_drag(self, event):
        if self.panning:
            self.offset_x = self.pan_offset_start_x + (event.x - self.pan_start_x)
            self.offset_y = self.pan_offset_start_y + (event.y - self.pan_start_y)
            self.refresh()
            return

        if self.dragging_device:
            sx, sy = self.to_scene(event.x, event.y)
            self.model.move_device(
                self.dragging_device,
                sx - self.drag_start_x,
                sy - self.drag_start_y
            )
            self.drag_start_x = sx - self.dragging_device.x
            self.drag_start_y = sy - self.dragging_device.y

    def _on_pan(self, event):
        if self.panning:
            self.offset_x = self.pan_offset_start_x + (event.x - self.pan_start_x)
            self.offset_y = self.pan_offset_start_y + (event.y - self.pan_start_y)
            self.refresh()

    def _on_double_click(self, event):
        device = self._find_device_at(event.x, event.y)
        if device:
            self._edit_device_dialog(device)

    def _on_wheel(self, event):
        sx, sy = self.to_scene(event.x, event.y)
        factor = 1.1 if event.delta > 0 else 0.9
        self.scale *= factor
        self.offset_x = event.x - sx * self.scale
        self.offset_y = event.y - sy * self.scale
        self.refresh()

    def _select_device(self, event, device: Device):
        self.selected_device = device
        self.selected_port = None
        self.connection_mode = False
        self.dragging_device = device
        sx, sy = self.to_scene(event.x, event.y)
        self.drag_start_x = sx - device.x
        self.drag_start_y = sy - device.y
        self.refresh()

    def _on_port_click(self, event, port: Port):
        self.selected_port = port
        self.selected_device = self.model.find_device_by_port(port)
        self.refresh()

    def _on_port_right_click(self, event, port: Port):
        self.connection_mode = True
        self.selected_port = port
        self.refresh()

    def _finish_connection(self, target_port: Port):
        if self.selected_port and self.selected_port != target_port:
            s_out = self.selected_port.port_type == PortType.OUTPUT
            t_in = target_port.port_type == PortType.INPUT

            if s_out and t_in:
                self._show_connection_dialog(self.selected_port, target_port)
            else:
                messagebox.showwarning("Ошибка",
                    "Соединение возможно только от выходного порта к входному!")

        self.connection_mode = False
        self.selected_port = None
        self.refresh()

    def _show_connection_dialog(self, port1: Port, port2: Port):
        dialog = ConnectionDialog(self.winfo_toplevel(), self.model, port1, port2)
        self.wait_window(dialog)

    def _show_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0)

        create_menu = tk.Menu(menu, tearoff=0)

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

        for cat_name, cat, devs in categories:
            sub = tk.Menu(create_menu, tearoff=0)
            for dname, dtype in devs:
                sx, sy = self.to_scene(event.x, event.y)
                sub.add_command(label=dname, command=lambda dt=dtype, c=cat, x=sx, y=sy:
                               self.model.add_device(dt, c, x, y))
            create_menu.add_cascade(label=cat_name, menu=sub)

        menu.add_cascade(label="Создать устройство", menu=create_menu)
        menu.add_separator()

        menu.add_command(label="🔗 Создать канал",
                        command=lambda: self._show_channel_dialog())
        menu.add_command(label="📊 Управление группами",
                        command=lambda: self._show_group_management())

        menu.add_separator()

        menu.add_command(label="🗑️ Удалить выбранное",
                        command=self._delete_selected)

        menu.post(event.x_root, event.y_root)

    def _edit_device_dialog(self, device: Device):
        dialog = DeviceEditDialog(self.winfo_toplevel(), self.model, device)
        self.wait_window(dialog)

    def _show_channel_dialog(self):
        dialog = ChannelCreationDialog(self.winfo_toplevel(), self.model)
        self.wait_window(dialog)

    def _show_group_management(self):
        dialog = GroupManagementDialog(self.winfo_toplevel(), self.model)
        self.wait_window(dialog)

    def _delete_selected(self):
        if self.selected_device:
            if messagebox.askyesno("Удаление",
                                  f"Удалить устройство '{self.selected_device.name}'?"):
                self.model.remove_device(self.selected_device)
                self.selected_device = None
                self.refresh()
        elif self.selected_port:
            self.model.remove_connections_for_port(self.selected_port)
            self.selected_port = None
            self.refresh()


# ============== DIALOGS ==============

class DeviceEditDialog(tk.Toplevel):
    def __init__(self, parent, model: NetworkModel, device: Device):
        super().__init__(parent)
        self.model = model
        self.device = device
        self.title(f"Редактирование: {device.name}")
        self.geometry("500x500")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.input_edits = []
        self.output_edits = []

        self._setup_ui()
        self.wait_window()

    def _setup_ui(self):
        # Name
        ttk.Label(self, text="Название:").pack(pady=(10, 0))
        self.name_var = tk.StringVar(value=self.device.name)
        ttk.Entry(self, textvariable=self.name_var).pack(fill='x', padx=10)

        # Type
        ttk.Label(self, text="Тип:").pack(pady=(10, 0))
        self.type_var = tk.StringVar(value=self.device.device_type)
        ttk.Entry(self, textvariable=self.type_var).pack(fill='x', padx=10)

        # Category
        ttk.Label(self, text="Категория:").pack(pady=(10, 0))
        self.category_var = tk.StringVar(value=self.device.category.value)
        combo = ttk.Combobox(self, textvariable=self.category_var,
                            values=[c.value for c in DeviceCategory])
        combo.pack(fill='x', padx=10)

        # Ports frame
        ports_frame = ttk.Frame(self)
        ports_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Input ports
        in_frame = ttk.LabelFrame(ports_frame, text="Входные порты")
        in_frame.pack(side='left', fill='both', expand=True, padx=5)

        in_canvas = tk.Canvas(in_frame, height=200)
        in_scroll = ttk.Scrollbar(in_frame, orient='vertical', command=in_canvas.yview)
        in_content = ttk.Frame(in_canvas)
        in_canvas.create_window((0, 0), window=in_content, anchor='nw')
        in_canvas.configure(yscrollcommand=in_scroll.set)

        for port in self.device.input_ports:
            self._add_port_row(in_content, port, self.input_edits, True)

        ttk.Button(in_frame, text="+ Добавить",
                  command=lambda: self._add_new_port(in_content, True)).pack()

        in_canvas.pack(side='left', fill='both', expand=True)
        in_scroll.pack(side='right', fill='y')

        # Output ports
        out_frame = ttk.LabelFrame(ports_frame, text="Выходные порты")
        out_frame.pack(side='right', fill='both', expand=True, padx=5)

        out_canvas = tk.Canvas(out_frame, height=200)
        out_scroll = ttk.Scrollbar(out_frame, orient='vertical', command=out_canvas.yview)
        out_content = ttk.Frame(out_canvas)
        out_canvas.create_window((0, 0), window=out_content, anchor='nw')
        out_canvas.configure(yscrollcommand=out_scroll.set)

        for port in self.device.output_ports:
            self._add_port_row(out_content, port, self.output_edits, False)

        ttk.Button(out_frame, text="+ Добавить",
                  command=lambda: self._add_new_port(out_content, False)).pack()

        out_canvas.pack(side='left', fill='both', expand=True)
        out_scroll.pack(side='right', fill='y')

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=10)
        ttk.Button(btn_frame, text="Сохранить", command=self._save).pack(side='right', padx=5)
        ttk.Button(btn_frame, text="Отмена", command=self.destroy).pack(side='right')

    def _add_port_row(self, parent, port: Port, edit_list: list, is_input: bool):
        frame = ttk.Frame(parent)
        frame.pack(fill='x', pady=2)

        var = tk.StringVar(value=port.name)
        ttk.Entry(frame, textvariable=var, width=15).pack(side='left', padx=2)

        label = ttk.Label(frame, text="▼ IN" if is_input else "■ OUT",
                         foreground="green" if is_input else "orange")
        label.pack(side='left', padx=2)

        ttk.Button(frame, text="×", width=2,
                  command=lambda f=frame, p=port, el=edit_list:
                  self._remove_port(f, p, el)).pack(side='right')

        frame._port = port
        frame._var = var
        edit_list.append(frame)

    def _add_new_port(self, parent, is_input: bool):
        max_id = max((p.id for p in self.device.ports), default=-1)
        new_port = Port(
            id=max_id + 1,
            name=f"New {'IN' if is_input else 'OUT'}",
            port_type=PortType.INPUT if is_input else PortType.OUTPUT
        )

        if is_input:
            self.device.input_ports.append(new_port)
            self._add_port_row(parent, new_port, self.input_edits, True)
        else:
            self.device.output_ports.append(new_port)
            self._add_port_row(parent, new_port, self.output_edits, False)

    def _remove_port(self, frame, port: Port, edit_list: list):
        has_conn = any(port in (c.port1, c.port2) for c in self.model.connections)

        if has_conn:
            if not messagebox.askyesno("Удаление порта",
                                      f"Порт '{port.name}' имеет соединения. Удалить?"):
                return
            self.model.remove_connections_for_port(port)

        if port in self.device.input_ports:
            self.device.input_ports.remove(port)
        elif port in self.device.output_ports:
            self.device.output_ports.remove(port)

        edit_list.remove(frame)
        frame.destroy()

    def _save(self):
        self.device.name = self.name_var.get()
        self.device.device_type = self.type_var.get()
        self.device.category = DeviceCategory(self.category_var.get())

        for frame in self.input_edits:
            if hasattr(frame, '_port') and hasattr(frame, '_var'):
                frame._port.name = frame._var.get()

        for frame in self.output_edits:
            if hasattr(frame, '_port') and hasattr(frame, '_var'):
                frame._port.name = frame._var.get()

        self.device.update_port_positions()
        self.model.notify_observers()
        self.destroy()


class ConnectionDialog(tk.Toplevel):
    def __init__(self, parent, model: NetworkModel, port1: Port, port2: Port):
        super().__init__(parent)
        self.model = model
        self.port1 = port1
        self.port2 = port2
        self.title("Создание соединения")
        self.geometry("400x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self.wait_window()

    def _setup_ui(self):
        dev1 = self.model.find_device_by_port(self.port1)
        dev2 = self.model.find_device_by_port(self.port2)

        ttk.Label(self, text=f"Соединение:\n{dev1.name} : {self.port1.name}\n↓\n"
                            f"{dev2.name} : {self.port2.name}",
                 font=("Arial", 10)).pack(pady=10)

        # Cable type
        ttk.Label(self, text="Тип кабеля:").pack()
        self.cable_var = tk.StringVar(value="Ethernet")
        ttk.Combobox(self, textvariable=self.cable_var,
                    values=["Ethernet", "Fiber Optic", "Serial", "Coaxial"]).pack()

        # Length
        ttk.Label(self, text="Длина (м):").pack()
        self.length_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(self, textvariable=self.length_var, from_=0.1, to=1000.0,
                   increment=0.1).pack()

        # Group
        ttk.Label(self, text="Группа:").pack(pady=(10, 0))
        self.group_var = tk.StringVar(value="Без группы")
        groups = ["Без группы"] + [f"{g.name} ({len(self.model.get_group_connections(g))})"
                                   for g in self.model.groups] + ["+ Новая группа..."]
        combo = ttk.Combobox(self, textvariable=self.group_var, values=groups)
        combo.pack()
        combo.bind('<<ComboboxSelected>>', self._on_group_select)

        # New group name
        self.new_group_frame = ttk.Frame(self)
        self.new_name_var = tk.StringVar()
        ttk.Entry(self.new_group_frame, textvariable=self.new_name_var).pack(fill='x')

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="OK", command=self._ok).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Отмена", command=self.destroy).pack(side='left', padx=5)

    def _on_group_select(self, event):
        if self.group_var.get() == "+ Новая группа...":
            self.new_group_frame.pack(pady=5)
        else:
            self.new_group_frame.pack_forget()

    def _ok(self):
        ct = self.cable_var.get()
        l = self.length_var.get()
        gs = self.group_var.get()

        if gs == "+ Новая группа...":
            name = self.new_name_var.get() or "Новая группа"
            group = self.model.create_group(name)
            gid = group.id
        elif gs == "Без группы":
            gid = None
        else:
            gname = gs.split(" (")[0]
            group = next((g for g in self.model.groups if g.name == gname), None)
            gid = group.id if group else None

        self.model.add_connection(self.port1, self.port2, ct, l, gid)
        self.destroy()


class ChannelCreationDialog(tk.Toplevel):
    def __init__(self, parent, model: NetworkModel):
        super().__init__(parent)
        self.model = model
        self.title("Создание канала связи")
        self.geometry("600x500")
        self.transient(parent)
        self.grab_set()

        self.route_devices = []
        self._setup_ui()
        self.wait_window()

    def _setup_ui(self):
        # Channel name
        ttk.Label(self, text="Название канала:").pack(pady=(10, 0))
        self.name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.name_var, width=50).pack()

        # Route frame
        route_frame = ttk.LabelFrame(self, text="Маршрут канала")
        route_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.route_list = tk.Listbox(route_frame, height=10)
        self.route_list.pack(fill='both', expand=True, padx=5, pady=5)

        btn_frame = ttk.Frame(route_frame)
        btn_frame.pack(fill='x', padx=5)

        ttk.Button(btn_frame, text="➕ Начальное",
                  command=lambda: self._add_device(is_start=True)).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="➕ Промежуточное",
                  command=self._add_device).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="➕ Конечное",
                  command=lambda: self._add_device(is_end=True)).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="➖ Удалить",
                  command=self._remove_device).pack(side='left', padx=2)

        # Cable params
        ttk.Label(self, text="Тип кабеля:").pack()
        self.cable_var = tk.StringVar(value="Ethernet")
        ttk.Combobox(self, textvariable=self.cable_var,
                    values=["Ethernet", "Fiber Optic", "Serial", "Coaxial"]).pack()

        ttk.Label(self, text="Длина сегмента (м):").pack()
        self.length_var = tk.DoubleVar(value=2.0)
        ttk.Spinbox(self, textvariable=self.length_var, from_=0.1, to=1000.0,
                   increment=0.1).pack()

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Создать", command=self._create).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Отмена", command=self.destroy).pack(side='left', padx=5)

    def _add_device(self, is_start=False, is_end=False):
        devices = self.model.devices
        if not devices:
            messagebox.showwarning("Внимание", "Нет устройств на схеме")
            return

        # Simple device selector
        selector = tk.Toplevel(self)
        selector.title("Выберите устройство")
        selector.geometry("300x400")
        selector.transient(self)
        selector.grab_set()

        lb = tk.Listbox(selector)
        lb.pack(fill='both', expand=True, padx=10, pady=10)

        for d in devices:
            lb.insert(tk.END, f"{d.name} ({d.device_type})")

        result = [None]

        def select():
            sel = lb.curselection()
            if sel:
                result[0] = devices[sel[0]]
                selector.destroy()

        ttk.Button(selector, text="Выбрать", command=select).pack(pady=10)

        self.wait_window(selector)

        if result[0]:
            device = result[0]
            self.route_devices.append(device)
            prefix = ""
            if is_start:
                prefix = "Старт: "
            elif is_end:
                prefix = "Конец: "
            else:
                prefix = "Пром: "
            self.route_list.insert(tk.END, f"{prefix}{device.name}")

    def _remove_device(self):
        sel = self.route_list.curselection()
        if sel:
            idx = sel[0]
            self.route_list.delete(idx)
            del self.route_devices[idx]

    def _create(self):
        if len(self.route_devices) < 2:
            messagebox.showwarning("Ошибка", "Добавьте минимум 2 устройства")
            return

        name = self.name_var.get() or "Новый канал"
        ct = self.cable_var.get()
        l = self.length_var.get()

        group = self.model.create_group(name)

        success = 0
        for i in range(len(self.route_devices) - 1):
            d1 = self.route_devices[i]
            d2 = self.route_devices[i + 1]

            # Use first available ports
            out_port = None
            for p in d1.output_ports:
                if not any(p in (c.port1, c.port2) for c in self.model.connections):
                    out_port = p
                    break

            in_port = None
            for p in d2.input_ports:
                if not any(p in (c.port1, c.port2) for c in self.model.connections):
                    in_port = p
                    break

            if out_port and in_port:
                if self.model.add_connection(out_port, in_port, ct, l, group.id):
                    success += 1

        messagebox.showinfo("Успех", f"Канал создан! Соединений: {success}")
        self.destroy()


class GroupManagementDialog(tk.Toplevel):
    def __init__(self, parent, model: NetworkModel):
        super().__init__(parent)
        self.model = model
        self.title("Управление группами")
        self.geometry("600x400")
        self.transient(parent)
        self.grab_set()

        self._setup_ui()
        self._refresh_list()
        self.wait_window()

    def _setup_ui(self):
        # Search
        search_frame = ttk.Frame(self)
        search_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(search_frame, text="🔍 Поиск:").pack(side='left')
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._refresh_list())
        ttk.Entry(search_frame, textvariable=self.search_var).pack(side='left', fill='x',
                                                                   expand=True, padx=5)

        # Group list
        self.group_list = tk.Listbox(self)
        self.group_list.pack(fill='both', expand=True, padx=10)
        self.group_list.bind('<<ListboxSelect>>', self._on_select)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(btn_frame, text="Переименовать",
                  command=self._rename).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Скрыть/Показать",
                  command=self._toggle).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Показать все",
                  command=self._show_all).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Удалить",
                  command=self._delete).pack(side='left', padx=2)
        ttk.Button(btn_frame, text="Закрыть",
                  command=self.destroy).pack(side='right', padx=2)

    def _refresh_list(self):
        self.group_list.delete(0, tk.END)
        ft = self.search_var.get().strip().lower()

        for group in self.model.groups:
            if not ft or ft in group.name.lower():
                conns = self.model.get_group_connections(group)
                prefix = "✓" if group.visible else "✗"
                self.group_list.insert(tk.END, f"{prefix} {group.name} ({len(conns)} соед.)")

    def _on_select(self, event):
        pass

    def _get_selected(self) -> Optional[ConnectionGroup]:
        sel = self.group_list.curselection()
        if sel:
            text = self.group_list.get(sel[0])
            name = text.split(" (")[0][2:]  # Remove prefix
            for g in self.model.groups:
                if g.name == name:
                    return g
        return None

    def _rename(self):
        group = self._get_selected()
        if group:
            new_name = simpledialog.askstring("Переименовать", "Новое название:",
                                             initialvalue=group.name, parent=self)
            if new_name:
                group.name = new_name
                self._refresh_list()

    def _toggle(self):
        group = self._get_selected()
        if group:
            group.visible = not group.visible
            self._refresh_list()
            self.model.notify_observers()

    def _show_all(self):
        for g in self.model.groups:
            g.visible = True
        self._refresh_list()
        self.model.notify_observers()

    def _delete(self):
        group = self._get_selected()
        if group:
            if messagebox.askyesno("Удаление", f"Удалить группу '{group.name}'?"):
                self.model.remove_group(group)
                self._refresh_list()


# ============== MAIN WINDOW ==============

class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Network Visualizer")
        self.geometry("1400x900")

        self.model = NetworkModel()

        self._setup_ui()
        self._setup_menu()

        self._create_demo_network()

    def _setup_ui(self):
        # PanedWindow for split
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill='both', expand=True)

        # Left panel
        left_panel = ttk.Frame(paned, width=250)
        paned.add(left_panel, weight=0)

        # Filter
        filter_frame = ttk.LabelFrame(left_panel, text="🔍 Фильтр групп")
        filter_frame.pack(fill='x', padx=5, pady=5)

        self.filter_var = tk.StringVar()
        self.filter_var.trace('w', lambda *args: self.model.set_filter(self.filter_var.get()))
        ttk.Entry(filter_frame, textvariable=self.filter_var).pack(fill='x', padx=5, pady=5)
        ttk.Button(filter_frame, text="✕ Очистить",
                  command=lambda: self.filter_var.set("")).pack(pady=5)

        # Display settings
        disp_frame = ttk.LabelFrame(left_panel, text="👁 Отображение")
        disp_frame.pack(fill='x', padx=5, pady=5)

        self.show_ports_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(disp_frame, text="Подписи портов", variable=self.show_ports_var,
                       command=lambda: setattr(self.model, 'show_port_labels',
                                              self.show_ports_var.get())).pack(anchor='w', padx=5)

        self.show_conns_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(disp_frame, text="Подписи соединений", variable=self.show_conns_var,
                       command=lambda: setattr(self.model, 'show_connection_labels',
                                              self.show_conns_var.get())).pack(anchor='w', padx=5)

        self.show_grid_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(disp_frame, text="Сетка", variable=self.show_grid_var,
                       command=lambda: setattr(self.model, 'show_grid',
                                              self.show_grid_var.get())).pack(anchor='w', padx=5)

        # Actions
        act_frame = ttk.LabelFrame(left_panel, text="Действия")
        act_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(act_frame, text="🔗 Создать канал",
                  command=self._create_channel).pack(fill='x', padx=5, pady=2)
        ttk.Button(act_frame, text="📊 Группы соединений",
                  command=self._manage_groups).pack(fill='x', padx=5, pady=2)
        ttk.Button(act_frame, text="💾 Сохранить",
                  command=self._save).pack(fill='x', padx=5, pady=2)
        ttk.Button(act_frame, text="📂 Загрузить",
                  command=self._load).pack(fill='x', padx=5, pady=2)
        ttk.Button(act_frame, text="🗑️ Удалить",
                  command=self._delete).pack(fill='x', padx=5, pady=2)

        # Canvas
        self.canvas = NetworkCanvas(paned, self.model)
        paned.add(self.canvas, weight=1)

        # Status bar
        self.status_var = tk.StringVar(value="ПКМ на канвасе - создать устройство | "
                                            "Ctrl+ЛКМ - перемещать | ПКМ на порте - соединение")
        status = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN)
        status.pack(fill='x', side='bottom')

    def _setup_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Новый проект", command=self._new_project,
                             accelerator="Ctrl+N")
        file_menu.add_command(label="Сохранить", command=self._save,
                             accelerator="Ctrl+S")
        file_menu.add_command(label="Загрузить", command=self._load,
                             accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.quit,
                             accelerator="Ctrl+Q")

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Правка", menu=edit_menu)
        edit_menu.add_command(label="Создать канал...", command=self._create_channel)
        edit_menu.add_command(label="Удалить выбранное", command=self._delete)
        edit_menu.add_command(label="Управление группами...", command=self._manage_groups)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_checkbutton(label="Подписи портов", variable=self.show_ports_var)
        view_menu.add_checkbutton(label="Подписи соединений", variable=self.show_conns_var)
        view_menu.add_checkbutton(label="Сетка", variable=self.show_grid_var)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Помощь", menu=help_menu)
        help_menu.add_command(label="О программе", command=self._show_about)

        # Keyboard shortcuts
        self.bind("<Control-n>", lambda e: self._new_project())
        self.bind("<Control-s>", lambda e: self._save())
        self.bind("<Control-o>", lambda e: self._load())
        self.bind("<Control-q>", lambda e: self.quit())
        self.bind("<Delete>", lambda e: self._delete())

    def _create_demo_network(self):
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

        for p1, p2, ct, l, gid in connections:
            self.model.add_connection(p1, p2, ct, l, gid)

    def _create_channel(self):
        ChannelCreationDialog(self, self.model)

    def _manage_groups(self):
        GroupManagementDialog(self, self.model)

    def _delete(self):
        self.canvas._delete_selected()

    def _save(self):
        filename = filedialog.asksaveasfilename(defaultextension=".json",
                                               filetypes=[("JSON", "*.json")])
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.model.to_dict(), f, indent=2, ensure_ascii=False)
            self.status_var.set(f"Сохранено: {filename}")

    def _load(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.model.from_dict(json.load(f))
                self.status_var.set(f"Загружено: {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    def _new_project(self):
        if messagebox.askyesno("Новый проект", "Создать новый проект?"):
            self.model = NetworkModel()
            self.canvas.model = self.model
            self.model.add_observer(self.canvas.refresh)
            self.canvas.refresh()

    def _show_about(self):
        messagebox.showinfo("О программе",
                           "Network Infrastructure Visualizer\n\n"
                           "Визуализация сетевой инфраструктуры\n"
                           "• Архитектура MVC (Tkinter)\n"
                           "• Контекстное меню для создания устройств\n"
                           "• Панорамирование (Ctrl+ЛКМ)\n"
                           "• Создание каналов с маршрутизацией\n"
                           "• Группировка соединений\n"
                           "• Сохранение/загрузка проектов")


def main():
    app = MainWindow()
    app.mainloop()


if __name__ == '__main__':
    main()