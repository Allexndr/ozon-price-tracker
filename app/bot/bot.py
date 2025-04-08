import os

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from aiogram.filters import Command
from loguru import logger

from .handlers import router as main_router
from app.bot.handlers import register_handlers_common

# Получаем токен бота из переменной окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не установлен в переменных окружения")

# ID администратора для отправки уведомлений
ADMIN_ID = os.getenv("ADMIN_ID")
if not ADMIN_ID:
    raise ValueError("ADMIN_ID не установлен в переменных окружения")

# Создаем объекты бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def send_message(text: str) -> None:
    """
    Функция для отправки сообщения администратору
    
    Args:
        text: Текст сообщения
    """
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text)
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")

async def setup_bot():
    """
    Настройка бота и регистрация обработчиков
    """
    # Регистрируем обработчики
    register_handlers_common(dp)
    
    # Устанавливаем команды бота
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Запустить парсер"),
        types.BotCommand(command="help", description="Помощь"),
        types.BotCommand(command="new", description="Новый список товаров"),
        types.BotCommand(command="done", description="Завершить ввод"),
        types.BotCommand(command="cancel", description="Отменить текущую операцию"),
        types.BotCommand(command="article", description="Поиск по артикулу"),
        types.BotCommand(command="filters", description="Управление фильтрами"),
        types.BotCommand(command="stats", description="Статистика запросов")
    ])
    
    return bot, dp

async def start_bot():
    """
    Запуск бота
    """
    bot, dp = await setup_bot()
    await dp.start_polling(bot)
