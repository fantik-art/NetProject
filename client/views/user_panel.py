from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QGroupBox, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class UserPanel(QGroupBox):
    """Панель отображения пользователей в секторе"""

    def __init__(self, parent=None):
        super().__init__("👥 Пользователи в секторе", parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.info_label = QLabel("Войдите в сектор")
        self.info_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(self.info_label)

        self.users_list = QListWidget()
        self.users_list.setStyleSheet("""
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #45475a;
            }
        """)
        layout.addWidget(self.users_list)

        self.setLayout(layout)

    def update_users(self, users: list):
        """Обновление списка пользователей"""
        self.users_list.clear()
        self.info_label.setText(f"Пользователей: {len(users)}")

        role_icons = {
            'admin': '👑',
            'manager': '🔧',
            'operator': '⚙️',
            'viewer': '👁'
        }

        for user in users:
            username = user.get('username', 'Unknown')
            role = user.get('role', 'viewer')
            is_online = user.get('is_online', False)

            icon = role_icons.get(role, '👤')
            status = "🟢" if is_online else "⚫"
            item_text = f"{status} {icon} {username} ({role})"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, user.get('id', 0))

            if not is_online:
                item.setForeground(QColor('#585b70'))

            self.users_list.addItem(item)

    def add_user(self, user: dict):
        """Добавление пользователя"""
        username = user.get('username', 'Unknown')
        role = user.get('role', 'viewer')

        # Проверяем, нет ли уже такого пользователя
        for i in range(self.users_list.count()):
            item = self.users_list.item(i)
            if username in item.text():
                return

        role_icons = {
            'admin': '👑',
            'manager': '🔧',
            'operator': '⚙️',
            'viewer': '👁'
        }

        icon = role_icons.get(role, '👤')
        item = QListWidgetItem(f"🟢 {icon} {username} ({role})")
        self.users_list.addItem(item)

        self.info_label.setText(f"Пользователей: {self.users_list.count()}")

    def remove_user(self, user_id: int):
        """Удаление пользователя"""
        for i in range(self.users_list.count()):
            item = self.users_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == user_id:
                self.users_list.takeItem(i)
                break

        self.info_label.setText(f"Пользователей: {self.users_list.count()}")