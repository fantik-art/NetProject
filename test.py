from PyQt6.QtWidgets import *

from PyQt6.QtCore import *

from PyQt6.QtGui import *

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Сложное окно")

        # Центральный виджет
        central = QWidget()
        self.setCentralWidget(central)
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Создаём вкладки в статус-баре
        tabs = QTabWidget()
        tabs.setMaximumHeight(40)

        # Вкладка "Информация"
        info_tab = QWidget()
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(5, 0, 5, 0)
        info_layout.addWidget(QLabel("Готово"))
        info_tab.setLayout(info_layout)

        # Вкладка "Логи"
        logs_tab = QWidget()
        logs_layout = QHBoxLayout()
        logs_layout.setContentsMargins(5, 0, 5, 0)
        logs_layout.addWidget(QLabel("Нет ошибок"))
        logs_tab.setLayout(logs_layout)

        tabs.addTab(info_tab, "📋 Информация")
        tabs.addTab(logs_tab, "📝 Логи")

        status_bar.addPermanentWidget(tabs)



        # # Главный горизонтальный layout
        main_layout = QHBoxLayout()
        #
        # # ===== ЛЕВАЯ ПАНЕЛЬ =====
        # left_panel = QWidget()
        # left_layout = QVBoxLayout()
        #
        # # Заголовок
        # left_layout.addWidget(QLabel("Панель инструментов"))
        #
        # # Кнопки
        # left_layout.addWidget(QPushButton("🔍 Поиск"))
        # left_layout.addWidget(QPushButton("📁 Открыть"))
        # left_layout.addWidget(QPushButton("💾 Сохранить"))
        #
        # # Растяжка
        # left_layout.addStretch()
        #
        # left_panel.setLayout(left_layout)
        # left_panel.setFixedWidth(200)
        #
        # # ===== ПРАВАЯ ЧАСТЬ =====
        # right_panel = QWidget()
        # right_layout = QVBoxLayout()
        #
        # # Верхняя панель с кнопками
        # top_bar = QHBoxLayout()
        # top_bar.addWidget(QPushButton("←"))
        # top_bar.addWidget(QPushButton("→"))
        # top_bar.addStretch()
        # top_bar.addWidget(QPushButton("⚙"))
        # right_layout.addLayout(top_bar)
        #
        # # Разделитель
        # splitter = QSplitter(Qt.Orientation.Vertical)
        #
        # # Верхняя часть: таблица
        # table = QTableWidget(5, 3)
        # table.setHorizontalHeaderLabels(["Имя", "Возраст", "Email"])
        # splitter.addWidget(table)
        #
        # # Нижняя часть: текст
        # text = QTextEdit()
        # splitter.addWidget(text)
        #
        # right_layout.addWidget(splitter)
        #
        # right_panel.setLayout(right_layout)

        table = DeviceTable()

        # Добавляем обе панели в главный layout
        main_layout.addWidget(table)

        central.setLayout(main_layout)


class DeviceTable(QTableWidget):
    def __init__(self):
        super().__init__()

        # Настройка
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["ID", "Название", "Тип", "Статус"])

        # Режимы
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)

        # Данные
        self.devices = [
            {'id': 1, 'name': 'Коммутатор 1', 'type': 'Switch', 'status': 'online'},
            {'id': 2, 'name': 'Сервер 1', 'type': 'Server', 'status': 'offline'},
            {'id': 3, 'name': 'Маршрутизатор', 'type': 'Router', 'status': 'online'},
        ]

        self.load_data()

        # Сигнал
        self.cellClicked.connect(self.on_click)

    def load_data(self):
        self.setRowCount(len(self.devices))

        for row, device in enumerate(self.devices):
            # ID
            id_item = QTableWidgetItem(str(device['id']))
            id_item.setData(Qt.ItemDataRole.UserRole, device['id'])
            self.setItem(row, 0, id_item)

            # Название
            self.setItem(row, 1, QTableWidgetItem(device['name']))

            # Тип
            self.setItem(row, 2, QTableWidgetItem(device['type']))

            # Статус
            status_item = QTableWidgetItem(device['status'])
            if device['status'] == 'online':
                status_item.setForeground(QColor('green'))
            else:
                status_item.setForeground(QColor('red'))
            self.setItem(row, 3, status_item)

    def on_click(self, row, col):
        item = self.item(row, 0)
        device_id = item.data(Qt.ItemDataRole.UserRole)
        print(f"Выбрано устройство с ID: {device_id}")


import sys
app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec())