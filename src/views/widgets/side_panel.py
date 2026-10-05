"""Левая панель инструментов."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
    QLineEdit, QPushButton, QCheckBox, QScrollArea, QFrame,
)
from PyQt6.QtCore import pyqtSignal, Qt

from config.constants import (
    CABLE_COLORS, CONNECTOR_COLORS,
    SIDE_PANEL_MIN_WIDTH, SIDE_PANEL_MAX_WIDTH,
)


class SidePanel(QWidget):
    """
    Левая панель: фильтр, отображение, легенды, действия.
    Испускает сигналы для контроллера.
    """

    filter_changed = pyqtSignal(str)
    display_changed = pyqtSignal()
    create_channel = pyqtSignal()
    manage_groups = pyqtSignal()
    save_project = pyqtSignal()
    load_project = pyqtSignal()
    delete_selected = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(SIDE_PANEL_MIN_WIDTH)
        self.setMaximumWidth(SIDE_PANEL_MAX_WIDTH)
        self.setObjectName("sidePanel")
        self._build()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Заголовок
        title = QLabel("Network Visualizer")
        title.setObjectName("sidePanelTitle")
        layout.addWidget(title)

        # Фильтр
        layout.addWidget(self._make_filter_group())

        # Отображение
        layout.addWidget(self._make_display_group())

        # Легенды
        layout.addWidget(self._make_cables_legend())
        layout.addWidget(self._make_connectors_legend())

        # Действия
        layout.addWidget(self._make_actions_group())

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    # ========================================================

    def _make_filter_group(self) -> QGroupBox:
        group = QGroupBox("🔍 Фильтр групп")
        layout = QVBoxLayout(group)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Поиск группы...")
        self.filter_edit.textChanged.connect(self.filter_changed.emit)
        layout.addWidget(self.filter_edit)

        clear_btn = QPushButton("✕ Очистить")
        clear_btn.clicked.connect(lambda: self.filter_edit.clear())
        layout.addWidget(clear_btn)

        return group

    def _make_display_group(self) -> QGroupBox:
        group = QGroupBox("👁 Отображение")
        layout = QVBoxLayout(group)

        self.ports_cb = QCheckBox("Подписи портов")
        self.ports_cb.setChecked(True)
        self.ports_cb.stateChanged.connect(self.display_changed.emit)
        layout.addWidget(self.ports_cb)

        self.conns_cb = QCheckBox("Подписи соединений")
        self.conns_cb.setChecked(True)
        self.conns_cb.stateChanged.connect(self.display_changed.emit)
        layout.addWidget(self.conns_cb)

        self.grid_cb = QCheckBox("Сетка")
        self.grid_cb.setChecked(True)
        self.grid_cb.stateChanged.connect(self.display_changed.emit)
        layout.addWidget(self.grid_cb)

        return group

    def _make_cables_legend(self) -> QGroupBox:
        group = QGroupBox("🔌 Типы кабелей")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        for name, color in CABLE_COLORS.items():
            layout.addWidget(self._make_legend_row(name, color, 24, 4, "line"))

        return group

    def _make_connectors_legend(self) -> QGroupBox:
        group = QGroupBox("🔗 Разъёмы")
        layout = QVBoxLayout(group)
        layout.setSpacing(4)

        for name, color in CONNECTOR_COLORS.items():
            layout.addWidget(self._make_legend_row(name, color, 12, 12, "square"))

        return group

    @staticmethod
    def _make_legend_row(name: str, color: str,
                         w: int, h: int, shape: str) -> QWidget:
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 2, 4, 2)
        rl.setSpacing(8)

        marker = QLabel()
        marker.setFixedSize(w, h)
        if shape == "line":
            style = f"background-color: {color}; border-radius: 2px;"
        else:
            style = (
                f"background-color: {color}; border-radius: 3px; "
                f"border: 1px solid #4b5563;"
            )
        marker.setStyleSheet(style)
        rl.addWidget(marker)

        label = QLabel(name)
        label.setStyleSheet("color: #4a5568; font-size: 11px;")
        rl.addWidget(label, 1)

        return row

    def _make_actions_group(self) -> QGroupBox:
        group = QGroupBox("Действия")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        layout.addWidget(self._make_action("🔗 Создать канал", self.create_channel))
        layout.addWidget(self._make_action("📊 Управление группами", self.manage_groups))
        layout.addWidget(self._make_action("💾 Сохранить проект", self.save_project))
        layout.addWidget(self._make_action("📂 Загрузить проект", self.load_project))

        delete_btn = QPushButton("🗑️ Удалить выбранное")
        delete_btn.setProperty("class", "danger")
        delete_btn.clicked.connect(self.delete_selected.emit)
        layout.addWidget(delete_btn)

        return group

    @staticmethod
    def _make_action(text: str, signal) -> QPushButton:
        btn = QPushButton(text)
        btn.clicked.connect(signal.emit)
        return btn

    # ========================================================

    def get_display_settings(self) -> dict:
        return {
            "show_port_labels": self.ports_cb.isChecked(),
            "show_connection_labels": self.conns_cb.isChecked(),
            "show_grid": self.grid_cb.isChecked(),
        }