from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtNetwork import QTcpSocket, QAbstractSocket, QHostAddress

from common.protocol import Message, MessageType
import struct


class TcpClient(QObject):
    """TCP клиент для связи с сервером"""
    
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    message_received = pyqtSignal(Message)
    connection_error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.socket = QTcpSocket()
        self.socket.connected.connect(self.connected)
        self.socket.disconnected.connect(self.disconnected)
        self.socket.readyRead.connect(self._on_ready_read)
        self.socket.errorOccurred.connect(self._on_error)
        
        self.buffer = bytearray()
        self.expected_size = 0
        
        # Таймер реконнекта
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self._try_reconnect)
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 3000  # 3 секунды
        
        # Параметры подключения
        self.host = "localhost"
        self.port = 5555
    
    def connect_to_server(self, host: str = "localhost", port: int = 5555):
        """Подключение к серверу"""
        self.host = host
        self.port = port
        self.socket.connectToHost(host, port)
    
    def disconnect_from_server(self):
        """Отключение от сервера"""
        self.reconnect_timer.stop()
        if self.socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            self.socket.disconnectFromHost()
    
    def send_message(self, message: Message) -> bool:
        """Отправка сообщения"""
        if self.socket.state() == QAbstractSocket.SocketState.ConnectedState:
            try:
                data = message.serialize()
                written = self.socket.write(data)
                self.socket.flush()
                return written > 0
            except Exception as e:
                print(f"Ошибка отправки: {e}")
                return False
        return False
    
    def _on_ready_read(self):
        """Чтение данных"""
        while self.socket.bytesAvailable() > 0:
            if self.expected_size == 0:
                # Ждем заголовок
                if self.socket.bytesAvailable() < 4:
                    return
                header = self.socket.read(4)
                if len(header) < 4:
                    return
                self.expected_size = struct.unpack('!I', header)[0]
            
            # Читаем тело
            if self.socket.bytesAvailable() >= self.expected_size:
                data = self.socket.read(self.expected_size)
                if len(data) == self.expected_size:
                    self.expected_size = 0
                    try:
                        message = Message.deserialize(data)
                        self.message_received.emit(message)
                    except Exception as e:
                        print(f"Ошибка десериализации: {e}")
            else:
                return
    
    def _on_error(self, error: QAbstractSocket.SocketError):
        """Обработка ошибок"""
        if error == QAbstractSocket.SocketError.RemoteHostClosedError:
            self.connection_error.emit("Сервер закрыл соединение")
        elif error == QAbstractSocket.SocketError.ConnectionRefusedError:
            self.connection_error.emit("Сервер недоступен")
        elif error == QAbstractSocket.SocketError.HostNotFoundError:
            self.connection_error.emit("Хост не найден")
        elif error == QAbstractSocket.SocketError.NetworkError:
            self.connection_error.emit("Сетевая ошибка")
            self._start_reconnect()
        else:
            self.connection_error.emit(self.socket.errorString())
    
    def _start_reconnect(self):
        """Запуск попыток переподключения"""
        if not self.reconnect_timer.isActive():
            self.reconnect_attempts = 0
            self.reconnect_timer.start(self.reconnect_delay)
    
    def _try_reconnect(self):
        """Попытка переподключения"""
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts:
            self.reconnect_timer.stop()
            self.connection_error.emit("Превышено количество попыток подключения")
            return
        
        print(f"Попытка переподключения {self.reconnect_attempts}/{self.max_reconnect_attempts}")
        self.socket.connectToHost(self.host, self.port)
        
        # Проверяем подключение через небольшую задержку
        QTimer.singleShot(1000, self._check_reconnect)
    
    def _check_reconnect(self):
        """Проверка успешности переподключения"""
        if self.socket.state() == QAbstractSocket.SocketState.ConnectedState:
            self.reconnect_timer.stop()
            self.reconnect_attempts = 0
            self.connected.emit()
    
    def is_connected(self) -> bool:
        return self.socket.state() == QAbstractSocket.SocketState.ConnectedState