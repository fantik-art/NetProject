from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QPushButton, QLabel, 
    QDialogButtonBox, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class LoginDialog(QDialog):
    """Диалог входа в систему"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Вход в систему")
        self.setFixedSize(400, 380)
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # Заголовок
        title = QLabel("Network Visualizer")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #89b4fa;")
        layout.addWidget(title)
        
        subtitle = QLabel("Многопользовательский редактор сети")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #a6adc8;")
        layout.addWidget(subtitle)
        
        # Сервер
        server_group = QGroupBox("Подключение к серверу")
        server_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #45475a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #cdd6f4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #89b4fa;
            }
        """)
        server_form = QFormLayout()
        server_form.setSpacing(8)
        
        self.server_input = QLineEdit("localhost")
        self.server_input.setPlaceholderText("Адрес сервера")
        self.server_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border-color: #89b4fa;
            }
        """)
        server_form.addRow("Сервер:", self.server_input)
        
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(5555)
        self.port_input.setStyleSheet("""
            QSpinBox {
                padding: 8px;
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 3px;
            }
        """)
        server_form.addRow("Порт:", self.port_input)
        
        server_group.setLayout(server_form)
        layout.addWidget(server_group)
        
        # Учетные данные
        auth_group = QGroupBox("Учетные данные")
        auth_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #45475a;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                color: #cdd6f4;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #89b4fa;
            }
        """)
        auth_form = QFormLayout()
        auth_form.setSpacing(8)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("admin, manager1, operator1, viewer1")
        self.username_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border-color: #89b4fa;
            }
        """)
        auth_form.addRow("Пользователь:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Пароль (по умолчанию: имя+123)")
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border-color: #89b4fa;
            }
        """)
        auth_form.addRow("Пароль:", self.password_input)
        
        # Подсказка
        hint = QLabel("Тестовые: admin/admin123, manager1/manager123")
        hint.setStyleSheet("color: #585b70; font-size: 10px;")
        hint.setWordWrap(True)
        auth_form.addRow(hint)
        
        auth_group.setLayout(auth_form)
        layout.addWidget(auth_group)
        
        # Кнопки
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        # Стилизуем кнопки
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("🚀 Войти")
        ok_btn.setMinimumHeight(35)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #b4d0fb;
            }
            QPushButton:pressed {
                background-color: #74a8f7;
            }
        """)
        
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText("Отмена")
        cancel_btn.setMinimumHeight(35)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #45475a;
                color: #cdd6f4;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
        """)
        
        layout.addWidget(buttons)
        self.setLayout(layout)
        
        # Общий стиль диалога
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
        """)
    
    def get_connection_info(self) -> dict:
        """Получение данных для подключения"""
        return {
            'host': self.server_input.text().strip() or 'localhost',
            'port': self.port_input.value(),
            'username': self.username_input.text().strip(),
            'password': self.password_input.text()
        }