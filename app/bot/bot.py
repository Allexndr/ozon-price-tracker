import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from aiogram.types import BotCommand
from loguru import logger

from .handlers import router as main_router
from app.bot.handlers import register_handlers_common


load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# ID администратора бота (можно получить из переменной окружения)
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

async def send_message(chat_id: int, text: str):
    """
    Отправляет сообщение пользователю через бота
    """
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.error(f"Error sending message: {e}")
    finally:
        await bot.session.close()

def setup_bot():
    """
    Настройка бота и диспетчера
    """
    # Создаем экземпляр бота
    bot = Bot(token=BOT_TOKEN)
    
    # Создаем диспетчер
    dp = Dispatcher()
    
    # Регистрируем обработчики
    register_handlers_common(dp)
    
    return bot, dp

async def start_bot():
    """
    Запуск бота
    """
    # Получаем экземпляры бота и диспетчера
    bot, dp = setup_bot()
    
    # Устанавливаем команды бота
    commands = [
        BotCommand(command="start", description="Запустить парсер"),
        BotCommand(command="help", description="Показать справку"),
        BotCommand(command="new", description="Создать новый список товаров"),
        BotCommand(command="done", description="Завершить ввод товаров"),
        BotCommand(command="cancel", description="Отменить текущую операцию"),
        BotCommand(command="article", description="Поиск по артикулу"),
        BotCommand(command="filters", description="Управление фильтрами"),
        BotCommand(command="stats", description="Статистика запросов")
    ]
    await bot.set_my_commands(commands)
    
    try:
        # Запускаем поллинг
        await dp.start_polling(bot)
    finally:
        # Закрываем сессию бота
        await bot.session.close()
