from enum import Enum, auto


class MessageType(Enum):
    """Типы сообщений протокола"""
    # Аутентификация
    LOGIN_REQUEST = auto()
    LOGIN_RESPONSE = auto()
    LOGOUT = auto()

    # Сектора и представления
    SECTOR_EDIT = auto()  # ДОБАВИТЬ
    SECTORS_LIST = auto()
    SECTOR_JOIN = auto()
    SECTOR_LEAVE = auto()
    VIEW_CHANGE = auto()  # Изменение представления (весь/сектор/несколько)

    # Блокировки
    LOCK_REQUEST = auto()
    LOCK_RESPONSE = auto()
    UNLOCK_REQUEST = auto()
    UNLOCK_RESPONSE = auto()
    LOCK_NOTIFICATION = auto()

    # Устройства
    DEVICE_ADD = auto()
    DEVICE_MOVE = auto()
    DEVICE_EDIT = auto()
    DEVICE_DELETE = auto()

    # Соединения
    CONNECTION_ADD = auto()
    CONNECTION_DELETE = auto()

    # Группы
    GROUP_CREATE = auto()
    GROUP_DELETE = auto()

    # Синхронизация
    FULL_STATE = auto()
    DELTA_UPDATE = auto()
    PING = auto()
    PONG = auto()

    # Пользователи
    USER_JOINED = auto()
    USER_LEFT = auto()
    USERS_LIST = auto()


class UserRole(Enum):
    """Роли пользователей"""
    ADMIN = "admin"  # Видит всё, может всё
    MANAGER = "manager"  # Видит свои сектора + может видеть всю сеть (read-only)
    OPERATOR = "operator"  # Видит и редактирует только свои сектора
    VIEWER = "viewer"  # Только просмотр назначенных секторов


class DeviceCategory(Enum):
    """Категории устройств"""
    GLOBAL_INPUT = "Входные (глобальные)"
    LOCAL_INPUT = "Входные (локальные)"
    SWITCHES = "Коммутаторы"
    SERVERS = "Сервера"


class PortType(Enum):
    """Типы портов"""
    INPUT = "input"
    OUTPUT = "output"


class ViewMode(Enum):
    """Режимы просмотра сети"""
    FULL_NETWORK = "full"  # Вся сеть целиком
    SINGLE_SECTOR = "single"  # Один сектор
    MULTIPLE_SECTORS = "multi"  # Несколько выбранных секторов