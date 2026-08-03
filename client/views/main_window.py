from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QListWidget, QListWidgetItem,
    QGroupBox, QStatusBar, QSplitter, QFrame, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from .canvas_widget import CanvasWidget
from .sector_panel import SectorPanel
from .user_panel import UserPanel


class MainWindow(QMainWindow):
    """Главное окно клиента"""

    login_requested = pyqtSignal()
    sector_selected = pyqtSignal(int)
    lock_toggled = pyqtSignal()
    leave_sector = pyqtSignal()
    view_mode_changed = pyqtSignal(str, list)  # view_mode, sector_ids

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Network Visualizer - Клиент")
        self.setGeometry(100, 100, 1400, 900)

        self.user_info = {}
        self.current_sector_id = 0
        self.is_locked = False

        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Левая панель
        left_panel = self._create_left_panel()

        # Центральная область
        center_widget = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Информационная панель с переключателем видов
        info_bar = self._create_info_bar()
        center_layout.addWidget(info_bar)

        # Канвас
        self.canvas = CanvasWidget()
        center_layout.addWidget(self.canvas, 1)

        center_widget.setLayout(center_layout)

        # Сплиттер
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_widget)
        splitter.setSizes([280, 1120])

        layout.addWidget(splitter)
        central.setLayout(layout)

        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Отключено от сервера")

    def _create_left_panel(self) -> QWidget:
        """Создание левой панели"""
        panel = QWidget()
        panel.setMaximumWidth(300)
        layout = QVBoxLayout()

        # Информация о пользователе
        self.user_info_label = QLabel("Не авторизован")
        self.user_info_label.setWordWrap(True)
        self.user_info_label.setStyleSheet(
            "padding: 10px; background-color: #45475a; border-radius: 5px;"
        )
        layout.addWidget(self.user_info_label)

        # Кнопка входа
        self.login_btn = QPushButton("🔑 Войти в систему")
        self.login_btn.clicked.connect(self.login_requested.emit)
        self.login_btn.setStyleSheet(
            "background-color: #89b4fa; color: #1e1e2e; font-weight: bold; padding: 10px;"
        )
        layout.addWidget(self.login_btn)

        # Разделитель
        layout.addWidget(self._create_separator())

        # Сектора
        self.sector_panel = SectorPanel()
        self.sector_panel.sector_selected.connect(self._on_sector_selected)
        layout.addWidget(self.sector_panel)

        # Разделитель
        layout.addWidget(self._create_separator())

        # Управление сектором
        sector_controls = QGroupBox("Управление сектором")
        controls_layout = QVBoxLayout()

        self.lock_btn = QPushButton("🔒 Заблокировать сектор")
        self.lock_btn.setEnabled(False)
        self.lock_btn.clicked.connect(self.lock_toggled.emit)
        controls_layout.addWidget(self.lock_btn)

        self.leave_btn = QPushButton("🚪 Покинуть сектор")
        self.leave_btn.setEnabled(False)
        self.leave_btn.clicked.connect(self.leave_sector.emit)
        controls_layout.addWidget(self.leave_btn)

        sector_controls.setLayout(controls_layout)
        layout.addWidget(sector_controls)

        # Разделитель
        layout.addWidget(self._create_separator())

        # Пользователи в секторе
        self.user_panel = UserPanel()
        layout.addWidget(self.user_panel)

        layout.addStretch()
        panel.setLayout(layout)
        return panel

    def _create_info_bar(self) -> QWidget:
        """Создание информационной панели с элементами управления"""
        bar = QWidget()
        bar.setMaximumHeight(42)
        bar.setStyleSheet("background-color: #313244;")

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # ===== Кнопка редактирования секторов =====
        self.edit_sectors_btn = QPushButton("✏️ Сектора")
        self.edit_sectors_btn.setCheckable(True)
        self.edit_sectors_btn.setMaximumWidth(90)
        self.edit_sectors_btn.setToolTip("Режим редактирования секторов (F3)\n"
                                         "Перетаскивайте сектора, тяните за углы для изменения размера")
        self.edit_sectors_btn.clicked.connect(self._on_toggle_sector_edit)
        self.edit_sectors_btn.setStyleSheet("""
            QPushButton {
                background-color: #45475a;
                color: #cdd6f4;
                border: 1px solid #585b70;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
            QPushButton:checked {
                background-color: #f9e2af;
                color: #1e1e2e;
                font-weight: bold;
                border-color: #f9e2af;
            }
        """)
        layout.addWidget(self.edit_sectors_btn)

        # ===== Разделитель =====
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setStyleSheet("color: #45475a;")
        layout.addWidget(sep1)

        # ===== Переключатель режимов просмотра =====
        view_label = QLabel("Вид:")
        view_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(view_label)

        self.view_mode_combo = QComboBox()
        self.view_mode_combo.addItem("🌐 Вся сеть", "full")
        self.view_mode_combo.addItem("📁 Один сектор", "single")
        self.view_mode_combo.addItem("📂 Несколько", "multi")
        self.view_mode_combo.setCurrentIndex(1)  # По умолчанию - один сектор
        self.view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        self.view_mode_combo.setMaximumWidth(140)
        self.view_mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #45475a;
                color: #cdd6f4;
                border: 1px solid #585b70;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox:hover {
                background-color: #585b70;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #cdd6f4;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #313244;
                color: #cdd6f4;
                selection-background-color: #45475a;
                border: 1px solid #45475a;
                outline: none;
            }
        """)
        layout.addWidget(self.view_mode_combo)

        # ===== Разделитель =====
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setStyleSheet("color: #45475a;")
        layout.addWidget(sep2)

        # ===== Название текущего сектора =====
        self.sector_name_label = QLabel("Сектор не выбран")
        self.sector_name_label.setStyleSheet(
            "color: #89b4fa; font-weight: bold; font-size: 12px; padding: 0 5px;"
        )
        layout.addWidget(self.sector_name_label)

        layout.addStretch()

        # ===== Информация о масштабе =====
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("color: #a6adc8; font-size: 10px; padding: 0 5px;")
        self.zoom_label.setToolTip("Текущий масштаб. Используйте колесико мыши для изменения")
        layout.addWidget(self.zoom_label)

        # ===== Разделитель =====
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.VLine)
        sep3.setStyleSheet("color: #45475a;")
        layout.addWidget(sep3)

        # ===== Статус блокировки =====
        self.lock_status_label = QLabel("")
        self.lock_status_label.setStyleSheet("font-size: 11px; padding: 0 5px;")
        layout.addWidget(self.lock_status_label)

        # ===== Версия =====
        self.version_label = QLabel("")
        self.version_label.setStyleSheet("color: #585b70; font-size: 10px; padding: 0 5px;")
        layout.addWidget(self.version_label)

        # ===== Разделитель =====
        sep4 = QFrame()
        sep4.setFrameShape(QFrame.Shape.VLine)
        sep4.setStyleSheet("color: #45475a;")
        layout.addWidget(sep4)

        # ===== Легенда =====
        legend_label = QLabel("🔗 пунктир = внеш. устр. | ⚡ жирный = межсекторная связь")
        legend_label.setStyleSheet("color: #585b70; font-size: 9px;")
        legend_label.setToolTip("Внешние устройства показаны полупрозрачными с пунктирной рамкой\n"
                                "Межсекторные соединения выделены жирной линией")
        layout.addWidget(legend_label)

        bar.setLayout(layout)
        return bar

    def _on_toggle_sector_edit(self):
        """Переключение режима редактирования секторов"""
        self.canvas.toggle_sector_edit_mode()
        self.edit_sectors_btn.setChecked(self.canvas.sector_edit_mode)
        if self.canvas.sector_edit_mode:
            self.status_bar.showMessage(
                "✏️ Режим редактирования секторов | Тяните за углы/края | Перетаскивайте | Esc - выход"
            )
        else:
            self.status_bar.showMessage("Готов к работе")

    def _on_view_mode_changed(self, index: int):
        """Обработка изменения режима просмотра"""
        view_mode = self.view_mode_combo.currentData()

        if view_mode == "full":
            sector_ids = []
        elif view_mode == "single":
            sector_ids = [self.current_sector_id] if self.current_sector_id else []
        elif view_mode == "multi":
            sector_ids = list(self.canvas.visible_sector_ids) if self.canvas.visible_sector_ids else []

        self.view_mode_changed.emit(view_mode, sector_ids)
        self.status_bar.showMessage(f"Режим просмотра: {view_mode}")

    def update_zoom_label(self, scale: float):
        """Обновление метки масштаба"""
        self.zoom_label.setText(f"{int(scale * 100)}%")

    def on_sector_joined(self, sector_id: int, sector_name: str):
        """Обработка входа в сектор"""
        self.current_sector_id = sector_id
        self.sector_name_label.setText(f"📁 {sector_name}")
        self.leave_btn.setEnabled(True)
        self.lock_btn.setEnabled(True)
        self.view_mode_combo.setCurrentIndex(1)  # Переключаем на "Один сектор"
        self.status_bar.showMessage(f"Вошли в сектор: {sector_name}")

    def _create_separator(self) -> QFrame:
        """Создание разделителя"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #45475a;")
        return line

    def _on_view_mode_changed(self, index: int):
        """Обработка изменения режима просмотра"""
        view_mode = self.view_mode_combo.currentData()

        if view_mode == "full":
            sector_ids = []
        elif view_mode == "single":
            sector_ids = [self.current_sector_id] if self.current_sector_id else []
        elif view_mode == "multi":
            # В будущем можно добавить диалог выбора секторов
            sector_ids = []

        self.view_mode_changed.emit(view_mode, sector_ids)
        self.status_bar.showMessage(f"Режим просмотра: {view_mode}")

    def _on_sector_selected(self, sector_id: int):
        """Обработка выбора сектора"""
        self.sector_selected.emit(sector_id)

    def update_user_info(self, info: dict):
        """Обновление информации о пользователе"""
        self.user_info = info
        self.user_info_label.setText(
            f"👤 {info.get('username', '')}\n"
            f"🎭 Роль: {info.get('role', '')}\n"
            f"📋 ID: {info.get('user_id', 0)}"
        )
        self.login_btn.setVisible(False)
        self.status_bar.showMessage(f"Авторизован как {info.get('username', '')}")

    def update_sectors(self, sectors: list):
        """Обновление списка секторов"""
        self.sector_panel.update_sectors(sectors)

    def on_sector_joined(self, sector_id: int, sector_name: str):
        """Обработка входа в сектор"""
        self.current_sector_id = sector_id
        self.sector_name_label.setText(f"📁 {sector_name}")
        self.leave_btn.setEnabled(True)
        self.lock_btn.setEnabled(True)
        self.status_bar.showMessage(f"Вошли в сектор: {sector_name}")

    def on_sector_left(self):
        """Обработка выхода из сектора"""
        self.current_sector_id = 0
        self.sector_name_label.setText("Сектор не выбран")
        self.leave_btn.setEnabled(False)
        self.lock_btn.setEnabled(False)
        self.lock_status_label.setText("")
        self.version_label.setText("")
        self.canvas.clear()
        self.status_bar.showMessage("Покинули сектор")

    def update_lock_status(self, is_locked: bool, locked_by: str = ""):
        """Обновление статуса блокировки"""
        self.is_locked = is_locked

        if is_locked:
            self.lock_btn.setText("🔓 Разблокировать сектор")
            self.lock_btn.setStyleSheet(
                "background-color: #f9e2af; color: #1e1e2e; font-weight: bold; padding: 10px;"
            )
            self.lock_status_label.setText(f"🔒 Заблокирован: {locked_by}")
            self.lock_status_label.setStyleSheet("color: #f9e2af;")
            self.canvas.set_editable(False)
        else:
            self.lock_btn.setText("🔒 Заблокировать сектор")
            self.lock_btn.setStyleSheet("")
            self.lock_status_label.setText("🔓 Разблокирован")
            self.lock_status_label.setStyleSheet("color: #a6e3a1;")
            self.canvas.set_editable(True)

    def update_version(self, version: int):
        """Обновление версии"""
        self.version_label.setText(f"v{version}")

    def update_users(self, users: list):
        """Обновление списка пользователей"""
        self.user_panel.update_users(users)

    def add_user(self, user: dict):
        """Добавление пользователя"""
        self.user_panel.add_user(user)

    def remove_user(self, user_id: int):
        """Удаление пользователя"""
        self.user_panel.remove_user(user_id)