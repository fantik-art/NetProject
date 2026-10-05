"""
Шаблоны устройств для фабрики.
Каждый шаблон — это готовая конфигурация устройства с портами.
"""

# Формат: (имя_порта, разъём, скорость)
# Каждый шаблон содержит: device_type, category, model, input_ports, output_ports


def _ports(prefix: str, count: int, connector: str, speed: str) -> list:
    """Утилита: генерирует список однотипных портов."""
    return [(f"{prefix}{i+1}", connector, speed) for i in range(count)]


DEVICE_TEMPLATES = {
    # ============== КОММУТАТОРЫ ==============
    "Агрегатор 100Gb": {
        "device_type": "Aggregator",
        "category": "SWITCHES",
        "model": "AG-100G-32",
        "input_ports":  _ports("IN ", 32, "SFP LC", "100Gb"),
        "output_ports": _ports("OUT ", 32, "SFP LC", "100Gb"),
    },
    "Коммутатор 10Gb": {
        "device_type": "Switch",
        "category": "SWITCHES",
        "model": "SW-10G-24",
        "input_ports":  _ports("IN ", 24, "SFP LC", "10Gb"),
        "output_ports": _ports("OUT ", 24, "SFP LC", "10Gb"),
    },
    "Коммутатор 1Gb": {
        "device_type": "Switch",
        "category": "SWITCHES",
        "model": "SW-1G-48",
        "input_ports":  _ports("IN ", 2, "SFP LC", "1Gb"),
        "output_ports": [
            ("eth1", "Ethernet", "1Gb"),
            ("eth2", "Ethernet", "1Gb"),
            ("eth3", "Ethernet", "1Gb"),
            ("eth4", "Ethernet", "1Gb"),
            ("eth5", "Ethernet", "1Gb"),
            ("eth6", "Ethernet", "1Gb"),
            ("eth7", "Ethernet", "1Gb"),
            ("eth8", "Ethernet", "1Gb"),
        ],
    },
    "Маршрутизатор": {
        "device_type": "Router",
        "category": "SWITCHES",
        "model": "RT-10G-8",
        "input_ports": [
            ("WAN 1", "SFP LC", "10Gb"),
            ("WAN 2", "SFP LC", "10Gb"),
        ],
        "output_ports": [
            ("LAN 1", "SFP LC", "10Gb"),
            ("LAN 2", "SFP LC", "10Gb"),
            ("LAN 3", "Ethernet", "1Gb"),
            ("LAN 4", "Ethernet", "1Gb"),
        ],
    },

    # ============== КРОССЫ И ПАТЧ-ПАНЕЛИ ==============
    "Магистральный кросс": {
        "device_type": "Main Cross-connect",
        "category": "GLOBAL_INPUT",
        "model": "MC-100G-16",
        "input_ports":  _ports("IN ", 24, "FC", "100Gb"),
        "output_ports": _ports("OUT ", 24, "FC", "100Gb"),
    },
    "Оптический кросс": {
        "device_type": "Fiber Cross-connect",
        "category": "GLOBAL_INPUT",
        "model": "FC-10G-24",
        "input_ports":  _ports("IN ", 24, "SFP LC", "10Gb"),
        "output_ports": _ports("OUT ", 24, "SFP LC", "10Gb"),
    },
    "Патч-панель LC": {
        "device_type": "Patch Panel LC",
        "category": "LOCAL_INPUT",
        "model": "PP-LC-24",
        "input_ports":  _ports("IN ", 12, "SFP LC", "10Gb"),
        "output_ports": _ports("OUT ", 12, "SFP LC", "10Gb"),
    },
    "Патч-панель MPO": {
        "device_type": "Patch Panel MPO",
        "category": "LOCAL_INPUT",
        "model": "PP-MPO-16",
        "input_ports":  _ports("IN ", 8, "SFP MPO", "100Gb"),
        "output_ports": _ports("OUT ", 8, "SFP MPO", "100Gb"),
    },

    # ============== СЕРВЕРЫ ==============
    "Сервер 100Gb": {
        "device_type": "Application Server",
        "category": "SERVERS",
        "model": "SRV-100G",
        "input_ports": [
            ("ib0", "SFP MPO", "100Gb"),
            ("ib1", "SFP MPO", "100Gb"),
            ("mgmt", "Ethernet", "1Gb"),
        ],
        "output_ports": [
            ("out", "SFP MPO", "100Gb"),
        ],
    },
    "Сервер БД 10Gb": {
        "device_type": "Database Server",
        "category": "SERVERS",
        "model": "SRV-DB-10G",
        "input_ports": [
            ("eth0", "SFP LC", "10Gb"),
            ("eth1", "SFP LC", "10Gb"),
            ("mgmt", "Ethernet", "1Gb"),
        ],
        "output_ports": [],
    },
    "Хранилище": {
        "device_type": "Storage",
        "category": "SERVERS",
        "model": "STOR-100G",
        "input_ports":  _ports("ib", 4, "SFP MPO", "100Gb"),
        "output_ports": [],
    },

    # ============== КАСТОМ ==============
    "Пустое устройство": {
        "device_type": "Custom Device",
        "category": "SWITCHES",
        "model": "",
        "input_ports": [],
        "output_ports": [],
    },
}