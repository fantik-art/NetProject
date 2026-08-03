from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QGroupBox, QLabel
)
from PyQt6.QtCore import pyqtSignal, Qt


class SectorPanel(QGroupBox):
    """Панель отображения и выбора секторов"""

    sector_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__("📁 Сектора", parent)
        self._sectors_cache = []  # Кеш для доступа извне
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.info_label = QLabel("Выберите сектор для работы")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(self.info_label)

        self.sectors_list = QListWidget()
        self.sectors_list.itemClicked.connect(self._on_sector_clicked)
        self.sectors_list.setStyleSheet("""
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #45475a;
                border-radius: 3px;
            }
            QListWidget::item:hover {
                background-color: #45475a;
            }
            QListWidget::item:selected {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
        """)
        layout.addWidget(self.sectors_list)

        self.setLayout(layout)

    def update_sectors(self, sectors: list):
        """Обновление списка секторов"""
        self._sectors_cache = sectors
        self.sectors_list.clear()

        if not sectors:
            self.info_label.setText("Нет доступных секторов")
            return

        self.info_label.setText(f"Доступно секторов: {len(sectors)}")

        for sector in sectors:
            name = sector.get('name', 'Без имени')
            users = sector.get('active_users', 0)
            devices = sector.get('devices_count', 0)
            is_locked = sector.get('is_locked', False)

            lock_icon = "🔒" if is_locked else "🔓"
            item_text = f"{lock_icon} {name}\n👥 {users} чел. | 🔌 {devices} устр."

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, sector.get('id', 0))
            self.sectors_list.addItem(item)

    def _on_sector_clicked(self, item: QListWidgetItem):
        """Обработка выбора сектора"""
        sector_id = item.data(Qt.ItemDataRole.UserRole)
        if sector_id:
            self.sector_selected.emit(sector_id)