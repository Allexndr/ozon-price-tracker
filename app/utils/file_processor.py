from aiogram import types
from loguru import logger
from app.utils.filter_utils import FilterManager
import re
import os
import json
from typing import Dict, List, Tuple, Any, Optional
import aiofiles

async def save_document(document: types.Document, file_path: str) -> None:
    """
    Download and save document to the specified path
    
    Args:
        document: Telegram document object
        file_path: Path where to save the file
    """
    try:
        await document.download(destination=file_path)
        logger.debug(f"Document saved to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save document: {e}")
        raise

async def read_product_list(file_path: str, filter_manager: Optional[FilterManager] = None) -> List[Tuple[str, float, str, Optional[str]]]:
    """
    Read product list from file
    
    Args:
        file_path: Path to file with product list
        filter_manager: Optional filter manager for filtering products
        
    Returns:
        List of tuples (product_name, price, currency, filter_reason) where filter_reason is None for valid products
    """
    products = []
    filter_reasons = {}
    
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
        content = await file.read()
        
    # Try to parse products from structured format first
    structured_products = parse_structured_format(content)
    if structured_products:
        products = structured_products
    else:
        # Try to parse from simple format
        simple_products = parse_simple_format(content)
        if simple_products:
            products = simple_products
        else:
            # Return empty list if parsing fails
            logger.warning(f"Не удалось распознать формат файла: {file_path}")
            return []
    
    # Filter products if filter manager is provided
    if filter_manager:
        filtered_products = []
        for product_tuple in products:
            product_name, price, currency = product_tuple
            
            # Check if product should be filtered
            filter_reason = filter_manager.match_stop_word(product_name)
            
            filtered_products.append((product_name, price, currency, filter_reason))
        
        return filtered_products
    else:
        # If no filter manager, return products with None as filter reason
        return [(name, price, currency, None) for name, price, currency in products]

def parse_structured_format(content: str) -> List[Tuple[str, float, str]]:
    """
    Parse products from structured format
    Format:
    ТОВАР N
    ИМЯ: Product name
    АРТИКУЛ: Article
    ЦЕНА: Price
    ВАЛЮТА: Currency (optional)
    
    Args:
        content: File content
        
    Returns:
        List of tuples (product_name, price, currency)
    """
    products = []
    
    # Проверяем, содержит ли контент структурированный формат
    if not re.search(r'(?:ТОВАР|ИМЯ|АРТИКУЛ|ЦЕНА)', content, re.IGNORECASE):
        return []
    
    # Разделяем контент на блоки товаров
    product_blocks = re.split(r'ТОВАР\s+\d+', content)
    
    # Пропускаем первый блок, если он пустой
    if product_blocks and not product_blocks[0].strip():
        product_blocks = product_blocks[1:]
    
    for block in product_blocks:
        try:
            # Извлекаем информацию о товаре
            name_match = re.search(r'ИМЯ:?\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            article_match = re.search(r'АРТИКУЛ:?\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            price_match = re.search(r'ЦЕНА:?\s*(\d+(?:[.,]\d+)?)(?:\n|$)', block, re.IGNORECASE)
            currency_match = re.search(r'ВАЛЮТА:?\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            
            if name_match and price_match:
                name = name_match.group(1).strip()
                
                # Если указан артикул, добавляем его к имени товара
                if article_match:
                    article = article_match.group(1).strip()
                    # Добавляем артикул только если его еще нет в имени
                    if article not in name:
                        name = f"{name} {article}"
                
                price_str = price_match.group(1).replace(',', '.')
                price = float(price_str)
                
                currency = "RUB"
                if currency_match:
                    currency = currency_match.group(1).strip()
                
                products.append((name, price, currency))
        except Exception as e:
            logger.warning(f"Ошибка при парсинге блока товара: {e}")
            continue
    
    return products

def parse_simple_format(content: str) -> List[Tuple[str, float, str]]:
    """
    Parse products from simple format
    Format: Product name article, Price[, Currency]
    or: Product name, Price[, Currency]
    
    Args:
        content: File content
        
    Returns:
        List of tuples (product_name, price, currency)
    """
    products = []
    
    # Разбиваем контент на строки
    lines = content.strip().split('\n')
    
    for line in lines:
        try:
            # Пропускаем пустые строки
            if not line.strip():
                continue
            
            # Проверяем, есть ли запятая в строке
            if ',' not in line:
                logger.warning(f"Строка не содержит разделителя запятой: {line}")
                continue
            
            # Разбиваем строку на части
            parts = [part.strip() for part in line.split(',')]
            
            # Должно быть минимум 2 части (имя и цена)
            if len(parts) < 2:
                logger.warning(f"Неверный формат строки: {line}")
                continue
            
            # Первая часть - имя товара
            product_name = parts[0].strip()
            
            # Вторая часть - цена
            try:
                price_str = parts[1].replace(' ', '')
                price = float(price_str)
            except ValueError:
                logger.warning(f"Неверный формат цены: {parts[1]}")
                continue
            
            # Третья часть (если есть) - валюта
            currency = "RUB"
            if len(parts) > 2:
                currency = parts[2].strip()
            
            products.append((product_name, price, currency))
            
        except Exception as e:
            logger.warning(f"Ошибка при парсинге строки: {e}")
            continue
    
    return products

def parse_multiple_formats(text: str) -> List[Dict[str, Any]]:
    """
    Parse products from multiple formats
    
    Args:
        text: Text content
        
    Returns:
        List of product dictionaries
    """
    products = []
    
    # Try to parse structured format first
    structured_products = parse_structured_format(text)
    if structured_products:
        for name, price, currency in structured_products:
            # Извлекаем артикул, если он указан в имени
            article = ""
            article_match = re.search(r'([A-Z0-9]+-?[A-Z0-9]+)$', name, re.IGNORECASE)
            if article_match:
                article = article_match.group(1)
                # Убираем артикул из имени, если он найден в конце
                name = name.replace(article, "").strip()
            
            products.append({
                "name": name,
                "price": price,
                "currency": currency,
                "article": article
            })
    else:
        # Try to parse simple format
        simple_products = parse_simple_format(text)
        if simple_products:
            for name, price, currency in simple_products:
                # Извлекаем артикул, если он указан в имени
                article = ""
                article_match = re.search(r'([A-Z0-9]+-?[A-Z0-9]+)$', name, re.IGNORECASE)
                if article_match:
                    article = article_match.group(1)
                    # Убираем артикул из имени, если он найден в конце
                    name = name.replace(article, "").strip()
                
                products.append({
                    "name": name,
                    "price": price,
                    "currency": currency,
                    "article": article
                })
        else:
            # Try to parse compact format (named_productArticle,price)
            lines = text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Проверяем формат с запятой
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        name_article = parts[0].strip()
                        
                        try:
                            price = float(parts[1].strip().replace(' ', '').replace(',', '.'))
                        except ValueError:
                            continue
                        
                        currency = "RUB"
                        if len(parts) > 2:
                            currency = parts[2].strip()
                        
                        # Выделяем артикул из названия товара
                        # 1. Ищем стандартный артикул в формате с числами и буквами
                        article = None
                        article_pattern = r'([A-Z0-9]+-?[A-Z0-9]+)$'
                        article_match = re.search(article_pattern, name_article.strip(), re.IGNORECASE)
                        
                        if article_match:
                            article = article_match.group(1)
                            # Убираем артикул из названия товара
                            name = name_article.replace(article, "").strip()
                        else:
                            # 2. Ищем цифровой код в конце названия
                            article_pattern = r'(\d{5,})$'
                            article_match = re.search(article_pattern, name_article.strip())
                            
                            if article_match:
                                article = article_match.group(1)
                                # Убираем артикул из названия товара
                                name = name_article[:article_match.start()].strip()
                            else:
                                # 3. Если не нашли артикул, ищем последнюю группу букв и цифр
                                # Обрабатываем компактный формат, где название и артикул слиты без пробелов
                                matches = re.finditer(r'[a-zA-Z0-9]{5,}', name_article)
                                last_match = None
                                for match in matches:
                                    last_match = match
                                
                                if last_match and any(c.isdigit() for c in last_match.group(0)):
                                    article = last_match.group(0)
                                    # Извлекаем название, убирая артикул
                                    name = name_article[:last_match.start()] + name_article[last_match.end():].strip()
                                else:
                                    # Если не удалось выделить артикул, используем все как название
                                    name = name_article
                                    article = ""
                        
                        products.append({
                            "name": name,
                            "price": price,
                            "currency": currency,
                            "article": article
                        })
    
    return products

def parse_product_file(content: str) -> List[Dict[str, Any]]:
    """
    Парсит содержимое файла с товарами и возвращает список товаров
    
    Args:
        content: Содержимое файла
        
    Returns:
        Список словарей с информацией о товарах
    """
    products = []
    lines = content.strip().split('\n')
    
    # Переменные для парсинга структурированного формата
    current_product = {}
    in_product = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        # Проверка формата структурированного товара (ТОВАР N)
        if line.startswith("ТОВАР"):
            # Если был предыдущий товар, добавляем его
            if in_product and current_product.get("name") and current_product.get("article") and current_product.get("price"):
                products.append(current_product)
                
            # Начинаем новый товар
            current_product = {}
            in_product = True
            continue
            
        if in_product:
            # Парсим поля товара
            if line.startswith("ИМЯ:"):
                current_product["name"] = line[5:].strip()
            elif line.startswith("АРТИКУЛ:"):
                current_product["article"] = line[9:].strip()
            elif line.startswith("ЦЕНА:"):
                try:
                    current_product["price"] = float(line[6:].strip().replace(",", "."))
                except ValueError:
                    logger.warning(f"Неверный формат цены в строке {i+1}: {line}")
                    continue
            elif line.startswith("ВАЛЮТА:"):
                current_product["currency"] = line[8:].strip() or "RUB"
            continue
            
        # Проверяем простой формат (название артикул,цена,валюта)
        # Формат: "Название товара артикул,цена,валюта"
        match = re.match(r'^(.+?)(?:\s+)(\w+\d+\w*)[\s]*,[\s]*(\d+(?:[.,]\d+)?)(?:[\s]*,[\s]*([A-Za-z]+))?$', line)
        if match:
            name = match.group(1).strip()
            article = match.group(2).strip()
            price = float(match.group(3).replace(',', '.'))
            currency = match.group(4).strip() if match.group(4) else "RUB"
            
            products.append({
                "name": name,
                "article": article,
                "price": price,
                "currency": currency
            })
            continue
        
        # Проверяем простой формат с запятой (название,цена)
        if ',' in line:
            parts = line.split(',')
            if len(parts) >= 2:
                name_article = parts[0].strip()
                try:
                    price = float(parts[1].strip().replace(' ', '').replace(',', '.'))
                except ValueError:
                    logger.warning(f"Неверный формат цены в строке {i+1}: {parts[1]}")
                    continue
                
                currency = "RUB"
                if len(parts) > 2:
                    currency = parts[2].strip()
                
                # Извлекаем артикул из названия
                article = None
                words = name_article.split()
                
                # Ищем слово, похожее на артикул (содержит цифры)
                for word in words:
                    if any(c.isdigit() for c in word) and len(word) >= 5:
                        article = word
                        name = name_article.replace(word, '').strip()
                        break
                
                if not article and len(words) > 1:
                    # Если артикул не найден, берем последнее слово
                    article = words[-1]
                    name = ' '.join(words[:-1])
                else:
                    name = name_article
                    article = ""
                
                products.append({
                    "name": name,
                    "article": article,
                    "price": price,
                    "currency": currency
                })
    
    # Добавляем последний товар, если он в структурированном формате
    if in_product and current_product.get("name") and current_product.get("article") and current_product.get("price"):
        products.append(current_product)
    
    logger.info(f"Распознано {len(products)} товаров из файла")
    return products

class FileProcessor:
    """
    Класс для обработки файлов с товарами
    """
    
    async def read_products_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Читает товары из файла
        
        Args:
            file_path: Путь к файлу с товарами
            
        Returns:
            Список словарей с информацией о товарах
        """
        try:
            # Читаем содержимое файла
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
                content = await file.read()
            
            # Пробуем распознать формат и парсим товары
            products = parse_multiple_formats(content)
            
            if not products:
                logger.warning(f"Не удалось распознать формат файла: {file_path}")
                return []
            
            return products
            
        except Exception as e:
            logger.exception(f"Ошибка при чтении файла с товарами: {e}")
            return [] 