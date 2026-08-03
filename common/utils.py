import hashlib
import time
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


class HeartbeatManager(QObject):
    """Менеджер heartbeat для проверки соединения"""
    ping_sent = pyqtSignal()
    timeout = pyqtSignal()
    
    def __init__(self, interval: int = 5000, timeout_ms: int = 15000):
        super().__init__()
        self.interval = interval
        self.timeout_ms = timeout_ms
        self.last_pong = time.time()
        
        self.ping_timer = QTimer()
        self.ping_timer.timeout.connect(self._send_ping)
        self.ping_timer.start(interval)
        
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_timeout)
        self.check_timer.start(timeout_ms)
    
    def _send_ping(self):
        self.ping_sent.emit()
    
    def _check_timeout(self):
        if time.time() - self.last_pong > self.timeout_ms / 1000:
            self.timeout.emit()
    
    def pong_received(self):
        self.last_pong = time.time()
    
    def stop(self):
        self.ping_timer.stop()
        self.check_timer.stop()


def hash_password(password: str) -> str:
    """Хеширование пароля"""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_id() -> int:
    """Генерация уникального ID на основе времени"""
    return int(time.time() * 1000) % 1000000