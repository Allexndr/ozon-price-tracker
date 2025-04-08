from aiogram import types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os
import tempfile
from loguru import logger
import re
from typing import List, Dict, Any, Optional
import aiogram.utils.formatting as fmt

from app.utils.filter_utils import FilterManager
from app.bot.product_parser import process_product_file, get_actual_price, request_stats
from app.utils.file_processor import parse_multiple_formats
from app.parser.ozon_parser import OzonParser, ProductInfo
from app.bot.bot import send_message

class ProductList(StatesGroup):
    choosing_method = State()
    collecting_products = State()
    viewing_list = State()

# Создаем экземпляр менеджера фильтров
filter_manager = FilterManager()

async def start_handler(message: types.Message):
    """
    Обработчик команды /start
    Запускает парсер после получения команды
    """
    # Создаем парсер и запускаем его
    parser = OzonParser()
    
    # Отправляем сообщение о начале работы
    await message.answer(
        "🚀 Парсер начал работу!\n\n"
        "Добавляйте товары через GUI приложение:\n"
        "- Список товаров в list.txt\n"
        "- Игнорируемые слова в ignore_list.txt\n\n"
        "Когда товар будет найден, вы получите уведомление."
    )
    
    # Запускаем парсер
    await parser.start_work()

// ... rest of the handlers code ... 
