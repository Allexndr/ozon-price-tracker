from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile
import os
import tempfile
from loguru import logger
import asyncio
from aiogram.types import BotCommand

from app.bot.handlers import (
    register_handlers_common,
    text_handler,
    filter_manager
)
from app.bot.product_parser import process_product_file
from app.utils.file_processor import save_document

# ID администратора бота (можно получить из переменной окружения)
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

def setup_bot():
    """
    Настройка бота и диспетчера
    """
    # Создаем экземпляр бота
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    
    # Создаем диспетчер
    dp = Dispatcher()
    
    # Регистрируем обработчики сообщений из модуля handlers
    from app.bot.handlers import (
        register_handlers_common,
        start_handler, 
        help_handler, 
        filters_handler, 
        daily_word_handler, 
        stopword_handler, 
        blacklist_handler,
        version_handler,
        article_command_handler,
        reset_handler,
        new_product_list_handler,
        improvements_handler
    )
    
    # Регистрируем все обработчики через общую функцию регистрации
    register_handlers_common(dp)
    
    return bot, dp

async def set_commands(bot: Bot):
    """
    Установка команд бота
    """
    commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Показать справку"),
        BotCommand(command="new", description="Создать новый список товаров"),
        BotCommand(command="done", description="Завершить ввод товаров и начать поиск"),
        BotCommand(command="cancel", description="Отменить текущую операцию"),
        BotCommand(command="filters", description="Управление фильтрами"),
        BotCommand(command="stopword", description="Управление стоп-словами"),
        BotCommand(command="blacklist", description="Управление черным списком продавцов"),
        BotCommand(command="dailyword", description="Ежедневное стоп-слово"),
        BotCommand(command="article", description="Поиск товара по артикулу"),
        BotCommand(command="version", description="Показать версию бота"),
        BotCommand(command="improvements", description="Список улучшений"),
        BotCommand(command="reset", description="Сбросить все настройки"),
    ]
    await bot.set_my_commands(commands)

async def start_bot():
    """
    Запуск бота
    """
    # Инициализируем бота и диспетчер
    bot, dp = setup_bot()
    
    # Устанавливаем команды бота
    await set_commands(bot)
    
    try:
        # Запускаем поллинг
        await dp.start_polling(bot)
    finally:
        # Закрываем сессию бота
        await bot.session.close() 