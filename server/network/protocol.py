import json
import struct
from PyQt6.QtNetwork import QTcpSocket
from common.protocol import Message


class MessageStream:
    """Потоковая обработка сообщений для TCP сокета (НЕ QObject)"""
    
    def __init__(self, socket: QTcpSocket):
        self.socket = socket
        self.expected_size: int = 0
        
        self.socket.readyRead.connect(self._on_ready_read)
    
    def _on_ready_read(self):
        """Обработка входящих данных"""
        while self.socket.bytesAvailable() > 0:
            if self.expected_size == 0:
                if self.socket.bytesAvailable() < 4:
                    return
                header = self.socket.read(4)
                if len(header) < 4:
                    return
                self.expected_size = struct.unpack('!I', header)[0]
                
                if self.expected_size > 10 * 1024 * 1024:
                    print(f"Слишком большое сообщение: {self.expected_size}")
                    self.expected_size = 0
                    return
            
            if self.socket.bytesAvailable() >= self.expected_size:
                data = self.socket.read(self.expected_size)
                if len(data) == self.expected_size:
                    self.expected_size = 0
                    self._on_message_received(data)
                else:
                    self.expected_size -= len(data)
            else:
                return
    
    def _on_message_received(self, data: bytes):
        """Переопределяется в наследниках"""
        pass
    
    def send_message(self, message: Message) -> bool:
        """Отправка сообщения"""
        if self.socket.isOpen() and self.socket.isWritable():
            try:
                data = message.serialize()
                written = self.socket.write(data)
                self.socket.flush()
                return written > 0
            except Exception as e:
                print(f"Ошибка отправки: {e}")
                return False
        return False