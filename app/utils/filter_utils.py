import os
import random
import string
import json
import sqlite3
from typing import List, Dict, Set, Any, Optional
from datetime import datetime, timedelta
from loguru import logger

class FilterManager:
    """
    Класс для управления фильтрами и стоп-словами
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Инициализация менеджера фильтров
        
        Args:
            db_path: Путь к файлу базы данных SQLite
        """
        self.stopwords: Set[str] = set()
        self.blacklist_sellers: Set[str] = set()
        self.daily_stop_word: str = ""
        self.daily_stop_word_date: datetime = datetime.now()
        self.db_path = db_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "filters.db")
        
        # Создаем директорию для базы данных, если она не существует
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Загружаем сохраненные фильтры
        self.load_filters()
        
        # Генерируем ежедневное стоп-слово, если необходимо
        self.update_daily_stop_word()
    
    def load_filters(self):
        """
        Загрузка фильтров из базы данных
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Создаем таблицы, если они не существуют
            c.execute('''
                CREATE TABLE IF NOT EXISTS stopwords (
                    word TEXT PRIMARY KEY
                )
            ''')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS blacklist_sellers (
                    seller TEXT PRIMARY KEY
                )
            ''')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS daily_stop_word (
                    word TEXT,
                    date TEXT
                )
            ''')
            
            # Загружаем стоп-слова
            c.execute("SELECT word FROM stopwords")
            self.stopwords = set(row[0] for row in c.fetchall())
            
            # Загружаем черный список продавцов
            c.execute("SELECT seller FROM blacklist_sellers")
            self.blacklist_sellers = set(row[0] for row in c.fetchall())
            
            # Загружаем ежедневное стоп-слово
            c.execute("SELECT word, date FROM daily_stop_word LIMIT 1")
            row = c.fetchone()
            
            if row:
                self.daily_stop_word = row[0]
                self.daily_stop_word_date = datetime.strptime(row[1], "%Y-%m-%d")
            
            conn.close()
            
            logger.info(f"Фильтры загружены: {len(self.stopwords)} стоп-слов, {len(self.blacklist_sellers)} продавцов в черном списке")
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке фильтров: {e}")
    
    def save_filters(self):
        """
        Сохранение фильтров в базу данных
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Очищаем таблицы перед сохранением
            c.execute("DELETE FROM stopwords")
            c.execute("DELETE FROM blacklist_sellers")
            c.execute("DELETE FROM daily_stop_word")
            
            # Сохраняем стоп-слова
            for word in self.stopwords:
                c.execute("INSERT INTO stopwords (word) VALUES (?)", (word,))
            
            # Сохраняем черный список продавцов
            for seller in self.blacklist_sellers:
                c.execute("INSERT INTO blacklist_sellers (seller) VALUES (?)", (seller,))
            
            # Сохраняем ежедневное стоп-слово
            c.execute("INSERT INTO daily_stop_word (word, date) VALUES (?, ?)",
                     (self.daily_stop_word, self.daily_stop_word_date.strftime("%Y-%m-%d")))
            
            conn.commit()
            conn.close()
            
            logger.info("Фильтры успешно сохранены")
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении фильтров: {e}")
    
    def add_stopword(self, word: str) -> bool:
        """
        Добавление стоп-слова в список
        
        Args:
            word: Слово для добавления
            
        Returns:
            True, если слово добавлено, False если оно уже было в списке
        """
        word = word.strip().lower()
        
        if not word:
            return False
            
        if word in self.stopwords:
            return False
            
        self.stopwords.add(word)
        self.save_filters()
        logger.info(f"Добавлено стоп-слово: {word}")
        return True
    
    def remove_stopword(self, word: str) -> bool:
        """
        Удаление стоп-слова из списка
        
        Args:
            word: Слово для удаления
            
        Returns:
            True, если слово удалено, False если его не было в списке
        """
        word = word.strip().lower()
        
        if not word or word not in self.stopwords:
            return False
            
        self.stopwords.remove(word)
        self.save_filters()
        logger.info(f"Удалено стоп-слово: {word}")
        return True
    
    def add_blacklist_seller(self, seller: str) -> bool:
        """
        Добавление продавца в черный список
        
        Args:
            seller: Имя продавца
            
        Returns:
            True, если продавец добавлен, False если он уже был в списке
        """
        seller = seller.strip()
        
        if not seller:
            return False
            
        if seller in self.blacklist_sellers:
            return False
            
        self.blacklist_sellers.add(seller)
        self.save_filters()
        logger.info(f"Продавец добавлен в черный список: {seller}")
        return True
    
    def remove_blacklist_seller(self, seller: str) -> bool:
        """
        Удаление продавца из черного списка
        
        Args:
            seller: Имя продавца
            
        Returns:
            True, если продавец удален, False если его не было в списке
        """
        seller = seller.strip()
        
        if not seller or seller not in self.blacklist_sellers:
            return False
            
        self.blacklist_sellers.remove(seller)
        self.save_filters()
        logger.info(f"Продавец удален из черного списка: {seller}")
        return True
    
    def generate_daily_stop_word(self) -> str:
        """
        Генерация случайного ежедневного стоп-слова
        
        Returns:
            Сгенерированное слово
        """
        # Список простых русских слов для использования в качестве стоп-слова
        words = [
            "уценка", "битый", "мятый", "скол", "трещина", "корея", "китай", "повреждение",
            "товар", "дефект", "брак", "отпечаток", "царапина", "нерабочий", "неисправный",
            "ремонт", "нерабочий", "обмен", "возврат", "сломан", "поломка", "аналог"
        ]
        
        # Выбираем случайное слово
        word = random.choice(words)
        
        # Добавляем случайный суффикс для уникальности
        # suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=3))
        
        # return f"{word}{suffix}"
        return word
    
    def update_daily_stop_word(self) -> str:
        """
        Обновление ежедневного стоп-слова, если необходимо
        
        Returns:
            Текущее ежедневное стоп-слово
        """
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Проверяем, нужно ли обновить стоп-слово
        if not self.daily_stop_word or self.daily_stop_word_date < today:
            # Генерируем новое стоп-слово
            self.daily_stop_word = self.generate_daily_stop_word()
            self.daily_stop_word_date = today
            
            # Сохраняем в базу данных
            self.save_filters()
            
            logger.info(f"Сгенерировано новое ежедневное стоп-слово: {self.daily_stop_word}")
        
        return self.daily_stop_word
    
    def get_daily_stop_word(self) -> str:
        """
        Получение текущего ежедневного стоп-слова
        
        Returns:
            Ежедневное стоп-слово
        """
        # Обновляем стоп-слово при необходимости
        self.update_daily_stop_word()
        return self.daily_stop_word
    
    def should_filter_product(self, product: Dict[str, Any]) -> bool:
        """
        Проверка, нужно ли фильтровать товар по заданным критериям
        
        Args:
            product: Словарь с данными о товаре
            
        Returns:
            True, если товар нужно отфильтровать (скрыть), False в противном случае
        """
        # Обновляем ежедневное стоп-слово
        daily_word = self.get_daily_stop_word()
        
        # Получаем название товара
        product_title = product.get("title", "").lower()
        
        # Проверяем наличие стоп-слов в названии
        for stopword in self.stopwords:
            if stopword.lower() in product_title:
                logger.debug(f"Товар отфильтрован по стоп-слову '{stopword}': {product_title}")
                return True
        
        # Проверяем наличие ежедневного стоп-слова
        if daily_word and daily_word.lower() in product_title:
            logger.debug(f"Товар отфильтрован по ежедневному стоп-слову '{daily_word}': {product_title}")
            return True
        
        # Проверяем продавца
        seller = product.get("seller", "")
        if seller and seller in self.blacklist_sellers:
            logger.debug(f"Товар отфильтрован по продавцу '{seller}': {product_title}")
            return True
        
        # Если ни один фильтр не сработал, товар проходит проверку
        return False
    
    def get_stopwords(self) -> List[str]:
        """
        Получение списка всех стоп-слов
        
        Returns:
            Список стоп-слов
        """
        return sorted(list(self.stopwords))
    
    def get_blacklist_sellers(self) -> List[str]:
        """
        Получение списка продавцов из черного списка
        
        Returns:
            Список продавцов
        """
        return sorted(list(self.blacklist_sellers))
    
    def clear_stopwords(self) -> int:
        """
        Очистка списка стоп-слов
        
        Returns:
            Количество удаленных слов
        """
        count = len(self.stopwords)
        self.stopwords.clear()
        self.save_filters()
        logger.info(f"Список стоп-слов очищен ({count} слов)")
        return count
    
    def clear_blacklist(self) -> int:
        """
        Очистка черного списка продавцов
        
        Returns:
            Количество удаленных продавцов
        """
        count = len(self.blacklist_sellers)
        self.blacklist_sellers.clear()
        self.save_filters()
        logger.info(f"Черный список продавцов очищен ({count} продавцов)")
        return count 