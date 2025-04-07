#!/usr/bin/env python3
"""
Run script for the Ozon Parser Bot
"""

import sys
import asyncio
from dotenv import load_dotenv
import os

# Загружаем переменные окружения из файла .env
load_dotenv()

from app.bot.bot import start_bot

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0) 