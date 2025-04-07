import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from .handlers import router as main_router


load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_routers(main_router)
USER_ID = os.getenv("TELEGRAM_USER_ID")


async def send_message(text: str) -> None:
    """Функция для отправки сообщения"""
    await bot.send_message(USER_ID, text)


async def start_bot() -> None:
    """Функцию нужно засунуть в run.py как таску в asyncio"""
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)
