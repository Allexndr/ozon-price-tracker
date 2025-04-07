from loguru import logger
import sys
import asyncio
import os

# Добавляем текущую директорию в путь
sys.path.append('.')

from app.bot.bot import setup_bot
from app.parser.ozon_captcha_solver import OzonCaptchaSolver
from app.config import SCHEDULED_SEARCH_ENABLED
from app.scheduler import start_scheduler
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

async def main():
    """
    Главная функция запуска бота
    """
    # Получаем объекты бота и диспетчера
    bot, dp = setup_bot()
    
    # Инициализируем решатель капчи
    captcha_solver = OzonCaptchaSolver()
    
    # Приветственное сообщение
    logger.info(f"Bot starting as @{(await bot.get_me()).username}")
    
    # Запускаем планировщик, если он включен
    scheduler = None
    if SCHEDULED_SEARCH_ENABLED:
        logger.info("Starting scheduler for periodic product search")
        scheduler = start_scheduler(bot)
    
    # Запускаем бота
    try:
        # Удаляем все предыдущие webhook и сбрасываем незавершенные обновления
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запускаем поллинг
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.exception(f"Error during bot operation: {e}")
    finally:
        # Останавливаем планировщик, если он был запущен
        if scheduler and hasattr(scheduler, "stop"):
            await scheduler.stop()
            
        # Закрываем сессию бота
        await bot.session.close()
        
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main()) 