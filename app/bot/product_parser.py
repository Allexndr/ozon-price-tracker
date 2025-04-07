import os
import asyncio
import concurrent.futures
import time
import random
from typing import List, Dict, Optional, Tuple, Any
import datetime

from aiogram import Bot
from loguru import logger
from aiogram.types import Message

from app.parser.ozon_parser import OzonParser, ProductInfo
from app.utils.file_processor import read_product_list, FileProcessor
from app.utils.filter_utils import FilterManager

# Кеш цен товаров: {артикул: (цена, валюта, URL продукта, URL поиска, время_обновления)}
price_cache = {}
# Время жизни кеша в секундах (30 минут)
CACHE_TTL = 1800

# Блокировка для предотвращения одновременного запуска нескольких браузеров
browser_lock = asyncio.Lock()
# Максимальное количество одновременных браузеров
MAX_CONCURRENT_BROWSERS = 3
# Счетчик активных браузеров
active_browsers = 0
# Статистика запросов
request_stats = {
    'total': 0,          # Всего запросов
    'cache_hits': 0,     # Попадания в кеш
    'browser_launches': 0, # Запуски браузера
    'api_successes': 0,  # Успешные API запросы
    'failures': 0        # Ошибки
}

class ProductNotFoundException(Exception):
    """Исключение, возникающее если товар не найден"""
    pass

async def get_actual_price(article: str) -> Tuple[float, str]:
    """
    Получает актуальную цену товара по артикулу
    
    Args:
        article: Артикул товара
        
    Returns:
        Tuple[float, str]: Кортеж (цена, валюта)
    """
    global active_browsers
    
    # Увеличиваем счетчик запросов
    request_stats['total'] += 1
    
    # Проверяем кеш
    if article in price_cache:
        price, currency, _, _, timestamp = price_cache[article]
        if time.time() - timestamp < CACHE_TTL:
            request_stats['cache_hits'] += 1
            return price, currency
    
    try:
        # Пытаемся получить цену через API
        parser = OzonParser()
        result = await parser.extract_price_by_article(article)
        if result:
            price = result.get("price", 0)
            currency = result.get("currency", "RUB")
            product_url = result.get("product_url", "")
            search_url = result.get("search_url", "")
            
            # Обновляем кеш
            price_cache[article] = (price, currency, product_url, search_url, time.time())
            request_stats['api_successes'] += 1
            return price, currency
            
    except Exception as e:
        logger.error(f"Error getting price for article {article}: {e}")
        request_stats['failures'] += 1
        raise ProductNotFoundException(f"Не удалось получить цену для артикула {article}")
    finally:
        await parser.close()

async def process_single_product(article: str, target_price: float, filter_manager: FilterManager = None) -> Dict[str, Any]:
    """
    Обрабатывает один товар
    
    Args:
        article: Артикул товара
        target_price: Целевая цена
        filter_manager: Менеджер фильтров
        
    Returns:
        Dict с информацией о товаре
    """
    try:
        # Получаем актуальную цену
        actual_price, currency = await get_actual_price(article)
        
        # Проверяем цену
        if actual_price <= target_price:
            return {
                'article': article,
                'price': actual_price,
                'currency': currency,
                'target_price': target_price,
                'status': 'found',
                'message': f'✅ Найдена цена ниже целевой! {actual_price} {currency}'
            }
        else:
            return {
                'article': article,
                'price': actual_price,
                'currency': currency,
                'target_price': target_price,
                'status': 'high_price',
                'message': f'❌ Текущая цена {actual_price} {currency} выше целевой {target_price} {currency}'
            }
            
    except ProductNotFoundException:
        return {
            'article': article,
            'status': 'not_found',
            'message': '❌ Товар не найден'
        }
    except Exception as e:
        logger.error(f"Error processing product {article}: {e}")
        return {
            'article': article,
            'status': 'error',
            'message': f'❌ Ошибка: {str(e)}'
        }

async def process_product_file(chat_id: int, file_path: str, filter_manager: FilterManager = None) -> None:
    """
    Обрабатывает файл со списком товаров
    
    Args:
        chat_id: ID чата для отправки результатов
        file_path: Путь к файлу со списком товаров
        filter_manager: Менеджер фильтров
    """
    try:
        # Читаем список товаров
        products = await read_product_list(file_path, filter_manager)
        if not products:
            logger.warning(f"No products found in file {file_path}")
            return
            
        logger.info(f"Processing {len(products)} products from file {file_path}")
        
        # Обрабатываем каждый товар
        for name, price, currency, filter_reason in products:
            if filter_reason:
                logger.info(f"Skipping {name}: {filter_reason}")
                continue
                
            # Извлекаем артикул из названия
            words = name.split()
            article = next((word for word in words if any(c.isdigit() for c in word)), None)
            
            if not article:
                logger.warning(f"No article found in product name: {name}")
                continue
                
            try:
                # Обрабатываем товар
                result = await process_single_product(article, float(price), filter_manager)
                
                # Формируем сообщение
                message = (
                    f"📦 {name}\n"
                    f"🔢 Артикул: {article}\n"
                    f"{result['message']}"
                )
                
                # Отправляем результат
                bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
                try:
                    await bot.send_message(chat_id=chat_id, text=message)
                finally:
                    await bot.session.close()
                    
            except Exception as e:
                logger.error(f"Error processing product {name}: {e}")
                
    except Exception as e:
        logger.exception(f"Error processing file {file_path}: {e}")
    finally:
        # Удаляем временный файл
        try:
            os.unlink(file_path)
        except Exception as e:
            logger.error(f"Error deleting temporary file {file_path}: {e}")

def request_stats() -> Dict[str, int]:
    """Возвращает статистику запросов"""
    return request_stats.copy() 