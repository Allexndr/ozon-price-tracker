import os
import re
import time
import json
import pickle
import base64
import random
import requests
import urllib.parse
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime
from loguru import logger
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, WebDriverException, NoSuchWindowException
)

from app.parser.ozon_captcha_solver import OzonCaptchaSolver
from app.utils.user_agent import get_random_user_agent
from app.utils.filter_utils import FilterManager
from app.utils.proxy_handler import ProxyHandler

# Добавляем класс ProductInfo для обратной совместимости
class ProductInfo:
    """
    Класс для хранения информации о продукте
    Оставлен для обратной совместимости
    """
    def __init__(self, name: str, price: int, article: str, image_url: str = "", url: str = "", seller: str = ""):
        self.name = name
        self.price = price
        self.article = article
        self.image_url = image_url
        self.url = url
        self.seller = seller

# Пытаемся импортировать undetected_chromedriver
try:
    import undetected_chromedriver as uc
    UNDETECTED_CHROMEDRIVER_AVAILABLE = True
    logger.info("Модуль undetected_chromedriver успешно импортирован")
except ImportError:
    UNDETECTED_CHROMEDRIVER_AVAILABLE = False
    logger.warning("undetected_chromedriver не установлен. Рекомендуется установить для обхода защиты от ботов.")
    # Пробуем установить undetected_chromedriver автоматически
    try:
        import subprocess
        subprocess.check_call(["pip", "install", "undetected-chromedriver"])
        import undetected_chromedriver as uc
        UNDETECTED_CHROMEDRIVER_AVAILABLE = True
        logger.info("Модуль undetected_chromedriver установлен, пробуем импортировать снова")
    except Exception as e:
        logger.error(f"Не удалось установить undetected_chromedriver: {e}")
        UNDETECTED_CHROMEDRIVER_AVAILABLE = False

class OzonParser:
    """
    Класс для парсинга данных с Ozon
    Использует Selenium с undetected_chromedriver для обхода защиты от ботов
    """
    
    BASE_URL = "https://www.ozon.ru"
    SEARCH_URL = f"{BASE_URL}/search"
    PRODUCT_URL = f"{BASE_URL}/product"
    
    def __init__(self, headless: bool = True, proxy: Optional[str] = None):
        """
        Инициализация парсера
        
        Args:
            headless: Запускать браузер в фоновом режиме (без интерфейса)
            proxy: Строка с прокси-сервером в формате "ip:port" или "user:pass@ip:port"
        """
        self.headless = headless
        self.proxy = proxy
        self.driver = None
        self.wait = None
        self.filter_manager = FilterManager()
        self.proxy_handler = ProxyHandler()
        
        # Инициализируем решатель капчи
        self.captcha_solver = OzonCaptchaSolver()
        
        # Cookies и сохраненные данные
        self.cookies_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cookies.pickle")
        
        # Создаем директорию, если ее нет
        os.makedirs(os.path.dirname(self.cookies_path), exist_ok=True)
        
        # Счетчики для статистики
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.captcha_encountered = 0
        self.captcha_solved = 0
        
        # Флаг активного драйвера
        self.is_driver_active = False
        
        logger.info(f"OzonParser инициализирован (headless: {headless}, proxy: {proxy})")
    
    def __del__(self):
        """
        Закрытие драйвера при уничтожении объекта
        """
        self.close_driver()
    
    def setup_driver(self):
        """
        Настройка и запуск Chrome WebDriver с использованием undetected_chromedriver
        """
        try:
            if UNDETECTED_CHROMEDRIVER_AVAILABLE:
                options = uc.ChromeOptions()
                
                if self.headless:
                    options.add_argument("--headless=new")
                
                # Добавляем случайный User-Agent
                user_agent = get_random_user_agent()
                options.add_argument(f"--user-agent={user_agent}")
                
                # Добавляем общие опции для предотвращения обнаружения
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-extensions")
                options.add_argument("--dns-prefetch-disable")
                
                # Если указан прокси, добавляем его
                if self.proxy:
                    options.add_argument(f"--proxy-server={self.proxy}")
                
                # Запускаем драйвер
                self.driver = uc.Chrome(options=options)
                self.driver.set_page_load_timeout(60)
                
                # Настраиваем wait для ожидания элементов
                self.wait = WebDriverWait(self.driver, 10)
                
                # Устанавливаем размер окна
                self.driver.set_window_size(1920, 1080)
                
                # Флаг активного драйвера
                self.is_driver_active = True
                
                logger.info(f"Chrome WebDriver успешно запущен с использованием undetected_chromedriver")
                return True
            else:
                logger.error("undetected_chromedriver не доступен, парсинг невозможен")
                return False
        
        except Exception as e:
            logger.error(f"Ошибка при запуске Chrome WebDriver: {e}")
            self.is_driver_active = False
            return False
    
    def close_driver(self):
        """
        Закрытие драйвера и освобождение ресурсов
        """
        if self.driver:
            try:
                self.save_cookies()
                self.driver.quit()
                logger.info("Chrome WebDriver успешно закрыт")
            except Exception as e:
                logger.warning(f"Ошибка при закрытии Chrome WebDriver: {e}")
            finally:
                self.driver = None
                self.wait = None
                self.is_driver_active = False
    
    def load_cookies(self):
        """
        Загрузка сохраненных cookies
        """
        if os.path.exists(self.cookies_path):
            try:
                with open(self.cookies_path, 'rb') as f:
                    cookies = pickle.load(f)
                    
                # Проверяем, что драйвер запущен и открыт домен Ozon
                if not self.is_driver_active:
                    if not self.setup_driver():
                        return False
                
                current_url = self.driver.current_url
                if "ozon.ru" not in current_url:
                    self.driver.get(self.BASE_URL)
                    time.sleep(2)
                
                # Устанавливаем cookies
                for cookie in cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        logger.warning(f"Не удалось добавить cookie: {e}")
                
                # Обновляем страницу для применения cookies
                self.driver.refresh()
                time.sleep(2)
                
                logger.info("Cookies успешно загружены")
                return True
            
            except Exception as e:
                logger.warning(f"Ошибка при загрузке cookies: {e}")
        
        return False
    
    def save_cookies(self):
        """
        Сохранение текущих cookies
        """
        if self.is_driver_active:
            try:
                cookies = self.driver.get_cookies()
                with open(self.cookies_path, 'wb') as f:
                    pickle.dump(cookies, f)
                logger.info("Cookies успешно сохранены")
                return True
            except Exception as e:
                logger.warning(f"Ошибка при сохранении cookies: {e}")
        
        return False
    
    def search_products(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Поиск товаров по запросу
        
        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов
            
        Returns:
            Список товаров
        """
        self.total_requests += 1
        logger.info(f"Поиск товаров по запросу: {query}, максимум результатов: {max_results}")
        
        if not self.is_driver_active:
            if not self.setup_driver():
                self.failed_requests += 1
                return []
        
        try:
            # Формируем URL для поиска
            encoded_query = urllib.parse.quote(query)
            if self.captcha_api_key:
                try:
                    from twocaptcha import TwoCaptcha
                    self.captcha_solver = TwoCaptcha(self.captcha_api_key)
                    logger.info("2Captcha solver initialized")
                except Exception as e:
                    logger.error(f"2Captcha initialization error: {e}")
                    self.captcha_solver = None
        except Exception as e:
            logger.error(f"Error initializing 2Captcha: {e}")
            self.captcha_solver = None

        # Инициализация CapMonster Cloud
        if CAPMONSTER_AVAILABLE and self.capmonster_key:
            try:
                from capmonstercloudclient import CapMonsterClient, ClientOptions
                options = ClientOptions(api_key=self.capmonster_key, client_key=self.capmonster_key)
                self.capmonster_client = CapMonsterClient(options=options)
                logger.info("CapMonster Cloud client initialized")
            except Exception as e:
                logger.error(f"CapMonster Cloud initialization error: {e}")
                self.capmonster_client = None
        else:
            self.capmonster_client = None

        # Инициализация AntiCaptcha
        if ANTICAPTCHA_AVAILABLE and self.anticaptcha_key:
            try:
                from python_anticaptcha import AnticaptchaClient
                self.anticaptcha_client = AnticaptchaClient(self.anticaptcha_key)
                logger.info("AntiCaptcha client initialized")
            except Exception as e:
                logger.error(f"AntiCaptcha initialization error: {e}")
                self.anticaptcha_client = None
        else:
            self.anticaptcha_client = None
    
    def setup_driver(self):
        """
        Setup and configure Chrome WebDriver
        """
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        # Add common options to avoid detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Add user agent
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
        
        # Disable images for faster loading
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        
        # Add proxy if needed
        if self.proxy_handler:
            # Implement proxy logic here
            pass
        
        # Exclude the "enable-automation" flag
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Create driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute CDP commands to avoid detection
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Улучшение обхода защиты
                window.navigator.chrome = {
                    runtime: {},
                };
                
                // Подделка языковых настроек
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                });
                
                // Подделка плагинов
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """
        })
        
        self.driver = driver
        logger.debug("WebDriver настроен успешно")
        
    def close_driver(self):
        """
        Close WebDriver if it exists
        """
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.debug("WebDriver закрыт")
    
    def normalize_article(self, article: str) -> str:
        """
        Нормализация артикула (удаление лишних символов)
        
        Args:
            article: Исходный артикул
            
        Returns:
            Нормализованный артикул
        """
        # Удаляем все не-буквенно-цифровые символы
        return re.sub(r'[^a-zA-Z0-9]', '', article)
    
    def extract_article_from_product_name(self, product_name: str) -> Optional[str]:
        """
        Извлечение артикула из названия товара
        
        Args:
            product_name: Название товара
            
        Returns:
            Артикул товара или None, если не удалось извлечь
        """
        # Ищем артикул по различным паттернам
        # Например: "Товар XYZ-123" или "Товар XYZ123" или "Товар (XYZ-123)"
        patterns = [
            r'\b([A-Z0-9]+-[A-Z0-9]+)\b',  # Артикул с тире
            r'\b([A-Z0-9]{3,})\b',         # Артикул без тире (минимум 3 символа)
            r'\(([A-Z0-9]+-?[A-Z0-9]+)\)'  # Артикул в скобках
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, product_name, re.IGNORECASE)
            if matches:
                return matches[0]
                
        return None
    
    def get_article_variations(self, article: str) -> set[str]:
        """
        Генерация вариаций артикула для поиска
        
        Args:
            article: Исходный артикул
            
        Returns:
            Набор вариаций артикула
        """
        article = self.normalize_article(article)
        
        if not article:
            return set()
            
        # Набор потенциальных вариаций артикула
        variations = set()
        variations.add(article)
        
        # Добавляем варианты артикула с ведущими нулями и без них
        if article.isdigit():
            # Вариант без ведущих нулей
            variations.add(article.lstrip('0'))
            
            # Вариант с дополнительными ведущими нулями (до 10 символов)
            if len(article) < 10:
                variations.add(article.zfill(10))
                
        # Если артикул содержит буквы, добавляем вариации с разным регистром
        if not article.isdigit():
            variations.add(article.upper())
            variations.add(article.lower())
            
        return variations
    
    async def search_product(self, product_name: str, max_price: float) -> List[Dict]:
        """
        Search for a product on Ozon with price filter
        
        Args:
            product_name: Product name with article to search
            max_price: Maximum price filter (будет умножена на 2 для более широкого диапазона)
            
        Returns:
            List of found products with details
        """
        # Initialize driver if needed
        if not self.driver:
            self.setup_driver()
        
        results = []
        retries = 0
        
        # Для поиска используем более широкий диапазон цен
        search_max_price = max_price * 2
        
        # Извлекаем возможный артикул из названия
        article = None
        for word in product_name.split():
            if re.match(r'^[A-Z0-9]+-?[A-Z0-9]+$', word, re.IGNORECASE):
                article = word
                break
        
        # Получаем варианты поискового запроса с разными вариациями артикула
        search_queries = [product_name]  # Базовый запрос
        
        if article:
            # Добавляем вариации запроса с разными форматами артикула
            article_variations = self.get_article_variations(article)
            logger.debug(f"Найдены вариации артикула {article}: {article_variations}")
            
            for variation in article_variations:
                if variation != article:
                    # Создаем новый запрос, заменяя оригинальный артикул на вариацию
                    new_query = product_name.replace(article, variation)
                    if new_query != product_name:
                        search_queries.append(new_query)
        
        logger.info(f"Будет выполнен поиск по запросам: {search_queries}")
        
        while retries < self.max_retries:
            try:
                # Перебираем все варианты запросов, пока не найдем результаты
                for search_query in search_queries:
                    logger.info(f"Поиск по запросу: {search_query}")
                    
                    # Navigate to Ozon search page
                    self.driver.get(self.search_url)
                    time.sleep(random.uniform(2, 4))  # Random delay
                    
                    # Проверяем наличие капчи или других элементов защиты
                    if self.is_captcha_present():
                        logger.warning("Обнаружена капча, пытаемся обойти...")
                        if not self.handle_captcha():
                            raise Exception("Не удалось обойти капчу")
                    
                    # Wait for search input to be available
                    search_selectors = [
                        "input[placeholder='Искать на Ozon']",
                        "input.search-field",
                        "#stickySearchInput",
                        ".tsBodyL input"
                    ]
                    
                    search_input = None
                    for selector in search_selectors:
                        try:
                            search_input = WebDriverWait(self.driver, 10).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            break
                        except:
                            continue
                    
                    if not search_input:
                        logger.warning("Не найдено поле поиска")
                        continue
                    
                    # Clear the search field
                    search_input.clear()
                    
                    # Type the search query with random delays
                    for char in search_query:
                        search_input.send_keys(char)
                        time.sleep(random.uniform(0.05, 0.1))  # Add slight delay between keystrokes
                    
                    # Submit the search
                    search_input.send_keys(Keys.ENTER)
                    
                    # Wait for results to load
                    time.sleep(random.uniform(3, 5))
                    
                    # Apply price filter
                    await self.apply_price_filter(search_max_price)
                    
                    # Extract search results
                    products = await self.extract_search_results()
                    
                    if products:
                        # Add products to results
                        results.extend(products)
                        logger.info(f"Найдено {len(products)} товаров для запроса '{search_query}'")
                        break  # Выходим из цикла по запросам, так как нашли результаты
                
                if results:
                    return results
                
                # If no results, increment retry counter
                retries += 1
                logger.warning(f"Попытка {retries}/{self.max_retries}: Не найдены товары. Повторный поиск...")
                time.sleep(random.uniform(1, 3))  # Wait before retry
                
            except Exception as e:
                logger.warning(f"Ошибка при поиске: {e}")
                retries += 1
                if retries >= self.max_retries:
                    logger.error(f"Превышено максимальное количество попыток ({self.max_retries})")
                    break
                time.sleep(random.uniform(1, 3))  # Wait before retry
        
        return results
    
    def is_captcha_present(self) -> bool:
        """
        Проверяет, присутствует ли капча на странице
        
        Returns:
            True, если капча обнаружена, иначе False
        """
        try:
            # Проверяем наличие различных элементов капчи
            captcha_indicators = [
                # reCAPTCHA
                "div.g-recaptcha",
                "iframe[src*='recaptcha']",
                "[data-sitekey]",
                
                # FunCaptcha / ArkoseLabs
                "iframe[src*='funcaptcha']",
                "iframe[src*='arkoselabs']",
                
                # Обычная капча
                "img[id*='captcha']",
                "img[class*='captcha']",
                "img[src*='captcha']",
                ".captcha img",
                "img.captcha",
                
                # Поля ввода для капчи
                "input[name*='captcha']",
                "input[placeholder*='captcha']",
                "input[id*='captcha']",
                ".captcha input",
                
                # Специфичные для Ozon
                "img.gn3",
                "input.fo3",
                "[data-widget='AdvancedCaptcha']"
            ]
            
            # Ищем элементы капчи в DOM
            for selector in captcha_indicators:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and any(el.is_displayed() for el in elements):
                    logger.info(f"Обнаружена капча (селектор: {selector})")
                    # Сохраняем скриншот страницы для анализа
                    try:
                        timestamp = int(time.time())
                        screenshot_path = f"captcha_screenshot_{timestamp}.png"
                        self.driver.save_screenshot(screenshot_path)
                        logger.info(f"Скриншот страницы с капчей сохранен: {screenshot_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при сохранении скриншота: {e}")
                    return True
            
            # Проверяем наличие ключевых слов капчи в исходном коде страницы
            page_source = self.driver.page_source.lower()
            captcha_keywords = [
                'captcha', 'recaptcha', 'grecaptcha', 'funcaptcha', 'arkoselabs',
                'подтвердите, что вы не робот', 'докажите, что вы не робот',
                'проверка безопасности', 'security check', 'bot check', 
                'защита от ботов', 'robot check', 'verification'
            ]
            
            for keyword in captcha_keywords:
                if keyword in page_source:
                    # Дополнительная проверка: убедимся, что это не часть другого слова
                    # Например, "captcha" не должно быть частью "captchaProcessed"
                    if re.search(r'\b' + re.escape(keyword) + r'\b', page_source):
                        logger.info(f"Обнаружена капча (ключевое слово: {keyword})")
                        # Не сохраняем скриншоты капчи, чтобы не засорять директорию
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при проверке наличия капчи: {e}")
            return False
    
    def detect_captcha_type(self) -> str:
        """
        Определяет тип капчи на странице
        
        Returns:
            Строка с типом капчи: 'recaptcha', 'funcaptcha', 'normal' или 'unknown'
        """
        try:
            logger.info("Определяем тип капчи на странице...")
            page_source = self.driver.page_source.lower()
            
            # Проверяем наличие reCAPTCHA
            recaptcha_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.g-recaptcha, [data-sitekey], iframe[src*='recaptcha']")
            if recaptcha_elements and any(el.is_displayed() for el in recaptcha_elements):
                logger.info("Обнаружена reCAPTCHA")
                return 'recaptcha'
                
            # Ищем reCAPTCHA в исходном коде страницы
            if 'google.com/recaptcha' in page_source or 'gstatic.com/recaptcha' in page_source:
                logger.info("Обнаружена reCAPTCHA в коде страницы")
                return 'recaptcha'
            
            # Проверяем наличие FunCaptcha / ArkoseLabs
            funcaptcha_elements = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='funcaptcha'], iframe[src*='arkoselabs']")
            if funcaptcha_elements and any(el.is_displayed() for el in funcaptcha_elements):
                logger.info("Обнаружена FunCaptcha")
                return 'funcaptcha'
                
            # Ищем FunCaptcha в исходном коде страницы
            if 'funcaptcha' in page_source or 'arkoselabs' in page_source:
                logger.info("Обнаружена FunCaptcha в коде страницы")
                return 'funcaptcha'
            
            # Проверяем наличие обычной капчи (изображение + поле ввода)
            captcha_images = self.driver.find_elements(By.CSS_SELECTOR, 
                "img[id*='captcha'], img[class*='captcha'], img[src*='captcha'], .captcha img, img.captcha, img.gn3, img[alt*='captcha'], img[data-widget='AdvancedCaptcha']")
            
            if captcha_images and any(img.is_displayed() for img in captcha_images):
                logger.info("Обнаружена обычная капча (изображение)")
                return 'normal'
            
            # Проверяем поля ввода, содержащие "captcha" в атрибутах
            captcha_inputs = self.driver.find_elements(By.CSS_SELECTOR,
                "input[name*='captcha'], input[placeholder*='captcha'], input[id*='captcha'], .captcha input, input.fo3, input[data-widget='AdvancedCaptcha']")
            
            if captcha_inputs and any(inp.is_displayed() for inp in captcha_inputs):
                logger.info("Обнаружено поле ввода для капчи")
                return 'normal'
            
            # Проверяем наличие ключевых слов в коде страницы
            if any(keyword in page_source for keyword in ['captcha', 'капча', 'подтвердите, что вы не робот']):
                logger.info("Обнаружена капча по ключевым словам")
                return 'normal'  # Если не можем точно определить тип, возвращаем обычную
                
            logger.warning("Не удалось определить тип капчи")
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Ошибка при определении типа капчи: {e}")
            return 'unknown'
    
    def get_captcha_image(self) -> Optional[str]:
        """
        Получает изображение обычной капчи в base64

        Returns:
            Строка base64 с изображением или None в случае ошибки
        """
        try:
            logger.info("Получаем изображение капчи...")
            # Ищем изображение капчи
            image_selectors = [
                "img[id*='captcha']", 
                "img[class*='captcha']", 
                "img[src*='captcha']",
                ".captcha img",
                "img.captcha",
                "img[alt*='captcha']",
                "img[data-testid='captcha']",
                # Специфично для Ozon
                "img.gn3",
                "img[data-widget='AdvancedCaptcha']",
                # Дополнительные селекторы для Ozon
                "div[data-widget='captcha'] img",
                "div.captcha img",
                "div.g23 img",
                # Общие селекторы для изображений
                "img[width][height]" # Попробуем найти любое изображение подходящего размера
            ]
            
            for selector in image_selectors:
                try:
                    logger.debug(f"Пробуем селектор: {selector}")
                    images = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if images:
                        for img in images:
                            if img.is_displayed():
                                try:
                                    # Проверяем размеры изображения - капчи обычно имеют разумные размеры
                                    width = img.get_attribute("width")
                                    height = img.get_attribute("height")
                                    
                                    # Если это общий селектор для изображений, проверяем размеры
                                    if selector == "img[width][height]":
                                        try:
                                            w = int(width)
                                            h = int(height)
                                            # Капчи обычно не очень большие и не очень маленькие
                                            if not (50 <= w <= 500 and 30 <= h <= 300):
                                                continue
                                        except (ValueError, TypeError):
                                            continue
                                    
                                    # Получаем изображение в формате base64
                                    logger.info(f"Найдено подходящее изображение капчи: {selector}")
                                    img_src = img.get_attribute("src")
                                    
                                    # Если src уже в формате base64
                                    if img_src and "base64" in img_src:
                                        # Извлекаем только данные после 'base64,'
                                        base64_data = img_src.split("base64,")[1]
                                        logger.info("Получено изображение капчи в формате base64")
                                        return base64_data
                                    
                                    # Если src - URL, скачиваем изображение
                                    if img_src and (img_src.startswith("http") or img_src.startswith("/")):
                                        # Если относительный URL, добавляем базовый URL
                                        if img_src.startswith("/"):
                                            img_src = f"https://www.ozon.ru{img_src}"
                                            
                                        logger.info(f"Скачиваем изображение капчи по URL: {img_src}")
                                        # Скачиваем изображение
                                        response = requests.get(img_src)
                                        if response.status_code == 200:
                                            img_data = base64.b64encode(response.content).decode("utf-8")
                                            logger.info("Изображение капчи успешно скачано")
                                            return img_data
                                    
                                    # Если не получили src, делаем скриншот элемента
                                    logger.info("Делаем скриншот элемента с капчей")
                                    img_base64 = img.screenshot_as_base64
                                    return img_base64
                                except Exception as e:
                                    logger.warning(f"Ошибка при обработке изображения: {e}")
                                    continue
                except Exception as e:
                    logger.warning(f"Ошибка при поиске изображений с селектором {selector}: {e}")
                    continue
            
            # Если не нашли изображение по селекторам, делаем скриншот всей страницы
            # и покажем его пользователю для ручного решения
            logger.warning("Не удалось найти изображение капчи, делаем скриншот страницы")
            try:
                return self.driver.get_screenshot_as_base64()
            except:
                pass
                
            logger.error("Не удалось получить изображение капчи никакими способами")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении изображения капчи: {e}")
            return None

    def get_recaptcha_sitekey(self) -> Optional[str]:
        """
        Получает site key для reCAPTCHA

        Returns:
            Site key или None, если не удалось найти
        """
        try:
            # Пробуем найти div с атрибутом data-sitekey
            recaptcha_divs = self.driver.find_elements(By.CSS_SELECTOR, "div.g-recaptcha, div[data-sitekey]")
            
            for div in recaptcha_divs:
                site_key = div.get_attribute("data-sitekey")
                if site_key:
                    return site_key
            
            # Если не нашли, ищем в HTML
            page_source = self.driver.page_source
            site_key_pattern = r'data-sitekey=["\']([^"\']+)["\']'
            match = re.search(site_key_pattern, page_source)
            
            if match:
                return match.group(1)
            
            # Еще один вариант - искать в скриптах
            scripts = self.driver.find_elements(By.TAG_NAME, "script")
            for script in scripts:
                script_text = script.get_attribute("innerHTML")
                if script_text and "recaptcha" in script_text.lower():
                    match = re.search(r'sitekey["\':\s]+["\'](.*?)["\']', script_text)
                    if match:
                        return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при получении site key для reCAPTCHA: {e}")
            return None
    
    def get_funcaptcha_sitekey(self) -> str:
        """
        Получение sitekey для FunCaptcha
        
        Returns:
            Строка с sitekey или пустая строка в случае ошибки
        """
        try:
            # Ищем скрипты, содержащие данные FunCaptcha
            script = """
                var sitekey = "";
                var scripts = document.getElementsByTagName("script");
                for (var i = 0; i < scripts.length; i++) {
                    var content = scripts[i].textContent;
                    if (content && content.includes("arkose") && content.includes("public_key")) {
                        var match = content.match(/public_key:[ \\t]*["']([^"']+)["']/);
                        if (match && match[1]) {
                            sitekey = match[1];
                            break;
                        }
                    }
                }
                return sitekey;
            """
            sitekey = self.driver.execute_script(script)
            
            # Если не нашли через скрипты, проверяем iframe
            if not sitekey:
                elements = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='arkoselabs'], iframe[src*='funcaptcha']")
                for element in elements:
                    src = element.get_attribute("src")
                    if src:
                        # Ищем public_key в URL
                        import re
                        match = re.search(r'public_key=([^&]+)', src)
                        if match:
                            sitekey = match.group(1)
                            break
            
            return sitekey if sitekey else ""
            
        except Exception as e:
            logger.exception(f"Ошибка при получении sitekey для FunCaptcha: {e}")
            return ""
    
    def solve_captcha_with_2captcha(self, captcha_type: str) -> Optional[str]:
        """
        Решает капчу с помощью сервиса 2captcha
        
        Args:
            captcha_type: Тип капчи для решения ('recaptcha', 'funcaptcha', 'normal')
            
        Returns:
            Строка с решением капчи или None в случае ошибки
        """
        if not self.captcha_api_key:
            logger.error("API ключ для решения CAPTCHA не найден. Установите переменную окружения CAPTCHA_API_KEY")
            return None
            
        if self.captcha_service == "2captcha":
            logger.info(f"Отправляем капчу типа {captcha_type} на решение с помощью 2captcha...")
            
            try:
                solver = TwoCaptcha(self.captcha_api_key)
                
                if captcha_type == 'recaptcha':
                    site_key = self.get_recaptcha_sitekey()
                    if not site_key:
                        logger.error("Не удалось получить site key для reCAPTCHA")
                        return None
                    
                    logger.info(f"Решаем reCAPTCHA с site key: {site_key}")
                    result = solver.recaptcha(
                        sitekey=site_key,
                        url=self.driver.current_url
                    )
                    
                    return result.get('code')
                    
                elif captcha_type == 'funcaptcha':
                    site_key = self.get_funcaptcha_sitekey()
                    if not site_key:
                        logger.error("Не удалось получить site key для FunCaptcha")
                        return None
                    
                    logger.info(f"Решаем FunCaptcha с site key: {site_key}")
                    result = solver.funcaptcha(
                        sitekey=site_key,
                        url=self.driver.current_url
                    )
                    
                    return result.get('code')
                    
                elif captcha_type == 'normal':
                    captcha_image = self.get_captcha_image()
                    if not captcha_image:
                        logger.error("Не удалось получить изображение обычной капчи")
                        return None
                    
                    logger.info("Решаем обычную изображение-капчу")
                    result = solver.normal(captcha_image)
                    
                    return result.get('code')
                
                logger.error(f"Неизвестный тип капчи: {captcha_type}")
                return None
                
            except Exception as e:
                logger.error(f"Ошибка при решении капчи через 2captcha: {e}")
                return None
                
        elif self.captcha_service == "next_captcha":
            return self.solve_captcha_with_next_captcha(captcha_type)
        else:
            logger.error(f"Неизвестный сервис решения капчи: {self.captcha_service}")
            return None
            
    def solve_captcha_with_next_captcha(self, captcha_type: str) -> Optional[str]:
        """
        Решает капчу с помощью сервиса Next CAPTCHA
        
        Args:
            captcha_type: Тип капчи для решения ('recaptcha', 'funcaptcha', 'normal')
            
        Returns:
            Строка с решением капчи или None в случае ошибки
        """
        if not self.captcha_api_key:
            logger.error("API ключ для Next CAPTCHA не найден")
            return None
            
        logger.info(f"Отправляем капчу типа {captcha_type} на решение с помощью Next CAPTCHA...")
        
        try:
            if captcha_type == 'recaptcha':
                site_key = self.get_recaptcha_sitekey()
                if not site_key:
                    logger.error("Не удалось получить site key для reCAPTCHA")
                    return None
                
                logger.info(f"Решаем reCAPTCHA с site key: {site_key}")
                
                # Создаем задачу на решение reCAPTCHA
                task_data = {
                    "key": self.captcha_api_key,
                    "method": "recaptcha_v2",
                    "pageURL": self.driver.current_url,
                    "sitekey": site_key
                }
                
                # Создаем задачу
                response = requests.post(f"{self.next_captcha_url}/task", json=task_data)
                
                if response.status_code == 200:
                    task_result = response.json()
                    if task_result.get("success"):
                        task_id = task_result.get("taskId")
                        
                        # Ждем решения
                        for attempt in range(60):  # Максимум 60 попыток (2 минуты)
                            time.sleep(2)
                            solve_response = requests.get(
                                f"{self.next_captcha_url}/task/{task_id}?key={self.captcha_api_key}"
                            )
                            
                            if solve_response.status_code == 200:
                                solve_result = solve_response.json()
                                
                                if solve_result.get("success"):
                                    solution = solve_result.get("solution", {})
                                    
                                    if solution and solution.get("status") == "solved":
                                        g_recaptcha_response = solution.get("gRecaptchaResponse")
                                        if g_recaptcha_response:
                                            logger.info("Получено решение reCAPTCHA от Next CAPTCHA")
                                            return g_recaptcha_response
                                    
                                    if solution and solution.get("status") == "failed":
                                        logger.error(f"Next CAPTCHA не смогла решить reCAPTCHA: {solution.get('error')}")
                                        return None
                                        
                                else:
                                    logger.warning(f"Ошибка при получении статуса задачи: {solve_result.get('error')}")
                        
                        logger.error("Истекло время ожидания решения reCAPTCHA")
                    else:
                        logger.error(f"Ошибка при создании задачи: {task_result.get('error')}")
                else:
                    logger.error(f"Ошибка запроса к Next CAPTCHA API: {response.status_code}")
                
                return None
                
            elif captcha_type == 'normal':
                captcha_image = self.get_captcha_image()
                if not captcha_image:
                    logger.error("Не удалось получить изображение обычной капчи")
                    return None
                
                logger.info("Решаем обычную изображение-капчу через Next CAPTCHA")
                
                # Создаем задачу на решение обычной captcha
                task_data = {
                    "key": self.captcha_api_key,
                    "method": "image",
                    "body": captcha_image,
                    "caseSensitive": True
                }
                
                # Создаем задачу
                response = requests.post(f"{self.next_captcha_url}/task", json=task_data)
                
                if response.status_code == 200:
                    task_result = response.json()
                    if task_result.get("success"):
                        task_id = task_result.get("taskId")
                        
                        # Ждем решения
                        for attempt in range(30):  # Максимум 30 попыток (1 минута)
                            time.sleep(2)
                            solve_response = requests.get(
                                f"{self.next_captcha_url}/task/{task_id}?key={self.captcha_api_key}"
                            )
                            
                            if solve_response.status_code == 200:
                                solve_result = solve_response.json()
                                
                                if solve_result.get("success"):
                                    solution = solve_result.get("solution", {})
                                    
                                    if solution and solution.get("status") == "solved":
                                        text = solution.get("text")
                                        if text:
                                            logger.info("Получено решение обычной капчи от Next CAPTCHA")
                                            return text
                                    
                                    if solution and solution.get("status") == "failed":
                                        logger.error(f"Next CAPTCHA не смогла решить обычную капчу: {solution.get('error')}")
                                        return None
                                        
                                else:
                                    logger.warning(f"Ошибка при получении статуса задачи: {solve_result.get('error')}")
                        
                        logger.error("Истекло время ожидания решения обычной капчи")
                    else:
                        logger.error(f"Ошибка при создании задачи: {task_result.get('error')}")
                else:
                    logger.error(f"Ошибка запроса к Next CAPTCHA API: {response.status_code}")
                
                return None
                
            elif captcha_type == 'funcaptcha':
                site_key = self.get_funcaptcha_sitekey()
                if not site_key:
                    logger.error("Не удалось получить site key для FunCaptcha")
                    return None
                
                logger.info(f"Решаем FunCaptcha с site key: {site_key}")
                
                # Создаем задачу на решение FunCaptcha
                task_data = {
                    "key": self.captcha_api_key,
                    "method": "funcaptcha",
                    "pageURL": self.driver.current_url,
                    "publicKey": site_key
                }
                
                # Создаем задачу
                response = requests.post(f"{self.next_captcha_url}/task", json=task_data)
                
                if response.status_code == 200:
                    task_result = response.json()
                    if task_result.get("success"):
                        task_id = task_result.get("taskId")
                        
                        # Ждем решения
                        for attempt in range(60):  # Максимум 60 попыток (2 минуты)
                            time.sleep(2)
                            solve_response = requests.get(
                                f"{self.next_captcha_url}/task/{task_id}?key={self.captcha_api_key}"
                            )
                            
                            if solve_response.status_code == 200:
                                solve_result = solve_response.json()
                                
                                if solve_result.get("success"):
                                    solution = solve_result.get("solution", {})
                                    
                                    if solution and solution.get("status") == "solved":
                                        token = solution.get("token")
                                        if token:
                                            logger.info("Получено решение FunCaptcha от Next CAPTCHA")
                                            return token
                                    
                                    if solution and solution.get("status") == "failed":
                                        logger.error(f"Next CAPTCHA не смогла решить FunCaptcha: {solution.get('error')}")
                                        return None
                                        
                                else:
                                    logger.warning(f"Ошибка при получении статуса задачи: {solve_result.get('error')}")
                        
                        logger.error("Истекло время ожидания решения FunCaptcha")
                    else:
                        logger.error(f"Ошибка при создании задачи: {task_result.get('error')}")
                else:
                    logger.error(f"Ошибка запроса к Next CAPTCHA API: {response.status_code}")
                
                return None
            
            logger.error(f"Неизвестный тип капчи для Next CAPTCHA: {captcha_type}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при решении капчи через Next CAPTCHA: {e}")
            return None

    def solve_ozon_captcha(self) -> bool:
        """
        Специальный метод для решения капчи на сайте Ozon
        
        Returns:
            True, если капча успешно решена, False в противном случае
        """
        try:
            logger.info("Запуск специального метода для решения капчи Ozon")
            
            # 1. Поиск изображения капчи по специфичным селекторам Ozon
            captcha_selectors = [
                "img.gn3", 
                "img[data-widget='AdvancedCaptcha']",
                "div[data-widget='captcha'] img",
                "img.captcha-img",
                ".tsBodyL img", 
                "form img"
            ]
            
            captcha_image = None
            for selector in captcha_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        for element in elements:
                            if element.is_displayed():
                                captcha_image = element
                                logger.info(f"Найдено изображение капчи: {selector}")
                                break
                        if captcha_image:
                            break
                except Exception as e:
                    logger.warning(f"Ошибка при поиске изображения по селектору {selector}: {e}")
            
            if not captcha_image:
                logger.warning("Изображение капчи не найдено по специфичным селекторам")
                
                # Попробуем найти любые изображения на странице
                try:
                    all_images = self.driver.find_elements(By.TAG_NAME, "img")
                    for img in all_images:
                        if img.is_displayed():
                            try:
                                width = img.get_attribute("width")
                                height = img.get_attribute("height")
                                
                                # Проверяем размеры (обычно капчи имеют определенные размеры)
                                if width and height:
                                    w = int(width)
                                    h = int(height)
                                    # Капчи обычно не очень большие и не очень маленькие
                                    if 50 <= w <= 300 and 30 <= h <= 150:
                                        captcha_image = img
                                        logger.info(f"Найдено потенциальное изображение капчи размером {w}x{h}")
                                        break
                            except:
                                continue
                except Exception as e:
                    logger.warning(f"Ошибка при поиске изображений на странице: {e}")
            
            # Если нашли изображение, пытаемся его распознать
            if captcha_image:
                # Получаем изображение в base64
                try:
                    src = captcha_image.get_attribute("src")
                    if src:
                        if src.startswith("data:image"):
                            # Уже в формате base64
                            image_base64 = src.split("base64,")[1]
                        else:
                            # Скачиваем изображение
                            response = requests.get(src)
                            if response.status_code == 200:
                                image_base64 = base64.b64encode(response.content).decode("utf-8")
                            else:
                                # Если не удалось скачать, делаем скриншот элемента
                                image_base64 = captcha_image.screenshot_as_base64
                    else:
                        # Если нет src, делаем скриншот элемента
                        image_base64 = captcha_image.screenshot_as_base64
                        
                    # Отправляем изображение на решение
                    solution = None
                    
                    # Используем наш OzonCaptchaSolver если он доступен
                    if OZON_CAPTCHA_SOLVER_AVAILABLE and self.ozon_captcha_solver:
                        solution = self.ozon_captcha_solver.solve_image_captcha(image_base64)
                        
                    # Если через OzonCaptchaSolver не получилось, пробуем стандартные методы
                    if not solution:
                        # Сначала пробуем через CapMonster если он настроен
                        if self.capmonster_client and CAPMONSTER_AVAILABLE and self.captcha_service == "capmonster":
                            try:
                                image_request = ImageToTextRequest(body=image_base64)
                                task_id = self.capmonster_client.create_task(image_request)
                                if task_id:
                                    result = self.capmonster_client.get_task_result(task_id, timeout=60)
                                    if result and result.get("solution") and result["solution"].get("text"):
                                        solution = result["solution"]["text"]
                                        logger.info(f"Получено решение капчи Ozon через CapMonster Cloud: {solution}")
                            except Exception as e:
                                logger.warning(f"Ошибка при решении через CapMonster Cloud: {e}")
                        
                        # Если через CapMonster не получилось, пробуем через 2captcha
                        if not solution and self.captcha_solver:
                            try:
                                result = self.captcha_solver.normal(image_base64)
                                solution = result.get('code')
                                logger.info(f"Получено решение капчи Ozon через 2captcha: {solution}")
                            except Exception as e:
                                logger.warning(f"Ошибка при решении через 2captcha: {e}")
                        
                        # Если через 2captcha не получилось, пробуем через AntiCaptcha
                        if not solution and self.anticaptcha_client and ANTICAPTCHA_AVAILABLE:
                            try:
                                task = ImageToTextTask(base64.b64decode(image_base64))
                                job = self.anticaptcha_client.createTask(task)
                                job.join(maximum_time=60)
                                solution = job.get_solution_response()
                                logger.info(f"Получено решение капчи Ozon через AntiCaptcha: {solution}")
                            except Exception as e:
                                logger.warning(f"Ошибка при решении через AntiCaptcha: {e}")
                                
                    if not solution:
                        logger.error("Не удалось получить решение капчи ни через один сервис")
                        return False
                    
                    # Ищем поле ввода для капчи
                    input_selectors = [
                        "input.fo3",
                        "input[data-widget='AdvancedCaptcha']",
                        "input[name*='captcha']",
                        "input[placeholder*='Введите']", 
                        "input[type='text']",
                        ".tsBodyL input",
                        "form input[type='text']"
                    ]
                    
                    input_field = None
                    for selector in input_selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                for element in elements:
                                    if element.is_displayed() and element.is_enabled():
                                        input_field = element
                                        logger.info(f"Найдено поле для ввода капчи: {selector}")
                                        break
                                if input_field:
                                    break
                        except:
                            continue
                    
                    if input_field:
                        # Вводим решение
                        input_field.clear()
                        
                        # Вводим посимвольно с небольшими задержками для естественности
                        for char in solution:
                            input_field.send_keys(char)
                            time.sleep(random.uniform(0.05, 0.1))
                        
                        logger.info(f"Решение капчи введено: {solution}")
                        
                        # Ищем кнопку отправки
                        submit_selectors = [
                            "button[type='submit']", 
                            "input[type='submit']", 
                            "button:contains('Подтвердить')",
                            "button:contains('Проверить')",
                            "button.submit-button",
                            ".captcha-submit",
                            "button.primary",
                            "button.btn-primary",
                            # Специфично для Ozon
                            "button.jsButton",
                            "button.tsBodyL",
                            "button.j4c",
                            "form button",
                            "button[data-test-id='captchaSubmitButton']"
                        ]
                        
                        # Если мы на Ozon, приоритезируем специфичные для Ozon селекторы
                        if 'ozon.ru' in self.driver.current_url:
                            ozon_selectors = [
                                "button.tsBodyL",
                                "button.j4c",
                                "form button",
                                "button[data-test-id='captchaSubmitButton']",
                                "button.jsButton"
                            ]
                            submit_selectors = ozon_selectors + submit_selectors
                        
                        submit_button = None
                        for selector in submit_selectors:
                            try:
                                buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                if buttons:
                                    for button in buttons:
                                        if button.is_displayed() and button.is_enabled():
                                            submit_button = button
                                            logger.info(f"Найдена кнопка отправки: {selector}")
                                            break
                                    if submit_button:
                                        break
                            except:
                                continue
                        
                        if submit_button:
                            # Нажимаем на кнопку
                            logger.info("Нажимаем на кнопку отправки")
                            submit_button.click()
                        else:
                            # Если не нашли кнопку, нажимаем Enter в поле
                            logger.info("Кнопка не найдена, нажимаем Enter в поле ввода")
                            input_field.send_keys(Keys.ENTER)
                    else:
                        logger.error("Не найдено поле для ввода решения капчи")
                        return False
                        
                    # Ждем, чтобы страница обновилась
                    logger.info("Ждем обработки решения капчи...")
                    time.sleep(5)
                    
                    # Проверяем, исчезла ли капча
                    if not self.is_captcha_present():
                        logger.info("Капча успешно решена!")
                        return True
                    else:
                        logger.warning("Капча все еще присутствует, решение не помогло")
                        
                        # Делаем еще одну попытку - иногда нужно дождаться завершения обработки
                        logger.info("Делаем дополнительную паузу и проверяем еще раз...")
                        time.sleep(3)
                        
                        if not self.is_captcha_present():
                            logger.info("Капча все-таки исчезла после дополнительного ожидания!")
                            return True
                            
                        return False
                except Exception as e:
                    logger.warning(f"Ошибка при обработке изображения капчи: {e}")
                    return False
            
            return True
            
        except Exception as e:
            logger.exception(f"Ошибка в методе solve_ozon_captcha: {e}")
            return False

    def handle_captcha(self) -> bool:
        """
        Обработка капчи на странице
        
        Returns:
            True, если капча успешно решена, False в противном случае
        """
        try:
            # Если доступен наш новый решатель, пробуем использовать его
            if OZON_CAPTCHA_SOLVER_AVAILABLE and self.ozon_captcha_solver:
                logger.info("Используем OzonCaptchaSolver для решения капчи")
                try:
                    result = self.ozon_captcha_solver.handle_ozon_captcha(self.driver)
                    if result:
                        logger.info("Капча успешно решена через OzonCaptchaSolver")
                        return True
                    else:
                        logger.warning("OzonCaptchaSolver не смог решить капчу, пробуем стандартные методы")
                except Exception as e:
                    logger.error(f"Ошибка при использовании OzonCaptchaSolver: {e}")
            
            # Если OzonCaptchaSolver не сработал или недоступен, используем стандартные методы
            
            # Проверяем наличие настроенного решателя капчи
            has_capmonster = CAPMONSTER_AVAILABLE and self.capmonster_client
            has_2captcha = self.captcha_solver is not None
            has_anticaptcha = ANTICAPTCHA_AVAILABLE and self.anticaptcha_client
            
            if not has_capmonster and not has_2captcha and not has_anticaptcha:
                logger.warning("Отсутствуют настроенные решатели капчи")
                return False
                
            # Специальная обработка для Ozon
            if 'ozon.ru' in self.driver.current_url:
                logger.info("Обнаружена капча на сайте Ozon, используем специальный метод")
                
                # Не сохраняем скриншоты, чтобы не засорять директорию
                # Для Ozon пробуем последовательно все методы решения капчи
                methods = [
                    ("normal", "Обычная капча с изображением"),
                    ("recaptcha", "reCAPTCHA"),
                    ("funcaptcha", "FunCaptcha/ArkoseLabs")
                ]
                
                for captcha_type, desc in methods:
                    logger.info(f"Пробуем решить как {desc}")
                    
                    # Получаем решение через соответствующий сервис
                    solution = None
                    
                    if has_capmonster and self.captcha_service == "capmonster":
                        try:
                            logger.info(f"Решаем через CapMonster Cloud...")
                            solution = self.solve_captcha_with_capmonster(captcha_type)
                            if solution:
                                logger.info(f"Получено решение через CapMonster Cloud для {desc}")
                                result = self.submit_captcha_solution(captcha_type, solution)
                                
                                # Проверяем, исчезла ли капча
                                if not self.is_captcha_present():
                                    logger.info(f"Капча успешно решена через CapMonster Cloud как {desc}!")
                                    return True
                                else:
                                    logger.warning(f"Капча все еще присутствует после отправки решения для {desc}")
                        except Exception as e:
                            logger.error(f"Ошибка при решении капчи {desc} через CapMonster Cloud: {e}")
                    
                    if not solution and has_2captcha:
                        try:
                            logger.info(f"Решаем через 2Captcha...")
                            solution = self.solve_captcha_with_2captcha(captcha_type)
                            if solution:
                                logger.info(f"Получено решение через 2captcha для {desc}")
                                result = self.submit_captcha_solution(captcha_type, solution)
                                
                                if not self.is_captcha_present():
                                    logger.info(f"Капча успешно решена через 2Captcha как {desc}!")
                                    return True
                                else:
                                    logger.warning(f"Капча все еще присутствует после отправки решения для {desc}")
                        except Exception as e:
                            logger.error(f"Ошибка при решении капчи {desc} через 2Captcha: {e}")
                    
                    if not solution and has_anticaptcha:
                        try:
                            logger.info(f"Решаем через AntiCaptcha...")
                            solution = self.solve_captcha_with_anticaptcha(captcha_type)
                            if solution:
                                logger.info(f"Получено решение через AntiCaptcha для {desc}")
                                result = self.submit_captcha_solution(captcha_type, solution)
                                
                                if not self.is_captcha_present():
                                    logger.info(f"Капча успешно решена через AntiCaptcha как {desc}!")
                                    return True
                                else:
                                    logger.warning(f"Капча все еще присутствует после отправки решения для {desc}")
                        except Exception as e:
                            logger.error(f"Ошибка при решении капчи {desc} через AntiCaptcha: {e}")
                    
                    # Делаем паузу перед следующей попыткой
                    time.sleep(2)
                
                # Если не помогло пошаговое решение, пробуем метод с ozon_captcha
                logger.info("Стандартные методы не сработали, пробуем специальный метод для Ozon")
                return self.solve_ozon_captcha()
                
            # Для других сайтов используем обычный подход с определением типа
            captcha_type = self.detect_captcha_type()
            logger.info(f"Определен тип капчи: {captcha_type}")
            
            if captcha_type == 'recaptcha':
                logger.info("Запускаем решение reCAPTCHA")
                return self.solve_recaptcha()
                
            elif captcha_type == 'funcaptcha':
                logger.info("Запускаем решение FunCaptcha")
                return self.solve_funcaptcha()
                
            elif captcha_type == 'normal':
                logger.info("Запускаем решение обычной капчи")
                # Находим изображение капчи
                captcha_images = self.driver.find_elements(By.CSS_SELECTOR, 
                    "img[id*='captcha'], img[class*='captcha'], img[src*='captcha'], .captcha img, img.captcha, img.gn3, img[alt*='captcha'], img[data-widget='AdvancedCaptcha']")
                
                if captcha_images and any(img.is_displayed() for img in captcha_images):
                    for img in captcha_images:
                        if img.is_displayed():
                            return self.solve_image_captcha(img)
                
                # Если не нашли изображение, пробуем получить скриншот всей страницы
                logger.info("Изображение капчи не найдено, пробуем решить капчу по скриншоту")
                page_screenshot = self.driver.get_screenshot_as_base64()
                if page_screenshot:
                    try:
                        # Выбираем сервис для решения
                        solution = None
                        if has_capmonster and self.captcha_service == "capmonster":
                            solution = self.solve_captcha_with_capmonster('normal')
                        elif has_2captcha:
                            solution = self.solve_captcha_with_2captcha('normal')
                        elif has_anticaptcha:
                            solution = self.solve_captcha_with_anticaptcha('normal')
                            
                        if solution:
                            logger.info(f"Получено решение капчи по скриншоту: {solution}")
                            
                            # Ищем поле ввода
                            input_selectors = [
                                "input[name*='captcha']", 
                                "input[placeholder*='captcha']", 
                                "input[type='text']",
                                "input.fo3",
                                "input.tsBodyM"
                            ]
                            
                            for selector in input_selectors:
                                try:
                                    input_fields = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                    for field in input_fields:
                                        if field.is_displayed() and field.is_enabled():
                                            field.clear()
                                            field.send_keys(solution)
                                            field.send_keys(Keys.ENTER)
                                            time.sleep(2)
                                            
                                            # Проверяем, исчезла ли капча
                                            if not self.is_captcha_present():
                                                logger.info("Капча успешно решена!")
                                                return True
                                except Exception as e:
                                    logger.warning(f"Ошибка при работе с полем ввода {selector}: {e}")
                                    continue
                    except Exception as e:
                        logger.error(f"Ошибка при решении капчи по скриншоту: {e}")
                
                logger.warning("Не найдено изображение капчи")
                return False
                
            logger.warning(f"Неизвестный тип капчи: {captcha_type}")
            return False
                
        except Exception as e:
            logger.exception(f"Ошибка при обработке капчи: {e}")
            return False

    def solve_recaptcha(self) -> bool:
        """
        Решение reCAPTCHA
        
        Returns:
            True, если капча успешно решена, False в противном случае
        """
        try:
            # Используем 2captcha для решения reCAPTCHA
            
            # Получаем sitekey
            sitekey = self.get_recaptcha_sitekey()
            if not sitekey:
                logger.error("Не удалось получить sitekey для reCAPTCHA")
                return False
                
            # Получаем URL страницы
            page_url = self.driver.current_url
            
            logger.info(f"Отправляем запрос на решение reCAPTCHA: sitekey={sitekey}, url={page_url}")
            
            if self.captcha_service == "2captcha":
                # Отправляем запрос на 2captcha
                try:
                    result = self.captcha_solver.recaptcha(
                        sitekey=sitekey,
                        url=page_url
                    )
                    
                    solution = result.get('code')
                    logger.info(f"Получено решение reCAPTCHA: {solution[:20]}...")
                    
                    # Отправляем решение
                    return self.submit_captcha_solution('recaptcha', solution)
                    
                except Exception as e:
                    logger.error(f"Ошибка при решении reCAPTCHA через 2captcha: {e}")
                    return False
                    
            return False
            
        except Exception as e:
            logger.exception(f"Ошибка при решении reCAPTCHA: {e}")
            return False

    def solve_funcaptcha(self) -> bool:
        """
        Решение FunCaptcha
        
        Returns:
            True, если капча успешно решена, False в противном случае
        """
        try:
            # Используем 2captcha для решения FunCaptcha
            
            # Получаем данные для FunCaptcha
            sitekey = self.get_funcaptcha_sitekey()
            if not sitekey:
                logger.error("Не удалось получить данные для FunCaptcha")
                return False
                
            # Получаем URL страницы
            page_url = self.driver.current_url
            
            logger.info(f"Отправляем запрос на решение FunCaptcha: sitekey={sitekey}, url={page_url}")
            
            if self.captcha_service == "2captcha":
                # Отправляем запрос на 2captcha
                try:
                    result = self.captcha_solver.funcaptcha(
                        sitekey=sitekey,
                        url=page_url
                    )
                    
                    solution = result.get('code')
                    logger.info(f"Получено решение FunCaptcha: {solution[:20]}...")
                    
                    # Отправляем решение
                    return self.submit_captcha_solution('funcaptcha', solution)
                    
                except Exception as e:
                    logger.error(f"Ошибка при решении FunCaptcha через 2captcha: {e}")
                    return False
                    
            return False
            
        except Exception as e:
            logger.exception(f"Ошибка при решении FunCaptcha: {e}")
            return False

    def solve_image_captcha(self, image_element) -> bool:
        """
        Решение обычной капчи с изображением
        
        Args:
            image_element: Элемент с изображением капчи
            
        Returns:
            True, если капча успешно решена, False в противном случае
        """
        try:
            # Получаем изображение капчи в base64
            image_base64 = self.get_image_base64(image_element)
            if not image_base64:
                logger.error("Не удалось получить изображение капчи")
                return False
                
            logger.info("Отправляем запрос на решение обычной капчи")
            
            if self.captcha_service == "2captcha":
                # Отправляем запрос на 2captcha
                try:
                    result = self.captcha_solver.normal(image_base64)
                    
                    solution = result.get('code')
                    logger.info(f"Получено решение обычной капчи: {solution}")
                    
                    # Находим поле ввода
                    input_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='captcha'], input.captcha-input, input[type='text']")
                    if not input_field:
                        logger.error("Не удалось найти поле для ввода решения капчи")
                        return False
                        
                    # Вводим решение
                    input_field.clear()
                    input_field.send_keys(solution)
                    input_field.send_keys(Keys.ENTER)
                    
                    # Ждем обработки
                    time.sleep(2)
                    
                    # Проверяем, исчезла ли капча
                    return not self.is_captcha_present()
                    
                except Exception as e:
                    logger.error(f"Ошибка при решении обычной капчи через 2captcha: {e}")
                    return False
                    
            return False
            
        except Exception as e:
            logger.exception(f"Ошибка при решении обычной капчи: {e}")
            return False

    def get_image_base64(self, image_element) -> str:
        """
        Получение изображения капчи в формате base64
        
        Args:
            image_element: Элемент с изображением капчи
            
        Returns:
            Строка с изображением в формате base64 или пустая строка в случае ошибки
        """
        try:
            # Получаем URL изображения
            src = image_element.get_attribute("src")
            
            if src.startswith("data:image"):
                # Изображение уже в формате base64
                return src.split(",")[1]
                
            # Если изображение по URL, скачиваем его
            response = requests.get(src)
            if response.status_code == 200:
                image_data = base64.b64encode(response.content).decode('utf-8')
                return image_data
                
            return ""
            
        except Exception as e:
            logger.exception(f"Ошибка при получении изображения капчи: {e}")
            return ""

    def submit_captcha_solution(self, captcha_type: str, solution: str) -> bool:
        """
        Отправляет решение капчи на сайт
        
        Args:
            captcha_type: Тип капчи ('recaptcha', 'funcaptcha', 'normal')
            solution: Решение капчи
            
        Returns:
            True, если решение было успешно отправлено, иначе False
        """
        try:
            logger.info(f"Отправляем решение капчи типа {captcha_type}")
            
            # Для Ozon используем специальный подход
            is_ozon = 'ozon.ru' in self.driver.current_url
            
            if captcha_type == 'recaptcha':
                # Для reCAPTCHA используем JavaScript
                logger.info("Отправляем решение reCAPTCHA через JavaScript")
                
                # Попробуем разные способы внедрения решения
                scripts = [
                    f'document.getElementById("g-recaptcha-response").innerHTML="{solution}";',
                    f'document.querySelector(".g-recaptcha-response").innerHTML="{solution}";',
                    f'var x = document.getElementsByName("g-recaptcha-response"); if(x.length > 0) x[0].innerHTML="{solution}";',
                    f'Array.from(document.querySelectorAll("textarea")).filter(el => el.id.includes("captcha")).forEach(el => el.innerHTML = "{solution}");'
                ]
                
                for script in scripts:
                    try:
                        self.driver.execute_script(script)
                        logger.info("JavaScript выполнен успешно")
                    except Exception as e:
                        logger.debug(f"Ошибка выполнения скрипта: {e}")
                
                # Вызываем событие изменения для активации проверки капчи
                try:
                    self.driver.execute_script('document.querySelector(".g-recaptcha-response").dispatchEvent(new Event("change"));')
                except:
                    pass
                
            elif captcha_type == 'funcaptcha':
                # Для FunCaptcha обычно тоже используется JavaScript
                logger.info("Отправляем решение FunCaptcha")
                
                scripts = [
                    f'document.querySelector("iframe[src*=\'funcaptcha\']").contentWindow.postMessage({{token: "{solution}"}}, "*");',
                    f'window.postMessage({{eventId: "challenge-complete", payload: {{sessionToken: "{solution}"}}}}, "*");',
                    f'window.arkoseEnforcement && window.arkoseEnforcement.setAuthToken("{solution}");'
                ]
                
                for script in scripts:
                    try:
                        self.driver.execute_script(script)
                        logger.info("JavaScript для FunCaptcha выполнен успешно")
                    except Exception as e:
                        logger.debug(f"Ошибка выполнения скрипта для FunCaptcha: {e}")
                
            elif captcha_type == 'normal':
                # Для обычной капчи ищем поле ввода
                logger.info("Ищем поле ввода для обычной капчи")
                
                # Более широкий список селекторов для поля ввода капчи
                input_selectors = [
                    "input[name*='captcha']", 
                    "input[placeholder*='captcha']", 
                    "input[aria-label*='captcha']",
                    "input[id*='captcha']",
                    "input[class*='captcha']",
                    ".captcha input",
                    "input.captcha-input",
                    # Специфично для Ozon
                    "input.fo3",
                    "input.tsBodyM",
                    "input[data-widget='AdvancedCaptcha']",
                    # Общие селекторы
                    "input[type='text']",
                    "form input[type='text']",
                    ".tsBodyL input",
                ]
                
                # Если мы на Ozon, приоритезируем специфичные для Ozon селекторы
                if is_ozon:
                    ozon_selectors = [
                        "input.fo3",
                        "input.tsBodyM",
                        "input[data-widget='AdvancedCaptcha']",
                        ".tsBodyL input",
                        "form input[type='text']"
                    ]
                    input_selectors = ozon_selectors + input_selectors
                
                input_field = None
                for selector in input_selectors:
                    try:
                        fields = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if fields:
                            for field in fields:
                                if field.is_displayed() and field.is_enabled():
                                    input_field = field
                                    logger.info(f"Найдено поле для ввода капчи: {selector}")
                                    break
                            if input_field:
                                break
                    except:
                        continue
                
                if input_field:
                    # Вводим решение
                    input_field.clear()
                    
                    # Вводим посимвольно с небольшими задержками для естественности
                    for char in solution:
                        input_field.send_keys(char)
                        time.sleep(random.uniform(0.05, 0.1))
                        
                    logger.info(f"Решение капчи введено: {solution}")
                    
                    # Ищем кнопку отправки
                    submit_selectors = [
                        "button[type='submit']", 
                        "input[type='submit']", 
                        "button:contains('Подтвердить')",
                        "button:contains('Проверить')",
                        "button.submit-button",
                        ".captcha-submit",
                        "button.primary",
                        "button.btn-primary",
                        # Специфично для Ozon
                        "button.jsButton",
                        "button.tsBodyL",
                        "button.j4c",
                        "form button",
                        "button[data-test-id='captchaSubmitButton']"
                    ]
                    
                    # Если мы на Ozon, приоритезируем специфичные для Ozon селекторы
                    if is_ozon:
                        ozon_submit_selectors = [
                            "button.tsBodyL",
                            "button.j4c",
                            "form button",
                            "button[data-test-id='captchaSubmitButton']",
                            "button.jsButton"
                        ]
                        submit_selectors = ozon_submit_selectors + submit_selectors
                    
                    submit_button = None
                    for selector in submit_selectors:
                        try:
                            buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if buttons:
                                for button in buttons:
                                    if button.is_displayed() and button.is_enabled():
                                        submit_button = button
                                        logger.info(f"Найдена кнопка отправки: {selector}")
                                        break
                                if submit_button:
                                    break
                        except:
                            continue
                    
                    if submit_button:
                        # Нажимаем на кнопку
                        logger.info("Нажимаем на кнопку отправки")
                        submit_button.click()
                    else:
                        # Если не нашли кнопку, нажимаем Enter в поле
                        logger.info("Кнопка не найдена, нажимаем Enter в поле ввода")
                        input_field.send_keys(Keys.ENTER)
                else:
                    logger.error("Не найдено поле для ввода решения капчи")
                    return False
            
            # Ждем, чтобы страница обновилась
            logger.info("Ждем обработки решения капчи...")
            time.sleep(5)
            
            # Проверяем, исчезла ли капча
            if not self.is_captcha_present():
                logger.info("Капча успешно решена!")
                return True
            else:
                logger.warning("Капча все еще присутствует, решение не помогло")
                
                # Делаем еще одну попытку - иногда нужно дождаться завершения обработки
                logger.info("Делаем дополнительную паузу и проверяем еще раз...")
                time.sleep(3)
                
                if not self.is_captcha_present():
                    logger.info("Капча все-таки исчезла после дополнительного ожидания!")
                    return True
                    
                return False
            
        except Exception as e:
            logger.error(f"Ошибка при отправке решения капчи: {e}")
            return False

    def initialize_driver(self) -> bool:
        """
        Initialize the Selenium WebDriver
        
        Returns:
            True if driver initialized successfully, False otherwise
        """
        try:
            if not self.driver:
                self.setup_driver()
            return True
        except Exception as e:
            logger.exception(f"Ошибка инициализации драйвера: {e}")
            return False

    def search_by_article(self, article, target_price=None, price_tolerance=0.2):
        """
        Ищет товар по артикулу и возвращает информацию о нем
        
        Args:
            article: Артикул товара
            target_price: Целевая цена
            price_tolerance: Допустимое отклонение цены в процентах
            
        Returns:
            Словарь с информацией о товаре
        """
        if not article:
            logger.warning("Артикул не указан")
            return None
            
        # Формируем данные для сообщения без открытия браузера
        article = article.strip()
        product_url = f"https://www.ozon.ru/product/{article}/"
        direct_search_url = f"https://www.ozon.ru/search/?text={article}&from_global=true"
            
        # Возвращаем информацию для отображения пользователю
        product_info = ProductInfo(
            name=f"Товар с артикулом {article}",
            price=target_price or 0,
            article=article,
            url=product_url,
            seller="Информация доступна по ссылке"
        )
        
        # Сохраняем дополнительную информацию как атрибуты
        product_info.direct_search_url = direct_search_url
        
        return product_info

    def extract_product_info(self, product_element):
        """
        Извлекает информацию о товаре из элемента на странице
        
        Args:
            product_element: Элемент товара
            
        Returns:
            Dict с информацией о товаре или None в случае ошибки
        """
        try:
            # Извлекаем название товара
            name_element = product_element.find_element(By.CSS_SELECTOR, "a.tile-hover-target span.tsBody")
            name = name_element.text
            
            # Извлекаем URL товара
            url_element = product_element.find_element(By.CSS_SELECTOR, "a.tile-hover-target")
            url = url_element.get_attribute("href")
            
            # Извлекаем цену
            price_element = product_element.find_element(By.CSS_SELECTOR, "span.tsBodyL:not(.tsBodyLBold)")
            price_text = price_element.text.replace(' ', '').replace('₽', '').replace(',', '.').strip()
            
            try:
                price = float(price_text)
            except ValueError:
                logger.warning(f"Не удалось преобразовать цену '{price_text}' в число")
                return None
                
            # Извлекаем артикул из URL или названия
            article = ""
            if url:
                # Пытаемся извлечь артикул из URL
                url_parts = url.split('/')
                for part in url_parts:
                    if part.isdigit() and len(part) > 5:
                        article = part
                        break
            
            if not article:
                # Если не удалось извлечь из URL, извлекаем из названия
                words = name.split()
                for word in words:
                    if any(c.isdigit() for c in word) and len(word) >= 5:
                        article = word
                        break
            
            # Извлекаем продавца
            seller = "Неизвестный продавец"
            try:
                seller_element = product_element.find_element(By.CSS_SELECTOR, "span.tsBodyM")
                if seller_element:
                    seller = seller_element.text
            except NoSuchElementException:
                pass
            
            return {
                "name": name,
                "article": article,
                "price": price,
                "url": url,
                "seller": seller
            }
            
        except NoSuchElementException as e:
            logger.warning(f"Не удалось найти один из элементов товара: {e}")
            return None
        except Exception as e:
            logger.exception(f"Ошибка при извлечении информации о товаре: {e}")
            return None

    def is_driver_closed(self):
        """
        Проверяет, закрыто ли окно драйвера
        """
        try:
            # Пробуем выполнить простую операцию
            self.driver.current_url
            return False
        except (NoSuchWindowException, WebDriverException):
            return True
            
    async def extract_price_by_article(self, article: str) -> Dict[str, Any]:
        """
        Извлекает цену товара по артикулу
        
        Args:
            article: Артикул товара
            
        Returns:
            Dict с информацией о цене товара и валюте
        """
        try:
            # Используем существующий метод search_by_article
            product_info = self.search_by_article(article)
            
            if not product_info:
                logger.warning(f"Не удалось найти товар с артикулом {article}")
                return {"price": 0, "currency": "RUB"}
            
            # Возвращаем словарь с ценой и валютой
            return {
                "price": product_info.price,
                "currency": "RUB",  # Ozon обычно использует рубли
                "product_url": product_info.url,
                "search_url": product_info.direct_search_url
            }
        except Exception as e:
            logger.exception(f"Ошибка при извлечении цены товара по артикулу {article}: {e}")
            return {"price": 0, "currency": "RUB"}