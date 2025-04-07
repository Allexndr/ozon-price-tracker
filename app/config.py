# config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройки Telegram-бота
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не установлен. Добавьте его в .env файл.")

# Настройки периодического поиска товаров
SCHEDULED_SEARCH_ENABLED = os.getenv("SCHEDULED_SEARCH_ENABLED", "False").lower() == "true"
SCHEDULED_SEARCH_INTERVAL_HOURS = int(os.getenv("SCHEDULED_SEARCH_INTERVAL_HOURS", "6"))
SCHEDULED_SEARCH_MAX_THREADS = int(os.getenv("SCHEDULED_SEARCH_MAX_THREADS", "4"))
SCHEDULED_SEARCH_PRODUCT_FILE = os.getenv("SCHEDULED_SEARCH_PRODUCT_FILE", "products.txt")

# Настройки базы данных
DATABASE_PATH = os.getenv("DATABASE_PATH", "ozon_parser.db")

# Настройки браузера
HEADLESS_MODE = os.getenv("HEADLESS_MODE", "True").lower() == "true"
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

# Статусы и результаты поиска
PRICE_TOLERANCE_PERCENT = float(os.getenv("PRICE_TOLERANCE_PERCENT", "20"))  # Допустимое отклонение цены в процентах 

# Базовые настройки
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Создаем директорию для данных, если она не существует
DATA_DIR.mkdir(exist_ok=True)

# Настройки базы данных
DB_PATH = DATA_DIR / "ozon_bot.db"

# Задержки и таймауты (в секундах)
PARSE_DELAY = 2  # Задержка между запросами к Ozon
REQUEST_TIMEOUT = 30  # Таймаут для HTTP-запросов
LONG_PARSE_DELAY = 5  # Увеличенная задержка при парсинге большого количества данных

# Настройки парсера
MAX_RETRIES = 3  # Максимальное число повторных попыток при ошибке
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Настройки Selenium
CHROME_EXECUTABLE_PATH = os.getenv("CHROME_EXECUTABLE_PATH", "")  # Путь к исполняемому файлу Chrome

# Настройки бота
MAX_ITEMS_PER_USER = 100  # Максимальное количество товаров для одного пользователя
DAILY_WORD_UPDATE_HOUR = 0  # Час обновления стоп-слова (0-23) 