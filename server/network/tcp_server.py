from typing import Dict, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QTcpServer, QTcpSocket, QHostAddress

from common.protocol import Message, MessageType


class ClientHandler(QObject):
    """Обработчик клиента - QObject для сигналов"""
    
    message_received = pyqtSignal(Message)
    disconnected = pyqtSignal()
    
    def __init__(self, socket: QTcpSocket):
        super().__init__()
        self.socket = socket
        self.expected_size: int = 0
        
        self.socket.readyRead.connect(self._on_ready_read)
        self.socket.disconnected.connect(self.disconnected.emit)
    
    def _on_ready_read(self):
        """Чтение данных из сокета"""
        while self.socket.bytesAvailable() > 0:
            if self.expected_size == 0:
                if self.socket.bytesAvailable() < 4:
                    return
                header = self.socket.read(4)
                if len(header) < 4:
                    return
                import struct
                self.expected_size = struct.unpack('!I', header)[0]
                
                if self.expected_size > 10 * 1024 * 1024:
                    print(f"Слишком большое сообщение: {self.expected_size}")
                    self.expected_size = 0
                    return
            
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
    
    def close(self):
        """Закрытие соединения"""
        try:
            self.socket.disconnectFromHost()
        except Exception:
            pass


class TcpServer(QObject):
    """TCP сервер для многопользовательской работы"""
    
    new_connection = pyqtSignal(int, QTcpSocket)
    client_disconnected = pyqtSignal(int)
    message_received = pyqtSignal(int, Message)
    
    def __init__(self, port: int = 5555):
        super().__init__()
        self.port = port
        self.server = QTcpServer()
        self.server.newConnection.connect(self._on_new_connection)
        
        # Активные соединения: user_id -> ClientHandler
        self.clients: Dict[int, ClientHandler] = {}
        # Ожидающие аутентификации: socket -> (handler, username)
        self.pending: Dict[QTcpSocket, tuple] = {}
    
    def start(self) -> bool:
        """Запуск сервера"""
        if self.server.isListening():
            print("Сервер уже запущен")
            return True
        
        if self.server.listen(QHostAddress.SpecialAddress.AnyIPv4, self.port):
            print(f"Сервер запущен на порту {self.port}")
            return True
        print(f"Ошибка запуска: {self.server.errorString()}")
        return False
    
    def stop(self):
        """Остановка сервера"""
        for handler in list(self.clients.values()):
            handler.close()
        self.clients.clear()
        
        for socket, (handler, _) in list(self.pending.items()):
            handler.close()
        self.pending.clear()
        
        if self.server.isListening():
            self.server.close()
    
    def _on_new_connection(self):
        """Обработка нового подключения"""
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            
            # Создаем обработчик для нового подключения
            handler = ClientHandler(socket)
            
            # Подключаем сигнал получения сообщения
            handler.message_received.connect(
                lambda msg, h=handler, s=socket: self._handle_pending_message(msg, h, s)
            )
            
            # Подключаем сигнал отключения
            handler.disconnected.connect(
                lambda h=handler, s=socket: self._handle_pending_disconnect(h, s)
            )
            
            # Сохраняем в ожидающих
            self.pending[socket] = (handler, "")
            
            print(f"Новое подключение: {socket.peerAddress().toString()}")
    
    def _handle_pending_message(self, message: Message, handler: ClientHandler, socket: QTcpSocket):
        """Обработка сообщения от неаутентифицированного клиента"""
        if message.type == MessageType.LOGIN_REQUEST:
            # Сохраняем username
            username = message.payload.get('username', '')
            self.pending[socket] = (handler, username)
            
            # Передаем в ServerApp (user_id=0 для новых)
            self.message_received.emit(0, message)
    
    def _handle_pending_disconnect(self, handler: ClientHandler, socket: QTcpSocket):
        """Обработка отключения неаутентифицированного клиента"""
        if socket in self.pending:
            del self.pending[socket]
        handler.deleteLater()
        socket.deleteLater()
    
    def register_client(self, user_id: int, username: str):
        """Регистрация аутентифицированного клиента"""
        # Ищем сокет по username
        target_socket = None
        target_handler = None
        
        for socket, (handler, pending_username) in list(self.pending.items()):
            if pending_username == username:
                target_socket = socket
                target_handler = handler
                break
        
        if not target_socket or not target_handler:
            print(f"Не найден сокет для {username}")
            return
        
        # Удаляем из pending
        del self.pending[target_socket]
        
        # Закрываем старое соединение если есть
        if user_id in self.clients:
            old_handler = self.clients[user_id]
            old_handler.message_received.disconnect()
            old_handler.disconnected.disconnect()
            old_handler.close()
            old_handler.deleteLater()
        
        # Отключаем старые сигналы
        try:
            target_handler.message_received.disconnect()
        except Exception:
            pass
        try:
            target_handler.disconnected.disconnect()
        except Exception:
            pass
        
        # Подключаем новые сигналы для аутентифицированного клиента
        target_handler.message_received.connect(
            lambda msg, uid=user_id: self.message_received.emit(uid, msg)
        )
        target_handler.disconnected.connect(
            lambda uid=user_id: self._on_client_disconnected(uid)
        )
        
        self.clients[user_id] = target_handler
        self.new_connection.emit(user_id, target_socket)
        
        print(f"Клиент {username} зарегистрирован как user_id={user_id}")
    
    def _on_client_disconnected(self, user_id: int):
        """Обработка отключения аутентифицированного клиента"""
        if user_id in self.clients:
            handler = self.clients[user_id]
            handler.deleteLater()
            del self.clients[user_id]
        
        self.client_disconnected.emit(user_id)
        print(f"Клиент {user_id} отключился")
    
    def send_to_user(self, user_id: int, message: Message) -> bool:
        """Отправка сообщения пользователю"""
        handler = self.clients.get(user_id)
        if handler:
            return handler.send_message(message)
        return False
    
    def broadcast(self, message: Message, exclude_user: int = 0):
        """Рассылка всем подключенным клиентам"""
        for user_id, handler in list(self.clients.items()):
            if user_id != exclude_user:
                handler.send_message(message)
    
    def disconnect_user(self, user_id: int):
        """Отключение пользователя"""
        handler = self.clients.get(user_id)
        if handler:
            handler.close()