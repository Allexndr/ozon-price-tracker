import asyncio
import os
import sys
import datetime
import aiofiles
from loguru import logger
import aioschedule as schedule
from concurrent.futures import ThreadPoolExecutor

from app.config import (
    SCHEDULED_SEARCH_ENABLED,
    SCHEDULED_SEARCH_INTERVAL_HOURS,
    SCHEDULED_SEARCH_MAX_THREADS,
    SCHEDULED_SEARCH_PRODUCT_FILE
)
from app.parser.ozon_parser import OzonParser
from app.utils.file_processor import parse_product_file
from app.bot.bot import send_notification_to_admin

class ProductSearchScheduler:
    """
    Планировщик для периодического поиска товаров
    """
    def __init__(self, bot=None):
        self.bot = bot
        self.is_running = False
        self.executor = ThreadPoolExecutor(max_workers=SCHEDULED_SEARCH_MAX_THREADS)
        self.current_tasks = []
        self.results = []
        logger.info(f"Scheduler initialized with {SCHEDULED_SEARCH_MAX_THREADS} threads")
        
    async def start(self):
        """
        Запускает планировщик
        """
        if not SCHEDULED_SEARCH_ENABLED:
            logger.info("Scheduled search is disabled. Enable it in .env file")
            return
            
        self.is_running = True
        
        # Проверяем существование файла с товарами
        product_file = SCHEDULED_SEARCH_PRODUCT_FILE
        if not os.path.exists(product_file):
            logger.error(f"Product file not found: {product_file}")
            await send_notification_to_admin(
                self.bot, 
                f"❌ Ошибка планировщика: файл с товарами не найден: {product_file}"
            )
            self.is_running = False
            return
            
        # Настраиваем расписание
        schedule.every(SCHEDULED_SEARCH_INTERVAL_HOURS).hours.do(self.run_search)
        logger.info(f"Scheduled search will run every {SCHEDULED_SEARCH_INTERVAL_HOURS} hours")
        
        # Запускаем сразу первый поиск
        await self.run_search()
        
        # Запускаем цикл планировщика
        while self.is_running:
            await schedule.run_pending()
            await asyncio.sleep(1)
    
    async def stop(self):
        """
        Останавливает планировщик
        """
        self.is_running = False
        schedule.clear()
        logger.info("Scheduler stopped")
        
    async def run_search(self):
        """
        Запускает процесс поиска товаров
        """
        start_time = datetime.datetime.now()
        logger.info(f"Starting scheduled product search at {start_time}")
        
        if self.bot:
            await send_notification_to_admin(
                self.bot, 
                f"🔄 Запущен плановый поиск товаров: {start_time.strftime('%d.%m.%Y %H:%M:%S')}"
            )
        
        # Загружаем список товаров из файла
        try:
            products = await self._load_products()
            if not products:
                logger.warning("No products found in the file")
                if self.bot:
                    await send_notification_to_admin(
                        self.bot, 
                        f"⚠️ В файле с товарами не найдено товаров для поиска: {SCHEDULED_SEARCH_PRODUCT_FILE}"
                    )
                return
                
            logger.info(f"Loaded {len(products)} products from file")
            if self.bot:
                await send_notification_to_admin(
                    self.bot, 
                    f"📋 Загружено {len(products)} товаров для поиска"
                )
            
            # Запускаем поиск всех товаров параллельно с ограничением по потокам
            # Разбиваем на батчи по SCHEDULED_SEARCH_MAX_THREADS
            tasks = []
            self.results = []
            
            for i in range(0, len(products), SCHEDULED_SEARCH_MAX_THREADS):
                batch = products[i:i+SCHEDULED_SEARCH_MAX_THREADS]
                # Создаем и запускаем задачи для поиска товаров в этом батче
                batch_tasks = [self._search_product(product) for product in batch]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                self.results.extend([r for r in batch_results if not isinstance(r, Exception)])
                
                # Если есть бот, отправляем промежуточные результаты
                if self.bot and self.results:
                    await self._send_batch_results(batch_results)
                    
                # Пауза между батчами для снижения нагрузки
                await asyncio.sleep(2)
            
            # Отправляем итоговый отчет
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info(f"Scheduled search completed in {duration:.2f} seconds")
            logger.info(f"Found {len(self.results)} products out of {len(products)}")
            
            if self.bot:
                await self._send_final_report(len(products), duration)
                
        except Exception as e:
            logger.exception(f"Error during scheduled search: {e}")
            if self.bot:
                await send_notification_to_admin(
                    self.bot, 
                    f"❌ Ошибка при выполнении планового поиска: {str(e)}"
                )
    
    async def _load_products(self):
        """
        Загружает список товаров из файла
        """
        product_file = SCHEDULED_SEARCH_PRODUCT_FILE
        products = []
        
        try:
            # Если файл существует, читаем его
            if os.path.exists(product_file):
                async with aiofiles.open(product_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    
                # Парсим содержимое файла
                products = parse_product_file(content)
                logger.info(f"Loaded {len(products)} products from file {product_file}")
            else:
                logger.error(f"Product file not found: {product_file}")
                
            return products
        
        except Exception as e:
            logger.exception(f"Error loading products from file: {e}")
            return []
    
    async def _search_product(self, product):
        """
        Ищет конкретный товар и возвращает результат
        """
        try:
            name = product.get('name', '')
            article = product.get('article', '')
            price = product.get('price', 0)
            currency = product.get('currency', 'RUB')
            
            logger.info(f"Searching for product: {name}, article: {article}, price: {price} {currency}")
            
            # Создаем парсер и инициализируем браузер
            ozon_parser = OzonParser()
            ozon_parser.initialize_driver()
            
            # Ищем товар
            found_product = ozon_parser.search_by_article(article, name)
            
            # Закрываем браузер
            ozon_parser.close_driver()
            
            if found_product:
                product_price = found_product.get('price', 0)
                product_name = found_product.get('name', '')
                product_url = found_product.get('url', '')
                direct_url = found_product.get('direct_url', product_url)
                seller = found_product.get('seller', 'Неизвестный продавец')
                
                # Информация о соответствии цены
                price_info = ""
                if 'price_diff_percent' in found_product:
                    diff_percent = found_product['price_diff_percent']
                    diff_amount = found_product['price_diff']
                    
                    if diff_amount < 0:
                        price_info = f"✅ Цена ниже целевой! Разница: {abs(diff_amount):.2f} руб. ({abs(diff_percent):.1f}%)"
                    elif diff_amount > 0:
                        if found_product.get('is_close_match', False):
                            price_info = f"⚠️ Цена на {diff_amount:.2f} руб. ({diff_percent:.1f}%) выше запрошенной, но это ближайшее совпадение"
                        else:
                            price_info = f"❌ Цена выше целевой. Разница: {abs(diff_amount):.2f} руб. ({abs(diff_percent):.1f}%)"
                    else:
                        price_info = "✅ Цена точно соответствует запрошенной!"
                
                # Формируем результат
                result = {
                    "original_name": name,
                    "original_article": article,
                    "original_price": price,
                    "found_name": product_name,
                    "found_price": product_price,
                    "found_url": direct_url,
                    "seller": seller,
                    "price_info": price_info,
                    "diff_amount": found_product.get('price_diff', 0),
                    "diff_percent": found_product.get('price_diff_percent', 0),
                    "is_close_match": found_product.get('is_close_match', False)
                }
                
                logger.info(f"Found product: {product_name}, price: {product_price} руб., seller: {seller}")
                return result
            else:
                logger.warning(f"Product not found: {name}, article: {article}")
                return None
                
        except Exception as e:
            logger.exception(f"Error searching for product {name}: {e}")
            return None
    
    async def _send_batch_results(self, batch_results):
        """
        Отправляет результаты поиска батча товаров
        """
        if not self.bot:
            return
            
        found_products = [r for r in batch_results if r and not isinstance(r, Exception)]
        not_found = len(batch_results) - len(found_products)
        
        if not found_products:
            return
            
        # Формируем сообщение с найденными товарами
        links_message = f"🔍 *Результаты поиска товаров* (батч {len(self.results)} / {len(batch_results) + not_found}):\n\n"
        
        for product in found_products:
            name = product.get('found_name', '')
            price = product.get('found_price', 0)
            url = product.get('found_url', '')
            diff_amount = product.get('diff_amount', 0)
            is_close_match = product.get('is_close_match', False)
            
            # Формируем строку для этого товара
            if diff_amount < 0:
                link_text = f"• [{name}]({url}) - {price} руб. (На {abs(diff_amount):.0f} руб. ДЕШЕВЛЕ ✅)"
            elif diff_amount > 0 and is_close_match:
                link_text = f"• [{name}]({url}) - {price} руб. (Ближайшая цена ⚠️)"
            elif diff_amount > 0:
                link_text = f"• [{name}]({url}) - {price} руб. (На {diff_amount:.0f} руб. ДОРОЖЕ ❌)"
            else:
                link_text = f"• [{name}]({url}) - {price} руб. (Точная цена ✅)"
                
            links_message += link_text + "\n"
            
        # Отправляем сообщение
        try:
            await send_notification_to_admin(self.bot, links_message, parse_mode="Markdown", disable_web_page_preview=False)
        except Exception as e:
            logger.exception(f"Error sending batch results: {e}")
    
    async def _send_final_report(self, total_products, duration):
        """
        Отправляет итоговый отчет о результатах поиска
        """
        if not self.bot:
            return
            
        found_count = len(self.results)
        not_found = total_products - found_count
        
        # Информация о статистике поиска
        cheaper_count = len([p for p in self.results if p.get('diff_amount', 0) < 0])
        exact_count = len([p for p in self.results if p.get('diff_amount', 0) == 0])
        more_expensive = len([p for p in self.results if p.get('diff_amount', 0) > 0])
        close_match = len([p for p in self.results if p.get('diff_amount', 0) > 0 and p.get('is_close_match', False)])
        
        # Формируем отчет
        report = (
            f"📊 *Отчет о плановом поиске товаров*\n\n"
            f"⏱ Время выполнения: {duration:.2f} сек.\n"
            f"📋 Всего товаров: {total_products}\n"
            f"✅ Найдено: {found_count}\n"
            f"❌ Не найдено: {not_found}\n\n"
            f"📈 Статистика по ценам:\n"
            f"• 📉 Дешевле запрошенной: {cheaper_count}\n"
            f"• ✅ Точное совпадение: {exact_count}\n"
            f"• 📌 Ближайшее совпадение: {close_match}\n"
            f"• 📈 Дороже запрошенной: {more_expensive - close_match}\n\n"
            f"🕓 Следующий поиск будет выполнен через {SCHEDULED_SEARCH_INTERVAL_HOURS} ч."
        )
        
        # Отправляем отчет
        try:
            await send_notification_to_admin(self.bot, report, parse_mode="Markdown")
        except Exception as e:
            logger.exception(f"Error sending final report: {e}")


def start_scheduler(bot=None):
    """
    Запускает планировщик в отдельном потоке
    """
    if not SCHEDULED_SEARCH_ENABLED:
        logger.info("Scheduled search is disabled. Enable it in .env file")
        return None
        
    scheduler = ProductSearchScheduler(bot)
    asyncio.create_task(scheduler.start())
    logger.info("Scheduler started")
    return scheduler 