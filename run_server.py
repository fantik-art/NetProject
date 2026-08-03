#!/usr/bin/env python3
"""
Запуск сервера Network Visualizer
"""

import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(__file__))

from server.main_server import run_server

if __name__ == '__main__':
    # Можно указать порт
    port = 5555
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    print("=" * 50)
    print("Network Visualizer Server")
    print("=" * 50)
    print(f"Запуск сервера на порту {port}")
    print("Для остановки нажмите Ctrl+C")
    print("=" * 50)
    
    run_server(port)