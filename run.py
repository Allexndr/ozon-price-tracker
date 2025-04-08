#!/usr/bin/env python3
"""
Главный файл для запуска бота и GUI
"""
import asyncio
import threading
from gui.app import start_gui_app
from app.bot.bot import start_bot

def run_gui():
    """Запуск GUI в отдельном потоке"""
    start_gui_app()

if __name__ == "__main__":
    # Создаем поток для GUI и запускаем его
    gui_thread = threading.Thread(target=run_gui, daemon=True)
    gui_thread.start()
    
    # Запускаем бота в основном потоке
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
