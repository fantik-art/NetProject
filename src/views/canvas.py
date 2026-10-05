"""Канвас отрисовки и взаимодействия."""

import math
from collections import defaultdict
from typing import Optional, Tuple

from PyQt6.QtWidgets import QWidget, QMenu, QMessageBox
from PyQt6.QtGui import (
    QPainter, QPainterPath, QPen, QBrush, QColor,
    QFont, QPolygonF, QAction,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF

from models.network import NetworkModel
from models.device import Device
from models.port import Port
from models.connection import Connection, ConnectionGroup
from models.enums import PortType, DeviceCategory, CATEGORY_KEY_MAP
from config.templates import DEVICE_TEMPLATES
from config.constants import (
    CANVAS_BG_COLOR, CANVAS_GRID_COLOR, CANVAS_GRID_SIZE,
    CATEGORY_COLORS, CABLE_COLORS, CABLE_STYLES, CONNECTOR_COLORS,
    SPEED_WIDTH_MAP, CABLE_GROUP_BG_ALPHA, CABLE_GROUP_BG_WIDTH,
    PORT_SIZE, PORT_HIT_RADIUS, PORT_LABEL_FONT_SIZE, PORT_LABEL_OFFSET,
    SELECTED_BORDER_COLOR, PORT_SELECTED_COLOR, PORT_OUTLINE_COLOR,
    CABLE_LABEL_FONT_SIZE, CABLE_LABEL_WIDTH, CABLE_LABEL_LINE_HEIGHT,
    ARROW_SIZE, TEMP_CONNECTION_COLOR, TEMP_CONNECTION_WIDTH,
    FILTER_INDICATOR_BG, FILTER_INDICATOR_BORDER, FILTER_INDICATOR_TEXT,
    ZOOM_MIN, ZOOM_MAX, ZOOM_STEP,CABLE_HIT_TOLERANCE,
    CABLE_SELECTED_COLOR,
    CABLE_SELECTED_EXTRA_WIDTH,
    PORT_HIGHLIGHT_COLOR,
    PORT_HIGHLIGHT_SIZE,
)


class NetworkCanvas(QWidget):
    """
    Канвас сети: отрисовка, взаимодействие мышью.

    Сигналы:
        device_selected — выбрано устройство
        device_edited   — двойной клик по устройству
        device_deleted  — удалить устройство
        connection_requested — запрос на соединение
        channel_requested — запрос на создание канала
        groups_requested  — запрос на управление группами
    """

    device_selected = pyqtSignal(object)
    device_edited = pyqtSignal(object)
    device_deleted = pyqtSignal(object)
    connection_requested = pyqtSignal(object, object)
    channel_requested = pyqtSignal()
    groups_requested = pyqtSignal()
    connection_deleted = pyqtSignal(object)

    def __init__(self, model: NetworkModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self.model.data_changed.connect(self.update)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(600, 400)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAutoFillBackground(True)

        # Камера
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        # Взаимодействие
        self.selected_device: Optional[Device] = None
        self.selected_port: Optional[Port] = None
        self.selected_connection: Optional[Connection] = None
        self.connection_mode = False
        self.dragging_device: Optional[Device] = None
        self.drag_offset = QPointF()

        self.panning = False
        self.pan_start = QPointF()
        self.pan_offset_start = QPointF()

    # ========================================================
    #  КООРДИНАТЫ
    # ========================================================

    def to_canvas(self, x: float, y: float) -> Tuple[float, float]:
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y

    def to_scene(self, cx: float, cy: float) -> Tuple[float, float]:
        return (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale

    # ========================================================
    #  ОТРИСОВКА
    # ========================================================

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(self.rect(), QColor(CANVAS_BG_COLOR))

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

    def _draw_grid(self, painter: QPainter) -> None:
        pen = QPen(QColor(CANVAS_GRID_COLOR), 1)
        pen.setCosmetic(True)
        painter.setPen(pen)

        left, top = self.to_scene(0, 0)
        right, bottom = self.to_scene(self.width(), self.height())

        grid = CANVAS_GRID_SIZE
        x = int(left // grid) * grid
        while x < right:
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))
            x += grid

        y = int(top // grid) * grid
        while y < bottom:
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            y += grid

    def _draw_temp_connection(self, painter: QPainter) -> None:
        if not self.selected_port:
            return

        cursor_pos = self.mapFromGlobal(self.cursor().pos())
        sx, sy = self.to_scene(cursor_pos.x(), cursor_pos.y())

        pen = QPen(QColor(TEMP_CONNECTION_COLOR), TEMP_CONNECTION_WIDTH)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(
            QPointF(self.selected_port.x, self.selected_port.y),
            QPointF(sx, sy),
        )

    def _draw_connections(self, painter: QPainter) -> None:
        visible = self.model.get_visible_connections()

        grouped = defaultdict(list)
        for c in visible:
            if c.group_id is not None:
                g = self.model.get_group(c.group_id)
                if g and g.visible:
                    grouped[c.group_id].append(c)

        # Фон групп
        for gid, conns in grouped.items():
            if len(conns) > 1:
                g = self.model.get_group(gid)
                if g:
                    self._draw_group_background(painter, conns, g)

        # Отдельные соединения
        for c in visible:
            group = self.model.get_group(c.group_id) if c.group_id else None
            if group and not group.visible:
                continue

            color = group.color if group else CABLE_COLORS.get(
                c.cable_type, "#9ca3af"
            )
            self._draw_single_connection(
                painter, c, color, group.name if group else None,
            )

    def _draw_group_background(self, painter: QPainter,
                                connections: list,
                                group: ConnectionGroup) -> None:
        color = QColor(group.color)
        color.setAlpha(CABLE_GROUP_BG_ALPHA)

        pen = QPen(color, CABLE_GROUP_BG_WIDTH)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        for c in connections:
            painter.drawPath(self._bezier_path(c.port1, c.port2))

    @staticmethod
    def _bezier_path(port1: Port, port2: Port) -> QPainterPath:
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
                                group_name: Optional[str]) -> None:
        """Рисует одно соединение с подсветкой если выделено."""
        is_selected = conn is self.selected_connection

        # Толщина по скорости
        speed = conn.port1.speed if conn.port1.speed == conn.port2.speed \
            else max(conn.port1.speed, conn.port2.speed)
        width = SPEED_WIDTH_MAP.get(speed, 2.0)

        # ✅ Если выделено — добавляем толщину и красный цвет
        if is_selected:
            color = CABLE_SELECTED_COLOR
            width += CABLE_SELECTED_EXTRA_WIDTH

        pen = QPen(QColor(color), width)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        if CABLE_STYLES.get(conn.cable_type) == "dash":
            pen.setStyle(Qt.PenStyle.DashLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)

        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._bezier_path(conn.port1, conn.port2))

        self._draw_arrow(painter, conn.port1, conn.port2, color)

        if self.model.show_connection_labels:
            self._draw_connection_label(painter, conn, group_name)

    def _draw_arrow(self, painter: QPainter,
                    port1: Port, port2: Port, color: str) -> None:
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
        s = ARROW_SIZE

        p1 = QPointF(ax + s * math.cos(angle), ay + s * math.sin(angle))
        p2 = QPointF(ax + s * math.cos(angle + 2.5), ay + s * math.sin(angle + 2.5))
        p3 = QPointF(ax + s * math.cos(angle - 2.5), ay + s * math.sin(angle - 2.5))

        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([p1, p2, p3]))

    def _draw_connection_label(self, painter: QPainter,
                                conn: Connection,
                                group_name: Optional[str]) -> None:
        mx = (conn.port1.x + conn.port2.x) / 2
        my = (conn.port1.y + conn.port2.y) / 2

        items = []
        if group_name:
            items.append(group_name)
        items.append(f"{conn.cable_type}  ·  {conn.length:.1f} м")

        font = QFont("Arial")
        font.setPointSizeF(CABLE_LABEL_FONT_SIZE)
        painter.setFont(font)

        lh = CABLE_LABEL_LINE_HEIGHT
        th = len(items) * lh
        lw = CABLE_LABEL_WIDTH

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.drawRoundedRect(
            QRectF(mx - lw / 2, my - th / 2, lw, th), 3, 3,
        )

        painter.setPen(QColor("#1f2937"))
        for i, item in enumerate(items):
            y = my - th / 2 + (i + 1) * lh
            painter.drawText(
                QRectF(mx - lw / 2, y - lh, lw, lh),
                Qt.AlignmentFlag.AlignCenter, item,
            )

    def _draw_device(self, painter: QPainter, device: Device) -> None:
        cat_key = CATEGORY_KEY_MAP.get(device.category, "SWITCHES")
        fill_color, border_color = CATEGORY_COLORS.get(
            cat_key, ("#808080", "#404040")
        )

        if device == self.selected_device:
            border_color = SELECTED_BORDER_COLOR

        w, h = device.width, device.height
        hh, fh = device.HEADER_HEIGHT, device.FOOTER_HEIGHT

        # Тело
        rect = QRectF(device.x - w / 2, device.y - h / 2, w, h)
        pen = QPen(QColor(border_color), 2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(fill_color)))
        painter.drawRoundedRect(rect, 6, 6)

        # Заголовок
        header = QRectF(device.x - w / 2, device.y - h / 2, w, hh)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 150)))
        painter.drawRect(header)

        painter.setPen(QColor("white"))
        font = QFont("Arial")
        font.setPointSizeF(9.5)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(header, Qt.AlignmentFlag.AlignCenter, device.name)

        # Подпись снизу
        footer = QRectF(device.x - w / 2, device.y + h / 2 - fh, w, fh)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 0, 0, 60)))
        painter.drawRect(footer)

        painter.setPen(QColor(255, 255, 255, 230))
        font.setPointSizeF(6.5)
        font.setBold(False)
        painter.setFont(font)

        type_text = device.device_type
        if device.model:
            type_text += f"  ·  {device.model}"

        painter.drawText(footer, Qt.AlignmentFlag.AlignCenter, type_text)

        # Порты
        for port in device.input_ports:
            self._draw_port(painter, port, is_input=True)
        for port in device.output_ports:
            self._draw_port(painter, port, is_input=False)

    def _draw_port(self, painter: QPainter, port: Port, is_input: bool) -> None:
        size = PORT_SIZE
        is_conn = self.model.is_port_connected(port)
        connector_color = CONNECTOR_COLORS.get(port.connector, "#9ca3af")

        # ✅ Проверяем, принадлежит ли порт выделенному соединению
        is_in_selected_conn = (
                self.selected_connection is not None and
                port in (self.selected_connection.port1, self.selected_connection.port2)
        )

        # ✅ Подсветка портов выделенного соединения
        if is_in_selected_conn:
            highlight_pen = QPen(QColor(PORT_HIGHLIGHT_COLOR), 3)
            highlight_pen.setCosmetic(True)
            painter.setPen(highlight_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(
                QPointF(port.x, port.y),
                PORT_HIGHLIGHT_SIZE,
                PORT_HIGHLIGHT_SIZE,
            )

        base = QColor(connector_color)
        if is_conn:
            base = base.darker(115)
            outline = "#047857"
        else:
            outline = PORT_OUTLINE_COLOR

        if port == self.selected_port:
            pen = QPen(QColor(PORT_SELECTED_COLOR), 2)
        else:
            pen = QPen(QColor(outline), 1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(base))

        if is_input:
            painter.drawPolygon(QPolygonF([
                QPointF(port.x - size, port.y - size),
                QPointF(port.x - size, port.y + size),
                QPointF(port.x + size, port.y),
            ]))
        else:
            painter.drawRect(QRectF(
                port.x - size, port.y - size, size * 2, size * 2,
            ))

        # Подпись — читаемая, с фоном
        if self.model.show_port_labels:
            painter.setPen(QColor("#1f2937"))
            font = QFont("Arial")
            font.setPointSizeF(PORT_LABEL_FONT_SIZE)
            font.setBold(True)
            painter.setFont(font)

            label = port.label()

            metrics = painter.fontMetrics()
            text_w = metrics.horizontalAdvance(label) + 8
            text_h = metrics.height() + 2

            if is_input:
                lx = port.x - PORT_LABEL_OFFSET - text_w
            else:
                lx = port.x + PORT_LABEL_OFFSET

            ly = port.y - text_h / 2

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
            painter.drawRoundedRect(
                QRectF(lx - 2, ly, text_w + 4, text_h), 3, 3,
            )

            painter.setPen(QColor("#1f2937"))
            painter.drawText(
                QRectF(lx, ly, text_w, text_h),
                Qt.AlignmentFlag.AlignCenter, label,
            )

    def _draw_filter_indicator(self, painter: QPainter) -> None:
        painter.save()
        painter.resetTransform()

        visible = [
            g.name for g in self.model.groups
            if self.model.filter_text in g.name.lower()
        ]
        text = f"🔍 Фильтр: «{self.model.filter_text}»"
        if visible:
            text += f"  ·  {', '.join(visible)}"

        rect = QRectF(12, 12, 420, 32)
        painter.setPen(QPen(QColor(FILTER_INDICATOR_BORDER), 1))
        painter.setBrush(QBrush(QColor(*FILTER_INDICATOR_BG)))
        painter.drawRoundedRect(rect, 6, 6)

        painter.setPen(QColor(FILTER_INDICATOR_TEXT))
        font = QFont("Arial", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(12, 0, -12, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text,
        )
        painter.restore()

    # ========================================================
    #  ПОИСК ЭЛЕМЕНТОВ
    # ========================================================

    def _find_port_at(self, cx: float, cy: float) -> Optional[Port]:
        sx, sy = self.to_scene(cx, cy)
        for device in self.model.devices:
            for port in device.ports:
                dx = sx - port.x
                dy = sy - port.y
                if dx * dx + dy * dy < PORT_HIT_RADIUS ** 2:
                    return port
        return None

    def _find_device_at(self, cx: float, cy: float) -> Optional[Device]:
        sx, sy = self.to_scene(cx, cy)
        for device in reversed(self.model.devices):
            if (abs(sx - device.x) < device.width / 2 and
                    abs(sy - device.y) < device.height / 2):
                return device
        return None

    def _find_connection_at(self, cx: float, cy: float) -> Optional[Connection]:
        """
        Находит соединение, ближайшее к указанной точке.

        Использует аппроксимацию кривой Безье: проверяет расстояние
        от точки до нескольких сегментов кривой.

        Args:
            cx, cy: координаты в системе сцены

        Returns:
            Connection или None
        """
        sx, sy = self.to_scene(cx, cy)

        closest_conn = None
        closest_dist = CABLE_HIT_TOLERANCE

        for conn in self.model.get_visible_connections():
            # Пропускаем невидимые группы
            if conn.group_id is not None:
                group = self.model.get_group(conn.group_id)
                if group and not group.visible:
                    continue

            # Проверяем расстояние до кривой Безье
            dist = self._point_to_bezier_distance(
                sx, sy, conn.port1, conn.port2
            )

            if dist < closest_dist:
                closest_dist = dist
                closest_conn = conn

        return closest_conn

    def _point_to_bezier_distance(self, px: float, py: float,
                                  port1: Port, port2: Port) -> float:
        """
        Вычисляет минимальное расстояние от точки до кривой Безье,
        аппроксимируя кривую ломаной из N сегментов.

        Args:
            px, py: координаты точки
            port1, port2: порты, задающие кривую

        Returns:
            Минимальное расстояние в единицах сцены
        """
        x1, y1 = port1.x, port1.y
        x2, y2 = port2.x, port2.y
        dx = abs(x2 - x1) * 0.4
        cx1, cy1 = x1 + dx, y1
        cx2, cy2 = x2 - dx, y2

        segments = 20
        min_dist = float("inf")

        for i in range(segments):
            t1 = i / segments
            t2 = (i + 1) / segments

            p1 = self._bezier_point(t1, x1, y1, cx1, cy1, cx2, cy2, x2, y2)
            p2 = self._bezier_point(t2, x1, y1, cx1, cy1, cx2, cy2, x2, y2)

            d = self._point_to_segment_distance(px, py, p1[0], p1[1], p2[0], p2[1])
            if d < min_dist:
                min_dist = d

        return min_dist

    @staticmethod
    def _bezier_point(t: float, x1, y1, cx1, cy1, cx2, cy2, x2, y2) -> tuple:
        """Возвращает точку на кривой Безье для параметра t."""
        x = ((1 - t) ** 3 * x1 + 3 * (1 - t) ** 2 * t * cx1 +
             3 * (1 - t) * t ** 2 * cx2 + t ** 3 * x2)
        y = ((1 - t) ** 3 * y1 + 3 * (1 - t) ** 2 * t * cy1 +
             3 * (1 - t) * t ** 2 * cy2 + t ** 3 * y2)
        return x, y

    @staticmethod
    def _point_to_segment_distance(px: float, py: float,
                                   x1: float, y1: float,
                                   x2: float, y2: float) -> float:
        """Расстояние от точки до отрезка."""
        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy

        if length_sq == 0:
            return math.hypot(px - x1, py - y1)

        # Проекция точки на отрезок (t в [0, 1])
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy

        return math.hypot(px - proj_x, py - proj_y)

    # ========================================================
    #  СОБЫТИЯ МЫШИ
    # ========================================================

    def mousePressEvent(self, event) -> None:
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

        if event.button() == Qt.MouseButton.RightButton:
            self._on_right_click(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self._on_left_click(event, sx, sy)
            return

    def _on_right_click(self, event) -> None:
        pos = event.position()
        port = self._find_port_at(pos.x(), pos.y())

        if port:
            if self.model.is_port_connected(port):
                dev = self.model.find_device_by_port(port)
                name = dev.name if dev else "?"
                QMessageBox.warning(
                    self, "Порт занят",
                    f"Порт «{port.name}» ({name}) уже используется.",
                )
                return

            if port.port_type != PortType.OUTPUT:
                QMessageBox.information(
                    self, "Неверный порт",
                    f"Порт «{port.name}» — входной.\n"
                    f"Начните с ВЫХОДНОГО порта (■).",
                )
                return

            self.connection_mode = True
            self.selected_port = port
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.update()
        else:
            self._show_context_menu(event)

    def _on_left_click(self, event, sx: float, sy: float) -> None:
        """Обработка клика ЛКМ с учётом выделения соединений."""
        # 1. Режим соединения — завершаем
        if self.connection_mode:
            port = self._find_port_at(event.position().x(),
                                      event.position().y())
            if port:
                self._finish_connection(port)
            else:
                self._cancel_connection()
            return

        # 2. Клик по порту — приоритет
        port = self._find_port_at(event.position().x(),
                                  event.position().y())
        if port:
            self.selected_port = port
            self.selected_device = self.model.find_device_by_port(port)
            self.selected_connection = None
            self.update()
            return

        # 3. Клик по устройству
        device = self._find_device_at(event.position().x(),
                                      event.position().y())
        if device:
            self.selected_device = device
            self.selected_port = None
            self.selected_connection = None
            self.dragging_device = device
            self.drag_offset = QPointF(sx - device.x, sy - device.y)
            self.device_selected.emit(device)
            self.update()
            return

        # 4. ✅ Клик по соединению
        conn = self._find_connection_at(event.position().x(),
                                        event.position().y())
        if conn:
            self.selected_connection = conn
            self.selected_device = None
            self.selected_port = None
            self.update()
            return

        # 5. Клик по пустому месту — снимаем выделение
        self.selected_device = None
        self.selected_port = None
        self.selected_connection = None
        self.update()

    def mouseMoveEvent(self, event) -> None:
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
                sy - self.drag_offset.y(),
            )
            return

        if self.connection_mode:
            self.update()

        if not self.dragging_device and not self.panning:
            conn = self._find_connection_at(pos.x(), pos.y())
            if conn and not self._find_port_at(pos.x(), pos.y()) \
                    and not self._find_device_at(pos.x(), pos.y()):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.panning:
                self.panning = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
            self.dragging_device = None

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            device = self._find_device_at(event.position().x(),
                                           event.position().y())
            if device:
                self.device_edited.emit(device)

    def wheelEvent(self, event) -> None:
        pos = event.position()
        sx, sy = self.to_scene(pos.x(), pos.y())

        factor = ZOOM_STEP if event.angleDelta().y() > 0 else 1 / ZOOM_STEP
        new_scale = self.scale * factor

        if ZOOM_MIN <= new_scale <= ZOOM_MAX:
            self.scale = new_scale
            self.offset_x = pos.x() - sx * self.scale
            self.offset_y = pos.y() - sy * self.scale
            self.update()

    def keyPressEvent(self, event) -> None:
        """Обработка клавиш."""
        if event.key() == Qt.Key.Key_Delete:
            # ✅ Удаление выделенного соединения
            if self.selected_connection:
                self._delete_selected_connection()
                return
            # Удаление устройства
            if self.selected_device:
                self.device_deleted.emit(self.selected_device)
                return
        elif event.key() == Qt.Key.Key_Escape:
            self._cancel_connection()
            # Сброс выделения
            self.selected_device = None
            self.selected_port = None
            self.selected_connection = None
            self.update()

    def _delete_selected_connection(self) -> None:
        """Удаляет выделенное соединение (без подтверждения при Delete)."""
        if not self.selected_connection:
            return
        conn = self.selected_connection
        self.selected_connection = None
        self.connection_deleted.emit(conn)

    # ========================================================
    #  СОЕДИНЕНИЯ
    # ========================================================

    def _finish_connection(self, target_port: Port) -> None:
        if not self.selected_port or self.selected_port == target_port:
            self._cancel_connection()
            return

        ok, error = self.model.can_connect(self.selected_port, target_port)
        if not ok:
            QMessageBox.warning(self, "Невозможно соединить", error)
            self._cancel_connection()
            return

        self.connection_requested.emit(self.selected_port, target_port)
        self._cancel_connection()

    def _cancel_connection(self) -> None:
        self.connection_mode = False
        self.selected_port = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    # ========================================================
    #  КОНТЕКСТНОЕ МЕНЮ
    # ========================================================

    def _show_context_menu(self, event) -> None:
        pos = event.position()
        sx, sy = self.to_scene(pos.x(), pos.y())

        # ✅ Проверяем, кликнули ли по соединению
        conn_under_cursor = self._find_connection_at(pos.x(), pos.y())

        menu = QMenu(self)

        if conn_under_cursor:
            # ✅ Контекстное меню для соединения
            self.selected_connection = conn_under_cursor
            self.selected_device = None
            self.selected_port = None
            self.update()

            # Информация о соединении
            group = (self.model.get_group(conn_under_cursor.group_id)
                     if conn_under_cursor.group_id else None)

            info_action = menu.addAction(
                f"🔌 {conn_under_cursor.cable_type} · "
                f"{conn_under_cursor.length:.1f} м"
            )
            info_action.setEnabled(False)

            if group:
                grp_action = menu.addAction(f"📦 Группа: {group.name}")
                grp_action.setEnabled(False)

            menu.addSeparator()

            # Копировать стиль группы (заглушка — можно расширить)
            # ...

            # Удалить соединение
            del_conn_action = menu.addAction("🗑️ Удалить соединение")
            del_conn_action.triggered.connect(self._delete_selected)

            menu.exec(event.globalPosition().toPoint())
            return

        # === Стандартное контекстное меню для пустого места ===

        create_menu = menu.addMenu("➕ Создать устройство")

        from collections import defaultdict
        groups = defaultdict(list)
        for name, tpl in DEVICE_TEMPLATES.items():
            groups[tpl["category"]].append(name)

        cat_titles = {
            "GLOBAL_INPUT": "Глобальные входные",
            "LOCAL_INPUT": "Локальные входные",
            "SWITCHES": "Коммутаторы",
            "SERVERS": "Сервера",
        }

        for cat_key, templates in groups.items():
            sub = create_menu.addMenu(cat_titles.get(cat_key, cat_key))
            for tpl_name in templates:
                action = sub.addAction(tpl_name)
                action.triggered.connect(
                    lambda checked=False, n=tpl_name, x=sx, y=sy:
                    self._create_device_at(n, x, y)
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

    def _create_device_at(self, template_name: str, x: float, y: float) -> None:
        device = self.model.add_device_from_template(template_name, x, y)
        if device:
            self.selected_device = device
            self.update()

    def _delete_selected(self) -> None:
        """Удаляет выбранный элемент (устройство/порт/соединение)."""
        if self.selected_device:
            reply = QMessageBox.question(
                self, "Удаление",
                f"Удалить устройство «{self.selected_device.name}»?\n"
                f"Все его соединения также будут удалены.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.device_deleted.emit(self.selected_device)
                self.selected_device = None
                self.update()

        elif self.selected_port:
            # Удаляем все соединения порта
            connections = [
                c for c in self.model.connections
                if c.port1 is self.selected_port or c.port2 is self.selected_port
            ]
            if connections:
                reply = QMessageBox.question(
                    self, "Удаление соединений",
                    f"У порта «{self.selected_port.name}» "
                    f"{len(connections)} соединений.\nУдалить все?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            self.model.remove_connections_for_port(self.selected_port)
            self.selected_port = None
            self.update()

        elif self.selected_connection:
            # ✅ Удаление соединения с подтверждением
            conn = self.selected_connection
            group = self.model.get_group(conn.group_id) if conn.group_id else None
            text = f"{conn.cable_type}  ·  {conn.length:.1f} м"
            if group:
                text = f"«{group.name}»\n{text}"

            reply = QMessageBox.question(
                self, "Удаление соединения",
                f"Удалить соединение?\n\n{text}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.selected_connection = None
                self.connection_deleted.emit(conn)