from PyQt6.QtWidgets import QWidget, QMenu, QInputDialog
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QPainter, QPainterPath, QPen, QBrush, QColor,
    QFont, QPolygonF, QAction
)
import math
from typing import Optional, List, Dict


class CanvasWidget(QWidget):
    """Канвас для отображения и редактирования сетевой топологии"""

    # Сигналы
    device_moved = pyqtSignal(int, float, float)
    device_added = pyqtSignal(dict)
    device_deleted = pyqtSignal(int)
    device_edited = pyqtSignal(dict)
    connection_requested = pyqtSignal(int, int, int, int)
    sector_changed = pyqtSignal(dict)
    zoom_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # ===== СОСТОЯНИЕ СЕТИ =====
        self.devices: List[dict] = []
        self.connections: List[dict] = []
        self.groups: List[dict] = []
        self.sectors: List[dict] = []

        # ===== РЕЖИМ ПРОСМОТРА =====
        self.view_mode = 'single'
        self.visible_sector_ids: List[int] = []
        self.show_sector_bounds = True
        self.is_editable = True

        # ===== ВЫДЕЛЕНИЕ =====
        self.selected_device_id: Optional[int] = None
        self.selected_port: Optional[dict] = None
        self.selected_device: Optional[dict] = None

        # ===== СОЗДАНИЕ СОЕДИНЕНИЙ =====
        self.connection_mode = False
        self.connection_start_device: Optional[dict] = None
        self.connection_start_port: Optional[dict] = None

        # ===== КАМЕРА =====
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.panning = False
        self.pan_start = QPointF()
        self.pan_offset_start = QPointF()

        # ===== ПЕРЕТАСКИВАНИЕ УСТРОЙСТВ =====
        self.dragging = False
        self.drag_device_id: Optional[int] = None
        self.drag_offset = QPointF()

        # ===== РЕДАКТИРОВАНИЕ СЕКТОРОВ =====
        self.sector_edit_mode = False
        self.dragging_sector_id: Optional[int] = None
        self.resizing_sector_id: Optional[int] = None
        self.resize_handle: Optional[str] = None
        self.sector_drag_offset = QPointF()
        self.sector_resize_start: Optional[dict] = None

        # ===== ЦВЕТА =====
        self.category_colors = {
            'GLOBAL_INPUT': QColor('#4682b4'),
            'LOCAL_INPUT': QColor('#87ceeb'),
            'SWITCHES': QColor('#3cb371'),
            'SERVERS': QColor('#9370db')
        }

        self.cable_colors = {
            'Ethernet': QColor('#0064c8'),
            'Fiber Optic': QColor('#c86400'),
            'Serial': QColor('#646464'),
            'Coaxial': QColor('#009600')
        }

        # ===== КОНСТАНТЫ =====
        self.DEVICE_W = 160
        self.DEVICE_H = 100
        self.PORT_SIZE = 5
        self.GRID = 50
        self.HANDLE_SIZE = 12

    # ============================================================
    #  ЗАГРУЗКА ДАННЫХ
    # ============================================================

    def load_state(self, state: dict):
        self.devices = state.get('devices', [])
        self.connections = state.get('connections', [])
        self.groups = state.get('groups', [])
        self.sectors = state.get('sectors', [])
        self.view_mode = state.get('view_mode', 'single')
        self.visible_sector_ids = state.get('sector_ids', [])
        self.show_sector_bounds = state.get('settings', {}).get('show_sector_bounds', True)
        self.selected_device_id = None
        self.selected_port = None
        self.selected_device = None
        self.update()

    def apply_changes(self, changes: list):
        for ch in changes:
            t = ch.get('type', '')
            d = ch.get('device', {})
            c = ch.get('connection', {})
            if 'DEVICE_DELETE' in t:
                self.devices = [x for x in self.devices if x.get('id') != d.get('id')]
            elif 'DEVICE' in t:
                self._upsert(d)
            elif 'CONNECTION_ADD' in t:
                if not self._conn_exists(c):
                    self.connections.append(c)
            elif 'CONNECTION_DELETE' in t:
                self.connections = [x for x in self.connections if not self._conn_eq(x, c)]
        self.update()

    def clear(self):
        self.devices.clear()
        self.connections.clear()
        self.groups.clear()
        self.sectors.clear()
        self.selected_device_id = None
        self.selected_port = None
        self.selected_device = None
        self.update()

    def set_editable(self, v: bool):
        self.is_editable = v
        self.update()

    # ============================================================
    #  ДОБАВЛЕНИЕ УСТРОЙСТВ
    # ============================================================

    def add_device_at(self, x: float, y: float, dtype: str = "Device", cat: str = "SWITCHES") -> dict:
        did = max([d.get('id', 0) for d in self.devices], default=0) + 1
        dev = {
            'id': did, 'name': f"{dtype} {did}", 'device_type': dtype,
            'category': cat, 'x': x, 'y': y,
            'width': self.DEVICE_W, 'height': self.DEVICE_H,
            'sector_ids': list(self.visible_sector_ids) if self.visible_sector_ids else [],
            'input_ports': self._gen_ports('input', x, y),
            'output_ports': self._gen_ports('output', x, y)
        }
        self.devices.append(dev)
        self.device_added.emit(dev)
        self.update()
        return dev

    def _gen_ports(self, pt: str, x: float, y: float, n: int = 4) -> list:
        ports = []
        inp = pt == 'input'
        for i in range(n):
            px = x - self.DEVICE_W / 2 if inp else x + self.DEVICE_W / 2
            py = y - self.DEVICE_H / 2 + (i + 1) * (self.DEVICE_H / (n + 1)) if n > 1 else y
            ports.append({'id': len(ports), 'name': f"{'IN' if inp else 'OUT'}{i + 1}",
                          'port_type': pt, 'x': px, 'y': py})
        return ports

    # ============================================================
    #  ОТРИСОВКА
    # ============================================================

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor('#1e1e2e'))

        p.save()
        p.translate(self.offset_x, self.offset_y)
        p.scale(self.scale, self.scale)

        self._grid(p)
        if self.show_sector_bounds:
            self._sectors(p)
        self._connections(p)
        if self.connection_mode and self.connection_start_port:
            self._temp_conn(p)
        for d in self.devices:
            self._device(p, d)
        if self.sector_edit_mode:
            self._sector_handles(p)

        p.restore()

        if not self.is_editable:
            self._readonly(p)
        if self.connection_mode:
            self._hint(p, "🔗 Режим соединения: ЛКМ на входном порту (▼) | Esc - отмена")
        if self.sector_edit_mode:
            self._hint(p, "✏️ Режим секторов: тяните за ■ ручки | перетаскивайте | Esc - выход")

    def _grid(self, p: QPainter):
        p.setPen(QPen(QColor('#313244'), 0.3))
        w, h = int(self.width() / self.scale) + 200, int(self.height() / self.scale) + 200
        for x in range(-200, w, self.GRID):
            p.drawLine(x, -200, x, h)
        for y in range(-200, h, self.GRID):
            p.drawLine(-200, y, w, y)

    def _sectors(self, p: QPainter):
        for s in self.sectors:
            b = s.get('bounds', {})
            if not b:
                continue
            x, y, w, h = b.get('x', 0), b.get('y', 0), b.get('width', 800), b.get('height', 600)
            col = QColor(s.get('color', '#45475a'))
            cur = s.get('is_current', False)

            # Фон
            p.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 30 if cur else 12)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(x, y, w, h))

            # Рамка
            if self.sector_edit_mode:
                pen = QPen(QColor('#f9e2af'), 2, Qt.PenStyle.DashLine)
            else:
                pen = QPen(col, 3 if cur else 1.5,
                           Qt.PenStyle.SolidLine if cur else Qt.PenStyle.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(x, y, w, h))

            # Заголовок
            p.setPen(QColor('#cdd6f4'))
            f = QFont('Arial', 11 if cur else 9, QFont.Weight.Bold if cur else QFont.Weight.Normal)
            p.setFont(f)
            title = s.get('name', '')
            if cur and not self.sector_edit_mode:
                title = f"▶ {title}"
            if self.sector_edit_mode:
                title = f"✏️ {title}"
            p.drawText(QRectF(x + 10, y + 5, w - 60, 25), Qt.AlignmentFlag.AlignLeft, title)

            # Размер в режиме редактирования
            if self.sector_edit_mode:
                f = QFont('Arial', 8)
                p.setFont(f)
                p.setPen(QColor('#a6adc8'))
                p.drawText(QRectF(x + w - 120, y + 5, 110, 25), Qt.AlignmentFlag.AlignRight,
                           f"{int(w)}×{int(h)}")

            # Блокировка
            if s.get('is_locked'):
                p.drawText(QRectF(x + w - 50, y + 5, 40, 25), Qt.AlignmentFlag.AlignRight, "🔒")

            # Счетчик устройств
            if not self.sector_edit_mode:
                f = QFont('Arial', 8)
                p.setFont(f)
                p.setPen(QColor('#a6adc8'))
                p.drawText(QRectF(x + w - 100, y + 5, 90, 25), Qt.AlignmentFlag.AlignRight,
                           f"🔌 {len(s.get('device_ids', []))}")

    def _sector_handles(self, p: QPainter):
        """Ручки редактирования секторов"""
        for s in self.sectors:
            b = s.get('bounds', {})
            if not b:
                continue
            x, y, w, h = b.get('x', 0), b.get('y', 0), b.get('width', 800), b.get('height', 600)
            hs = self.HANDLE_SIZE
            col = QColor('#f9e2af')
            p.setBrush(QBrush(col))
            p.setPen(QPen(QColor('#1e1e2e'), 1))

            # 8 ручек
            for cx, cy in [(x, y), (x + w, y), (x, y + h), (x + w, y + h),  # углы
                           (x + w / 2, y), (x + w / 2, y + h), (x, y + h / 2), (x + w, y + h / 2)]:  # середины
                p.drawRect(QRectF(cx - hs / 2, cy - hs / 2, hs, hs))

    def _connections(self, p: QPainter):
        for c in self.connections:
            d1 = self._fdev(c.get('device1_id'))
            d2 = self._fdev(c.get('device2_id'))
            if not d1 or not d2:
                continue

            x1, y1 = self._ppos(d1, c.get('port1_id'))
            x2, y2 = self._ppos(d2, c.get('port2_id'))

            ct = c.get('cable_type', 'Ethernet')
            col = self.cable_colors.get(ct, QColor('#808080'))

            # Межсекторное?
            s1 = set(d1.get('sector_ids', []))
            s2 = set(d2.get('sector_ids', []))
            inter = bool(s1 and s2 and s1 != s2)
            ext = d1.get('_external', False) or d2.get('_external', False)

            if inter:
                pen = QPen(col.lighter(130), 2.5, Qt.PenStyle.DashDotLine)
            elif ext:
                pen = QPen(col, 1.2, Qt.PenStyle.DashLine)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            else:
                pen = QPen(col, 1.5)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                if ct == 'Fiber Optic':
                    pen.setStyle(Qt.PenStyle.DashLine)
                elif ct == 'Serial':
                    pen.setStyle(Qt.PenStyle.DotLine)
                elif ct == 'Coaxial':
                    pen.setStyle(Qt.PenStyle.DashDotLine)

            p.setPen(pen)

            # Безье
            path = QPainterPath()
            path.moveTo(x1, y1)
            dx = abs(x2 - x1) * 0.4
            path.cubicTo(x1 + dx, y1, x2 - dx, y2, x2, y2)
            p.drawPath(path)

            # Стрелка
            self._arrow(p, x1, y1, x2, y2, col)

            # Подпись
            self._clabel(p, c, x1, y1, x2, y2, d1, d2, inter)

    def _clabel(self, p: QPainter, c: dict, x1, y1, x2, y2, d1, d2, inter):
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        lines = []
        if inter:
            n1 = self._sname(d1.get('sector_ids', []))
            n2 = self._sname(d2.get('sector_ids', []))
            lines.append(f"🌐 {n1} → {n2}")
        g = next((g for g in self.groups if g.get('id') == c.get('group_id')), None) if c.get('group_id') else None
        if g:
            lines.append(f"📦 {g.get('name', '')}")
        lines.append(f"{c.get('cable_type', 'Ethernet')} | {c.get('length', 1.0)}м")

        lh = 15
        th = len(lines) * lh + 6
        r = QRectF(mx - 70, my - th / 2, 140, th)
        p.fillRect(r, QColor(50, 50, 0, 220) if inter else QColor(30, 30, 46, 220))
        p.setPen(QPen(QColor('#45475a'), 1))
        p.drawRoundedRect(r, 4, 4)
        p.setPen(QColor('#cdd6f4'))
        f = QFont('Arial', 7)
        p.setFont(f)
        for i, line in enumerate(lines):
            p.drawText(QRectF(mx - 65, my - th / 2 + 4 + i * lh, 130, lh), Qt.AlignmentFlag.AlignCenter, line)

    def _arrow(self, p: QPainter, x1, y1, x2, y2, col: QColor):
        t = 0.7
        dx = abs(x2 - x1) * 0.4
        ax = (1 - t) ** 3 * x1 + 3 * (1 - t) ** 2 * t * (x1 + dx) + 3 * (1 - t) * t ** 2 * (x2 - dx) + t ** 3 * x2
        ay = (1 - t) ** 3 * y1 + 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3 * y2
        ang = math.atan2(y2 - y1, x2 - x1)
        sz = 7
        p.setBrush(QBrush(col))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([
            QPointF(ax + sz * math.cos(ang), ay + sz * math.sin(ang)),
            QPointF(ax + sz * math.cos(ang + 2.5), ay + sz * math.sin(ang + 2.5)),
            QPointF(ax + sz * math.cos(ang - 2.5), ay + sz * math.sin(ang - 2.5))
        ]))

    def _temp_conn(self, p: QPainter):
        if not self.connection_start_port:
            return
        x1, y1 = self.connection_start_port.get('x', 0), self.connection_start_port.get('y', 0)
        cp = self.mapFromGlobal(self.cursor().pos())
        x2 = (cp.x() - self.offset_x) / self.scale
        y2 = (cp.y() - self.offset_y) / self.scale
        p.setPen(QPen(QColor('#f9e2af'), 2, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _device(self, p: QPainter, d: dict):
        x, y = d.get('x', 0), d.get('y', 0)
        w, h = d.get('width', self.DEVICE_W), d.get('height', self.DEVICE_H)
        cat = d.get('category', 'SWITCHES')
        ext = d.get('_external', False)
        sel = d.get('id') == self.selected_device_id

        bc = self.category_colors.get(cat, QColor('#808080'))
        if ext:
            fc = QColor(bc.red(), bc.green(), bc.blue(), 100)
            boc = QColor(bc.red(), bc.green(), bc.blue(), 180)
            bw, bs = 1.5, Qt.PenStyle.DotLine
        else:
            fc, boc = bc, bc.darker(150)
            bw, bs = 2, Qt.PenStyle.SolidLine

        if sel:
            boc, bw = QColor('#f9e2af'), 3

        pen = QPen(boc, bw)
        pen.setStyle(bs)
        p.setPen(pen)
        p.setBrush(QBrush(fc))
        r = QRectF(x - w / 2, y - h / 2, w, h)
        p.drawRoundedRect(r, 8, 8)

        # Метка внешнего
        if ext:
            es = d.get('_external_sectors', [])
            if es:
                lr = QRectF(x - w / 2, y - h / 2 - 22, w, 18)
                p.fillRect(lr, QColor(50, 50, 70, 220))
                p.setPen(QColor('#f9e2af'))
                f = QFont('Arial', 7, QFont.Weight.Bold)
                p.setFont(f)
                txt = f"🔗 {', '.join(es[:2])}"
                if len(es) > 2:
                    txt += f" +{len(es) - 2}"
                p.drawText(lr, Qt.AlignmentFlag.AlignCenter, txt)

        # Мульти-сектор
        sids = d.get('sector_ids', [])
        if len(sids) > 1 and not ext:
            p.setPen(QColor('#f9e2af'))
            f = QFont('Arial', 6)
            p.setFont(f)
            p.drawText(QRectF(x - w / 2, y - h / 2 - 14, w, 12), Qt.AlignmentFlag.AlignCenter,
                       f"📂 {len(sids)} сектора")

        # Заголовок
        hr = QRectF(x - w / 2, y - h / 2, w, 22)
        p.fillRect(hr, QColor(80, 80, 80, 120) if ext else QColor(0, 0, 0, 80))
        p.setPen(QColor('#ffffff'))
        f = QFont('Arial', 9, QFont.Weight.Bold)
        p.setFont(f)
        nm = f"[{d.get('name', '')}]" if ext else d.get('name', '')
        p.drawText(hr, Qt.AlignmentFlag.AlignCenter, nm)

        # Тип
        p.setPen(QColor('#cdd6f4'))
        f = QFont('Arial', 7)
        p.setFont(f)
        p.drawText(QRectF(x - w / 2, y + h / 2 - 16, w, 16), Qt.AlignmentFlag.AlignCenter,
                   d.get('device_type', ''))

        # Порты
        for pt in d.get('input_ports', []):
            self._port(p, pt, True)
        for pt in d.get('output_ports', []):
            self._port(p, pt, False)

    def _port(self, p: QPainter, pt: dict, inp: bool):
        px, py = pt.get('x', 0), pt.get('y', 0)
        sz = self.PORT_SIZE
        conn = any(pt.get('id') in (c.get('port1_id'), c.get('port2_id')) for c in self.connections)
        col = QColor('#00c800') if (conn and inp) else (QColor('#c89600') if conn else QColor('#585b70'))

        p.setBrush(QBrush(col))
        p.setPen(QPen(QColor('#ff0000'), 2) if pt == self.selected_port else QPen(QColor('#cdd6f4'), 0.5))

        if inp:
            p.drawPolygon(QPolygonF([
                QPointF(px - sz, py - sz), QPointF(px - sz, py + sz), QPointF(px + sz, py)
            ]))
        else:
            p.drawRect(QRectF(px - sz, py - sz, sz * 2, sz * 2))

        p.setPen(QColor('#a6adc8'))
        f = QFont('Arial', 5)
        p.setFont(f)
        p.drawText(QRectF(px - 20, py - 18, 40, 12), Qt.AlignmentFlag.AlignCenter, pt.get('name', ''))

    def _readonly(self, p: QPainter):
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 100))
        p.drawRect(self.rect())
        p.setPen(QColor('#f9e2af'))
        f = QFont('Arial', 14, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                   "🔒 Сектор заблокирован\nРежим только для чтения")
        p.restore()

    def _hint(self, p: QPainter, text: str):
        p.save()
        p.setPen(QColor('#f9e2af'))
        f = QFont('Arial', 10, QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(10, self.height() - 10, text)
        p.restore()

    # ============================================================
    #  ВСПОМОГАТЕЛЬНЫЕ
    # ============================================================

    def _fdev(self, did: int) -> Optional[dict]:
        return next((d for d in self.devices if d.get('id') == did), None)

    def _fport(self, d: dict, pid: int) -> Optional[dict]:
        for k in ['input_ports', 'output_ports']:
            for p in d.get(k, []):
                if p.get('id') == pid:
                    return p
        return None

    def _ppos(self, d: dict, pid: int) -> tuple:
        p = self._fport(d, pid)
        return (p.get('x', 0), p.get('y', 0)) if p else (d.get('x', 0), d.get('y', 0))

    def _sname(self, sids: list) -> str:
        names = []
        for sid in sids:
            s = next((x for x in self.sectors if x.get('id') == sid), None)
            if s:
                nm = s.get('name', '')
                names.append(nm.split(' - ')[-1] if ' - ' in nm else nm.split(' ')[-1])
        return '/'.join(names) if names else '?'

    def _upsert(self, d: dict):
        did = d.get('id')
        for i, x in enumerate(self.devices):
            if x.get('id') == did:
                self.devices[i].update(d)
                return
        self.devices.append(d)

    def _conn_exists(self, c: dict) -> bool:
        return any(self._conn_eq(x, c) for x in self.connections)

    def _conn_eq(self, a: dict, b: dict) -> bool:
        return (a.get('device1_id') == b.get('device1_id') and a.get('port1_id') == b.get('port1_id') and
                a.get('device2_id') == b.get('device2_id') and a.get('port2_id') == b.get('port2_id'))

    def _to_scene(self, cx: float, cy: float) -> tuple:
        return (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale

    def _up_ports(self, d: dict):
        x, y = d.get('x', 0), d.get('y', 0)
        w, h = d.get('width', self.DEVICE_W), d.get('height', self.DEVICE_H)
        for k in ['input_ports', 'output_ports']:
            pl = d.get(k, [])
            inp = k == 'input_ports'
            n = len(pl)
            for i, pt in enumerate(pl):
                pt['x'] = x - w / 2 if inp else x + w / 2
                pt['y'] = y - h / 2 + (i + 1) * (h / (n + 1)) if n > 1 else y

    def _fport_at(self, cx: float, cy: float) -> Optional[tuple]:
        for d in self.devices:
            for k in ['input_ports', 'output_ports']:
                for pt in d.get(k, []):
                    if abs(cx - pt.get('x', 0)) < 8 and abs(cy - pt.get('y', 0)) < 8:
                        return pt, d
        return None

    def _fdev_at(self, cx: float, cy: float) -> Optional[dict]:
        for d in reversed(self.devices):
            if abs(cx - d.get('x', 0)) < d.get('width', self.DEVICE_W) / 2 and \
                    abs(cy - d.get('y', 0)) < d.get('height', self.DEVICE_H) / 2:
                return d
        return None

    # ============================================================
    #  РЕДАКТИРОВАНИЕ СЕКТОРОВ
    # ============================================================

    def toggle_sector_edit_mode(self):
        self.sector_edit_mode = not self.sector_edit_mode
        self.setCursor(Qt.CursorShape.CrossCursor if self.sector_edit_mode else Qt.CursorShape.ArrowCursor)
        self.dragging_sector_id = None
        self.resizing_sector_id = None
        self.resize_handle = None
        self.update()

    def _fsector_at(self, cx: float, cy: float) -> Optional[dict]:
        for s in self.sectors:
            b = s.get('bounds', {})
            if not b:
                continue
            if b.get('x', 0) <= cx <= b.get('x', 0) + b.get('width', 800) and \
                    b.get('y', 0) <= cy <= b.get('y', 0) + b.get('height', 600):
                return s
        return None

    def _fhandle(self, cx: float, cy: float, s: dict) -> Optional[str]:
        b = s.get('bounds', {})
        x, y, w, h = b.get('x', 0), b.get('y', 0), b.get('width', 800), b.get('height', 600)
        hs = self.HANDLE_SIZE * 2

        # Углы
        if abs(cx - x) < hs and abs(cy - y) < hs:
            return 'nw'
        if abs(cx - (x + w)) < hs and abs(cy - y) < hs:
            return 'ne'
        if abs(cx - x) < hs and abs(cy - (y + h)) < hs:
            return 'sw'
        if abs(cx - (x + w)) < hs and abs(cy - (y + h)) < hs:
            return 'se'
        # Края
        if abs(cx - x) < hs and y < cy < y + h:
            return 'w'
        if abs(cx - (x + w)) < hs and y < cy < y + h:
            return 'e'
        if abs(cy - y) < hs and x < cx < x + w:
            return 'n'
        if abs(cy - (y + h)) < hs and x < cx < x + w:
            return 's'
        return None

    def _hcursor(self, h: str) -> Qt.CursorShape:
        return {
            'n': Qt.CursorShape.SizeVerCursor, 's': Qt.CursorShape.SizeVerCursor,
            'e': Qt.CursorShape.SizeHorCursor, 'w': Qt.CursorShape.SizeHorCursor,
            'nw': Qt.CursorShape.SizeFDiagCursor, 'se': Qt.CursorShape.SizeFDiagCursor,
            'ne': Qt.CursorShape.SizeBDiagCursor, 'sw': Qt.CursorShape.SizeBDiagCursor,
        }.get(h, Qt.CursorShape.ArrowCursor)

    # ============================================================
    #  СОБЫТИЯ
    # ============================================================

    def contextMenuEvent(self, event):
        pos = event.pos()
        sx, sy = self._to_scene(pos.x(), pos.y())

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; padding: 5px; }
            QMenu::item { padding: 8px 20px; border-radius: 3px; }
            QMenu::item:selected { background-color: #45475a; }
            QMenu::separator { height: 1px; background: #45475a; margin: 3px 10px; }
        """)

        dev = self._fdev_at(sx, sy)
        if dev and not dev.get('_external', False):
            self.selected_device_id = dev.get('id')
            self.selected_device = dev
            self.update()
            menu.addAction("✏️ Редактировать (F2)").triggered.connect(lambda: self._edit_dialog(dev))
            menu.addSeparator()
            a = menu.addAction("🗑️ Удалить (Del)")
            a.triggered.connect(lambda: self.device_deleted.emit(dev.get('id', 0)))
        else:
            self.selected_device_id = None
            self.selected_device = None
            self.update()
            add = menu.addMenu("➕ Добавить устройство")
            for name, dt, cat in [
                ("🌐 Магистральный кросс", "Main Cross-connect", "GLOBAL_INPUT"),
                ("🔌 Локальный кросс", "Local Cross-connect", "LOCAL_INPUT"),
                ("⚡ Агрегатор", "Aggregator", "SWITCHES"),
                ("🔀 Коммутатор", "Switch", "SWITCHES"),
                ("🖥 Сервер приложений", "Application Server", "SERVERS"),
                ("🗄 Сервер БД", "Database Server", "SERVERS"),
            ]:
                a = add.addAction(name)
                a.triggered.connect(lambda checked, d=dt, c=cat, x=sx, y=sy: self.add_device_at(x, y, d, c))

        menu.exec(event.globalPos())

    def _edit_dialog(self, dev: dict):
        nm, ok = QInputDialog.getText(self, "Редактирование", "Название:", text=dev.get('name', ''))
        if ok and nm:
            dev['name'] = nm
            self.device_edited.emit(dev)
            self.update()

    def mousePressEvent(self, event):
        if not self.is_editable and event.button() not in (Qt.MouseButton.MiddleButton,):
            return

        pos = event.position()
        sx, sy = self._to_scene(pos.x(), pos.y())

        # Панорамирование
        if event.button() == Qt.MouseButton.MiddleButton or \
                (
                        event.button() == Qt.MouseButton.LeftButton and event.modifiers() == Qt.KeyboardModifier.ControlModifier):
            self.panning = True
            self.pan_start = pos
            self.pan_offset_start = QPointF(self.offset_x, self.offset_y)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        # Режим секторов
        if self.sector_edit_mode and event.button() == Qt.MouseButton.LeftButton:
            for s in self.sectors:
                h = self._fhandle(sx, sy, s)
                if h:
                    self.resizing_sector_id = s.get('id')
                    self.resize_handle = h
                    self.sector_resize_start = {'x': sx, 'y': sy, 'bounds': dict(s.get('bounds', {}))}
                    self.setCursor(self._hcursor(h))
                    return
            sec = self._fsector_at(sx, sy)
            if sec:
                self.dragging_sector_id = sec.get('id')
                b = sec.get('bounds', {})
                self.sector_drag_offset = QPointF(sx - b.get('x', 0), sy - b.get('y', 0))
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                return

        # Соединения
        if event.button() == Qt.MouseButton.RightButton:
            pi = self._fport_at(sx, sy)
            if pi and pi[0].get('port_type') == 'output':
                self.connection_mode = True
                self.connection_start_port = pi[0]
                self.connection_start_device = pi[1]
                self.selected_port = pi[0]
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.update()
            return

        if self.connection_mode and event.button() == Qt.MouseButton.LeftButton:
            pi = self._fport_at(sx, sy)
            if pi and pi[0].get('port_type') == 'input' and self.connection_start_device:
                self.connection_requested.emit(
                    self.connection_start_device.get('id', 0),
                    self.connection_start_port.get('id', 0),
                    pi[1].get('id', 0), pi[0].get('id', 0))
            self._cancel_conn()
            return

        # Перетаскивание устройства
        if event.button() == Qt.MouseButton.LeftButton:
            dev = self._fdev_at(sx, sy)
            if dev and not dev.get('_external', False):
                self.selected_device_id = dev.get('id')
                self.selected_device = dev
                self.dragging = True
                self.drag_device_id = dev.get('id')
                self.drag_offset = QPointF(sx - dev.get('x', 0), sy - dev.get('y', 0))
                self.update()
                return
            self.selected_device_id = None
            self.selected_device = None
            self.selected_port = None
            self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()

        if self.panning:
            d = pos - self.pan_start
            self.offset_x = self.pan_offset_start.x() + d.x()
            self.offset_y = self.pan_offset_start.y() + d.y()
            self.update()
            return

        if self.sector_edit_mode:
            sx, sy = self._to_scene(pos.x(), pos.y())
            if self.resizing_sector_id and self.resize_handle:
                s = next((x for x in self.sectors if x.get('id') == self.resizing_sector_id), None)
                if s and self.sector_resize_start:
                    ob = self.sector_resize_start['bounds']
                    nb = dict(s.get('bounds', {}))
                    dx = sx - self.sector_resize_start['x']
                    dy = sy - self.sector_resize_start['y']
                    if 'e' in self.resize_handle:
                        nb['width'] = max(200, ob['width'] + dx)
                    if 'w' in self.resize_handle:
                        nb['x'] = ob['x'] + dx
                        nb['width'] = max(200, ob['width'] - dx)
                    if 's' in self.resize_handle:
                        nb['height'] = max(150, ob['height'] + dy)
                    if 'n' in self.resize_handle:
                        nb['y'] = ob['y'] + dy
                        nb['height'] = max(150, ob['height'] - dy)
                    s['bounds'] = nb
                    self.update()
                return
            if self.dragging_sector_id:
                s = next((x for x in self.sectors if x.get('id') == self.dragging_sector_id), None)
                if s:
                    b = s.get('bounds', {})
                    b['x'] = sx - self.sector_drag_offset.x()
                    b['y'] = sy - self.sector_drag_offset.y()
                    self.update()
                return
            if not self.dragging_sector_id and not self.resizing_sector_id:
                cur = Qt.CursorShape.CrossCursor
                for s in self.sectors:
                    h = self._fhandle(sx, sy, s)
                    if h:
                        cur = self._hcursor(h)
                        break
                    if self._fsector_at(sx, sy):
                        cur = Qt.CursorShape.SizeAllCursor
                self.setCursor(cur)
            return

        if self.dragging and self.drag_device_id is not None:
            sx, sy = self._to_scene(pos.x(), pos.y())
            dev = self._fdev(self.drag_device_id)
            if dev:
                dev['x'] = sx - self.drag_offset.x()
                dev['y'] = sy - self.drag_offset.y()
                self._up_ports(dev)
                self.update()

        if self.connection_mode:
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self.panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if self.sector_edit_mode:
            if self.resizing_sector_id:
                s = next((x for x in self.sectors if x.get('id') == self.resizing_sector_id), None)
                if s:
                    self.sector_changed.emit(s)
                self.resizing_sector_id = None
                self.resize_handle = None
                self.sector_resize_start = None
            if self.dragging_sector_id:
                s = next((x for x in self.sectors if x.get('id') == self.dragging_sector_id), None)
                if s:
                    self.sector_changed.emit(s)
                self.dragging_sector_id = None
            self.update()
            return

        if self.dragging and self.drag_device_id is not None:
            dev = self._fdev(self.drag_device_id)
            if dev:
                self.device_moved.emit(dev.get('id', 0), dev.get('x', 0), dev.get('y', 0))
            self.dragging = False
            self.drag_device_id = None

    def wheelEvent(self, event):
        d = event.angleDelta().y()
        f = 1.1 if d > 0 else 0.9
        op = event.position()
        ns = self.scale * f
        if 0.1 <= ns <= 5.0:
            self.offset_x = op.x() - (op.x() - self.offset_x) * f
            self.offset_y = op.y() - (op.y() - self.offset_y) * f
            self.scale = ns
            self.zoom_changed.emit(self.scale)
            self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.sector_edit_mode:
                self.toggle_sector_edit_mode()
            elif self.connection_mode:
                self._cancel_conn()
        elif event.key() == Qt.Key.Key_Delete and not self.sector_edit_mode:
            if self.selected_device_id:
                self.device_deleted.emit(self.selected_device_id)
        elif event.key() == Qt.Key.Key_F2 and self.selected_device:
            self._edit_dialog(self.selected_device)
        elif event.key() == Qt.Key.Key_F3:
            self.toggle_sector_edit_mode()
        elif event.key() == Qt.Key.Key_F5:
            self.update()

    def _cancel_conn(self):
        self.connection_mode = False
        self.connection_start_port = None
        self.connection_start_device = None
        self.selected_port = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()