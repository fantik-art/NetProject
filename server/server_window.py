from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
    QSplitter, QStatusBar, QGroupBox, QListWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from .server_app import ServerApp


class ServerWindow(QMainWindow):
    """Окно управления сервером"""

    def __init__(self, port: int = 5555):
        super().__init__()
        self.setWindowTitle("Сервер Network Visualizer")
        self.setGeometry(100, 100, 1000, 700)

        self.server = ServerApp(port)

        self.setup_ui()
        self.setup_connections()

        # Запускаем сервер с небольшой задержкой
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self.start_server)
    
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout()
        
        # Верхняя панель управления
        control_panel = QHBoxLayout()
        
        self.start_btn = QPushButton("▶ Запустить")
        self.start_btn.clicked.connect(self.server.start)
        control_panel.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹ Остановить")
        self.stop_btn.clicked.connect(self.server.stop)
        control_panel.addWidget(self.stop_btn)
        
        control_panel.addStretch()
        
        self.status_label = QLabel("Порт: 5555 | Статус: Запущен")
        control_panel.addWidget(self.status_label)
        
        layout.addLayout(control_panel)
        
        # Основной сплиттер
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Левая панель - пользователи и сектора
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        
        # Пользователи
        users_group = QGroupBox("Пользователи онлайн")
        users_layout = QVBoxLayout()
        self.users_list = QListWidget()
        users_layout.addWidget(self.users_list)
        users_group.setLayout(users_layout)
        left_layout.addWidget(users_group)
        
        # Сектора
        sectors_group = QGroupBox("Сектора")
        sectors_layout = QVBoxLayout()
        self.sectors_tree = QTreeWidget()
        self.sectors_tree.setHeaderLabels(["Сектор", "Пользователей", "Заблокирован"])
        sectors_layout.addWidget(self.sectors_tree)
        sectors_group.setLayout(sectors_layout)
        left_layout.addWidget(sectors_group)
        
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)
        
        # Правая панель - логи
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        
        log_group = QGroupBox("Логи сервера")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)
        
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)
        
        splitter.setSizes([350, 650])
        layout.addWidget(splitter)
        
        central.setLayout(layout)
        
        # Статус бар
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Сервер запущен")
        
        # Таймер обновления
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_info)
        self.update_timer.start(3000)
    
    def setup_connections(self):
        self.server.log_message.connect(self.log)
        self.server.user_connected.connect(self.on_user_connected)
        self.server.user_disconnected.connect(self.on_user_disconnected)
    
    def log(self, message: str):
        self.log_text.append(message)
    
    def on_user_connected(self, user_id: int, username: str):
        self.users_list.addItem(f"🟢 {username} (ID: {user_id})")
        self.log(f"✓ Подключился: {username}")
    
    def on_user_disconnected(self, user_id: int, username: str):
        # Находим и удаляем из списка
        for i in range(self.users_list.count()):
            if username in self.users_list.item(i).text():
                self.users_list.takeItem(i)
                break
        self.log(f"✗ Отключился: {username}")
    
    def update_info(self):
        """Обновление информации о секторах"""
        self.sectors_tree.clear()
        
        for sector in self.server.state.sectors.values():
            item = QTreeWidgetItem([
                sector.name,
                str(len(sector.active_users)),
                "🔒" if sector.is_locked() else "🔓"
            ])
            
            if sector.is_locked():
                item.setForeground(0, QColor(255, 152, 0))
            
            self.sectors_tree.addTopLevelItem(item)
    
    def closeEvent(self, event):
        self.server.stop()
        self.update_timer.stop()
        event.accept()

    def start_server(self):
        """Запуск сервера"""
        if self.server.start():
            self.log("Сервер запущен")
        else:
            self.log("Ошибка запуска сервера")