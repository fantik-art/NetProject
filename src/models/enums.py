"""Перечисления приложения."""

from enum import Enum


class PortType(Enum):
    """Направление порта."""
    INPUT = "input"
    OUTPUT = "output"


class DeviceCategory(Enum):
    """Категория устройства."""
    GLOBAL_INPUT = "Входные (глобальные)"
    LOCAL_INPUT = "Входные (локальные)"
    SWITCHES = "Коммутаторы"
    SERVERS = "Сервера"


# Соответствие строк из конфига и Enum
CATEGORY_MAP = {
    "GLOBAL_INPUT": DeviceCategory.GLOBAL_INPUT,
    "LOCAL_INPUT": DeviceCategory.LOCAL_INPUT,
    "SWITCHES": DeviceCategory.SWITCHES,
    "SERVERS": DeviceCategory.SERVERS,
}

CATEGORY_KEY_MAP = {v: k for k, v in CATEGORY_MAP.items()}