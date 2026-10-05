"""Главное окно приложения."""

import json

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QFileDialog, QMessageBox,
    QStatusBar, QToolBar, QLabel,
)
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import Qt

from models.network import NetworkModel
from views.canvas import NetworkCanvas
from views.widgets.side_panel import SidePanel
from controllers.network_controller import NetworkController
from config.constants import MAIN_WINDOW
from config.templates import DEVICE_TEMPLATES


class MainWindow(QMainWindow):
    """Главное окно с панелью, канвасом и контроллером."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Network Visualizer v3.0")
        self.resize(MAIN_WINDOW["width"], MAIN_WINDOW["height"])
        self.setMinimumSize(
            MAIN_WINDOW["min_width"], MAIN_WINDOW["min_height"],
        )

        self.model = NetworkModel()
        self.canvas = NetworkCanvas(self.model)
        self.side_panel = SidePanel()
        self.controller = NetworkController(
            self.model, self.canvas, self.side_panel, self,
        )

        self._setup_ui()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_statusbar()
        self._create_demo_network()

    # ========================================================
    #  UI
    # ========================================================

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self.side_panel)
        layout.addWidget(self.canvas, 1)

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Файл")
        self._add_action(file_menu, "Новый проект",
                         QKeySequence.StandardKey.New, self._new_project)
        self._add_action(file_menu, "Сохранить",
                         QKeySequence.StandardKey.Save, self._save_project)
        self._add_action(file_menu, "Загрузить",
                         QKeySequence.StandardKey.Open, self._load_project)
        file_menu.addSeparator()
        self._add_action(file_menu, "Выход",
                         QKeySequence.StandardKey.Quit, self.close)

        edit_menu = menubar.addMenu("Правка")
        self._add_action(edit_menu, "Создать канал...",
                         None, self.controller.create_channel)
        self._add_action(edit_menu, "Управление группами...",
                         None, self.controller.manage_groups)
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Удалить выбранное",
                         QKeySequence.StandardKey.Delete,
                         self.controller.delete_selected)

        help_menu = menubar.addMenu("Помощь")
        self._add_action(help_menu, "О программе", None, self._show_about)

    def _setup_toolbar(self) -> None:
        tb = QToolBar("Основная")
        tb.setMovable(False)
        self.addToolBar(tb)

        actions = [
            ("📄 Новый", self._new_project),
            ("💾 Сохранить", self._save_project),
            ("📂 Загрузить", self._load_project),
            None,  # separator
            ("🔗 Канал", self.controller.create_channel),
            ("📊 Группы", self.controller.manage_groups),
            None,
            ("🗑️ Удалить", self.controller.delete_selected),
        ]

        for item in actions:
            if item is None:
                tb.addSeparator()
                continue
            text, slot = item
            action = QAction(text, self)
            action.triggered.connect(slot)
            tb.addAction(action)

    def _setup_statusbar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage(
            "ПКМ на канвасе — создать устройство  ·  "
            "ПКМ на ■ — начать соединение  ·  "
            "Двойной клик — редактировать  ·  "
            "Ctrl+ЛКМ — панорамирование  ·  "
            "Колесико — масштаб"
        )

    @staticmethod
    def _add_action(menu, text: str, shortcut, slot) -> None:
        action = QAction(text, menu)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        menu.addAction(action)

    # ========================================================
    #  ДЕМО-СЕТЬ
    # ========================================================

    def _create_demo_network(self) -> None:
        mc = self.model.add_device_from_template("Магистральный кросс", 250, 200)
        oc = self.model.add_device_from_template("Оптический кросс", 250, 500)
        ag = self.model.add_device_from_template("Агрегатор 100Gb", 650, 200)
        sw = self.model.add_device_from_template("Коммутатор 10Gb", 650, 550)
        srv = self.model.add_device_from_template("Сервер 100Gb", 1050, 200)
        stor = self.model.add_device_from_template("Хранилище", 1050, 550)

        g1 = self.model.create_group("Магистраль МСК-СПб", "#f59e0b")
        g2 = self.model.create_group("ЦОД Storage", "#8b5cf6")
        g3 = self.model.create_group("Резерв", "#ef4444")

        pairs = [
            (mc, oc, "Optical MPO", 5.0, g1),
            (oc, ag, "Optical LC", 3.0, g1),
            (ag, sw, "Optical LC", 2.0, g3),
            (ag, srv, "Infiniband", 3.0, g2),
            (sw, stor, "Ethernet", 1.0, None),
        ]

        for dev1, dev2, cable, length, group in pairs:
            if not dev1 or not dev2:
                continue
            if not dev1.output_ports or not dev2.input_ports:
                continue
            self.model.add_connection(
                dev1.output_ports[0], dev2.input_ports[0],
                cable, length, group.id if group else None,
            )

    # ========================================================
    #  ФАЙЛОВЫЕ ОПЕРАЦИИ
    # ========================================================

    def _new_project(self) -> None:
        reply = QMessageBox.question(
            self, "Новый проект",
            "Создать новый проект? Несохранённые данные будут потеряны.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.model.devices.clear()
            self.model.connections.clear()
            self.model.groups.clear()
            self.model.next_device_id = 0
            self.model.next_group_id = 0
            self.model.notify()

    def _save_project(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", "", "JSON Files (*.json)",
        )
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.model.to_dict(), f, indent=2, ensure_ascii=False)
            self.status_bar.showMessage(f"Сохранено: {filename}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось сохранить: {e}")

    def _load_project(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Загрузить проект", "", "JSON Files (*.json)",
        )
        if not filename:
            return
        try:
            with open(filename, "r", encoding="utf-8") as f:
                self.model.from_dict(json.load(f))
            self.status_bar.showMessage(f"Загружено: {filename}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось загрузить: {e}")

    # ========================================================
    #  ПРОЧЕЕ
    # ========================================================

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "О программе",
            "<h2>Network Visualizer v3.0</h2>"
            "<p>Визуализация сетевой инфраструктуры</p>"
            "<p><b>Возможности:</b></p>"
            "<ul>"
            "<li>Создание устройств из шаблонов</li>"
            "<li>Типы разъёмов: SFP LC, SFP MPO, FC, Ethernet, RJ45</li>"
            "<li>Скорости: 1Gb, 10Gb, 100Gb</li>"
            "<li>Кабели: Optical LC, Optical MPO, Infiniband, Ethernet</li>"
            "<li>Группировка соединений в каналы</li>"
            "<li>Стандартные длины кабелей</li>"
            "</ul>"
        )