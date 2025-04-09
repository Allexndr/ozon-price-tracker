"""
Ozon Parser module for extracting product data.
"""
import os
import asyncio
import time
import logging
import json
import random
import requests
from urllib.parse import quote
from typing import Dict, List, Optional, Tuple, Any, Union

# Path constants - can be modified as needed
PRODUCTS_FILE_PATH = "list.txt"  # File with products to parse
IGNORE_LIST_PATH = "ignore_list.txt"  # File with products to ignore
RESULTS_DIR = "results"  # Directory for saving results

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class OzonParser:
    """
    Parser for Ozon online store.
    Extracts product prices and details.
    """
    def __init__(self, captcha_solver=None):
        """
        Initialize the Ozon parser.
        
        Args:
            captcha_solver: Optional captcha solver instance to handle CAPTCHAs
        """
        self.session = requests.Session()
        self.captcha_solver = captcha_solver
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,ru;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://www.ozon.ru/',
            'Connection': 'keep-alive',
        }
        self.session.headers.update(self.headers)
        
        # Load ignore list
        self.ignore_list = self._load_ignore_list()

    def _load_ignore_list(self) -> List[str]:
        """
        Load list of products to ignore from file.
        
        Returns:
            List of product IDs or keywords to ignore
        """
        ignore_list = []
        try:
            if os.path.exists(IGNORE_LIST_PATH):
                with open(IGNORE_LIST_PATH, 'r', encoding='utf-8') as f:
                    ignore_list = [line.strip() for line in f if line.strip()]
                logger.info(f"Loaded {len(ignore_list)} items to ignore")
            else:
                logger.warning(f"Ignore list file not found at {IGNORE_LIST_PATH}")
        except Exception as e:
            logger.error(f"Error loading ignore list: {e}")
        
        return ignore_list
    
    def _load_products(self) -> List[str]:
        """
        Load products to parse from file.
        
        Returns:
            List of product entries in format "name article,price"
        """
        products = []
        try:
            if os.path.exists(PRODUCTS_FILE_PATH):
                with open(PRODUCTS_FILE_PATH, 'r', encoding='utf-8') as f:
                    products = [line.strip() for line in f if line.strip()]
                logger.info(f"Loaded {len(products)} products to parse")
            else:
                logger.error(f"Products file not found at {PRODUCTS_FILE_PATH}")
        except Exception as e:
            logger.error(f"Error loading products: {e}")
        
        return products
    
    def _parse_product_line(self, line: str) -> Tuple[str, str, float]:
        """
        Parse a product line from the file.
        
        Args:
            line: Line from products file in format "name article,price"
            
        Returns:
            Tuple of (name_article, article, target_price)
        """
        try:
            # Format: "Name Article,Price"
            name_article, price = line.rsplit(",", 1)
            # Get last word as article
            article = name_article.split()[-1].strip()
            target_price = float(price.strip())
            return name_article, article, target_price
        except ValueError as e:
            logger.error(f"Error parsing product line: {line} - {e}")
            raise ValueError(f"Invalid product format: {line}. Expected format: 'Name Article,Price'")
    
    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from a URL with retry and CAPTCHA handling.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string
        """
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                
                # Check for CAPTCHA
                if "captcha" in response.text.lower() or response.status_code == 403:
                    if self.captcha_solver:
                        logger.info("CAPTCHA detected, solving...")
                        solved = await self.captcha_solver.solve_captcha(response.text)
                        if solved:
                            logger.info("CAPTCHA solved, retrying...")
                            continue
                    else:
                        logger.warning("CAPTCHA detected but no solver provided")
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                
                if response.status_code == 200:
                    return response.text
                    
                logger.warning(f"HTTP error {response.status_code} for {url}")
                
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
            
            # Wait before retry
            await asyncio.sleep(retry_delay * (attempt + 1))
        
        raise Exception(f"Failed to fetch {url} after {max_retries} attempts")
    
    def _extract_price_from_html(self, html: str) -> Dict:
        """
        Extract price and product details from HTML.
        
        Args:
            html: HTML content
            
        Returns:
            Dictionary with price, title and product_url
        """
        # This is a placeholder - in a real implementation, you'd use BeautifulSoup or similar
        # to parse the HTML and extract the price, title, etc.
        # For now, we'll return dummy data
        return {
            "price": random.randint(500, 10000),
            "title": "Example Product",
            "product_url": "https://www.ozon.ru/product/example"
        }
    
    async def extract_price_by_article(self, article: str) -> Dict:
        """
        Extract price and product details for a given article.
        
        Args:
            article: Product article number
            
        Returns:
            Dictionary with price, title and product_url
        """
        try:
            url = f"https://www.ozon.ru/search/?text={quote(article)}"
            html = await self._fetch_html(url)
            
            # Extract product data from HTML
            result = self._extract_price_from_html(html)
            result["product_url"] = f"https://www.ozon.ru/product/{article}"
            
            return result
        except Exception as e:
            logger.error(f"Error extracting price for article {article}: {e}")
            raise
    
    def _should_ignore_product(self, name_article: str, article: str) -> bool:
        """
        Check if a product should be ignored based on ignore list.
        
        Args:
            name_article: Product name and article
            article: Product article number
            
        Returns:
            True if product should be ignored, False otherwise
        """
        for item in self.ignore_list:
            if item in name_article or item == article:
                return True
        return False
    
    async def process_single_product(self, name_article: str, article: str, target_price: float) -> Dict:
        """
        Process a single product and check if it meets price criteria.
        
        Args:
            name_article: Product name and article
            article: Product article number
            target_price: Target price to compare against
            
        Returns:
            Dictionary with product details and comparison results
        """
        # Check if product should be ignored
        if self._should_ignore_product(name_article, article):
            logger.info(f"Ignoring product: {name_article}")
            return {
                "name": name_article,
                "article": article,
                "target_price": target_price,
                "ignored": True
            }
        
        # Get current price and details
        result = await self.extract_price_by_article(article)
        current_price = result["price"]
        
        # Calculate price difference
        price_diff = abs(current_price - target_price)
        price_diff_percent = (price_diff / target_price * 100) if target_price > 0 else 0
        
        return {
            "name": name_article,
            "article": article,
            "target_price": target_price,
            "current_price": current_price,
            "title": result["title"],
            "product_url": result["product_url"],
            "is_cheaper": current_price <= target_price,
            "price_diff": price_diff,
            "price_diff_percent": price_diff_percent,
            "ignored": False
        }
    
    def product_found_callback(self, result: Dict):
        """
        Callback function called when a product meeting criteria is found.
        Override this method to implement custom behavior.
        
        Args:
            result: Dictionary with product details
        """
        # Default implementation: print to console
        if result.get("ignored", False):
            return
            
        if result.get("is_cheaper", False):
            print("\n" + "="*50)
            print(f"📦 {result['title']}")
            print(f"📌 Артикул: {result['article']}")
            print(f"💰 Целевая цена: {result['target_price']} руб.")
            print(f"💵 Актуальная цена: {result['current_price']} руб.")
            print(f"✅ Цена ниже целевой!")
            print(f"📊 Разница: {result['price_diff']} руб. ({result['price_diff_percent']:.1f}%)")
            print(f"🔗 Товар: {result['product_url']}")
            print("="*50 + "\n")
    
    async def start_parse(self):
        """
        Start parsing products from the products file.
        """
        start_time = time.time()
        logger.info("Starting parser")
        
        try:
            # Load products
            products = self._load_products()
            
            if not products:
                logger.warning("No products found to parse")
                return
                
            total_products = len(products)
            logger.info(f"Found {total_products} products to parse")
            
            # Process each product
            processed = 0
            successful = 0
            failed = 0
            ignored = 0
            found = 0
            
            for product in products:
                processed += 1
                try:
                    # Parse product line
                    name_article, article, target_price = self._parse_product_line(product)
                    
                    # Process product
                    result = await self.process_single_product(name_article, article, target_price)
                    
                    if result.get("ignored", False):
                        ignored += 1
                        continue
                    
                    # Check if product meets criteria and call callback
                    if result.get("is_cheaper", False):
                        found += 1
                        self.product_found_callback(result)
                    
                    successful += 1
                    
                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing product: {product} - {e}")
            
            # Print final statistics
            duration = int(time.time() - start_time)
            print("\n📊 Итоговая статистика:")
            print(f"- Всего товаров: {total_products}")
            print(f"- Успешно обработано: {successful}")
            print(f"- Найдено товаров по цене: {found}")
            print(f"- Игнорировано: {ignored}")
            print(f"- Ошибок: {failed}")
            print(f"- Время выполнения: {duration // 60}м {duration % 60}с")
            
        except Exception as e:
            logger.error(f"Error in parser: {e}")
        finally:
            self.close()
    
    def close(self):
        """Close the session"""
        if hasattr(self, 'session'):
            self.session.close()