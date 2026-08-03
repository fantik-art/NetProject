import sys
from PyQt6.QtWidgets import QApplication
from .server_window import ServerWindow


def run_server(port: int = 5555):
    """Запуск сервера"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Стили
    app.setStyleSheet("""
        QMainWindow { background-color: #1e1e2e; color: #cdd6f4; }
        QGroupBox { 
            font-weight: bold; 
            border: 1px solid #45475a; 
            border-radius: 5px; 
            margin-top: 10px; 
            padding-top: 10px;
            color: #cdd6f4;
        }
        QGroupBox::title { 
            subcontrol-origin: margin; 
            left: 10px; 
            padding: 0 5px;
            color: #89b4fa;
        }
        QPushButton { 
            padding: 8px 15px; 
            border: 1px solid #45475a; 
            border-radius: 3px; 
            background-color: #313244;
            color: #cdd6f4;
        }
        QPushButton:hover { background-color: #45475a; }
        QTextEdit {
            background-color: #11111b;
            color: #a6e3a1;
            border: 1px solid #45475a;
            font-family: Consolas, monospace;
        }
        QListWidget, QTreeWidget {
            background-color: #313244;
            color: #cdd6f4;
            border: 1px solid #45475a;
        }
        QStatusBar {
            background-color: #313244;
            color: #a6adc8;
        }
    """)
    
    window = ServerWindow(port)
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    run_server()