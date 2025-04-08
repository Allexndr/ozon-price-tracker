#!/usr/bin/env python3
"""
Run script for the Ozon Parser Bot
"""

import sys
import asyncio
import threading
from dotenv import load_dotenv
from app.bot.bot import start_bot
from gui.app import start_gui_app

# Загружаем переменные окружения из файла .env
load_dotenv()

def run_gui():
    """Запускает GUI в отдельном потоке"""
    start_gui_app()

if __name__ == "__main__":
    try:
        # Запускаем GUI в отдельном потоке
        gui_thread = threading.Thread(target=run_gui)
        gui_thread.daemon = True  # Поток завершится вместе с основной программой
        gui_thread.start()
        
        # Запускаем бота в основном потоке
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0)
