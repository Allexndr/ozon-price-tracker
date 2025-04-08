import os
import asyncio
import logging
import time
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class OzonParser:
    async def extract_price_by_article(self, article: str) -> Dict:
        """
        Extract price and other info for a given article
        Returns dict with price, title and product_url
        """
        try:
            # Simulate API call for now
            await asyncio.sleep(1)
            return {
                "price": 1000,  # Example price
                "title": f"Product {article}",
                "product_url": f"https://www.ozon.ru/product/{article}"
            }
        except Exception as e:
            logger.error(f"Error extracting price for article {article}: {e}")
            raise

    async def parse_product_line(self, line: str) -> Tuple[str, str, float]:
        """Parse a single product line from the file"""
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

    async def process_single_product(self, name_article: str, article: str, target_price: float) -> Dict:
        """Process a single product and return result"""
        result = await self.extract_price_by_article(article)
        current_price = result["price"]
        
        price_diff = abs(current_price - target_price)
        price_diff_percent = (price_diff / target_price * 100)
        
        return {
            "name": name_article,
            "article": article,
            "target_price": target_price,
            "current_price": current_price,
            "title": result["title"],
            "product_url": result["product_url"],
            "is_cheaper": current_price <= target_price,
            "price_diff": price_diff,
            "price_diff_percent": price_diff_percent
        }

    def send_notification(self, result: Dict):
        """Print product information to console"""
        print("\n" + "="*50)
        print(f"📦 {result['title']}")
        print(f"📌 Артикул: {result['article']}")
        print(f"💰 Целевая цена: {result['target_price']} руб.")
        print(f"💵 Актуальная цена: {result['current_price']} руб.")
        
        if result['is_cheaper']:
            print(f"✅ Цена ниже целевой!")
        else:
            print(f"❌ Цена выше целевой")
            
        print(f"📊 Разница: {result['price_diff']} руб. ({result['price_diff_percent']:.1f}%)")
        print(f"🔗 Товар: {result['product_url']}")
        print("="*50 + "\n")

    async def start_parse(self):
        """
        Start parsing products from list.txt file
        """
        start_time = time.time()
        logger.info("Starting parser")
        
        try:
            # Read products from file
            file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'list.txt')
            logger.info(f"Reading products from: {file_path}")
            
            if not os.path.exists(file_path):
                logger.error(f"Products file not found: {file_path}")
                return
            
            with open(file_path, 'r', encoding='utf-8') as file:
                products = [line.strip() for line in file.readlines() if line.strip()]
            
            if not products:
                logger.warning("No products found in file")
                return
                
            total_products = len(products)
            logger.info(f"Found {total_products} products to parse")
            
            # Process each product
            processed = 0
            successful = 0
            failed = 0
            
            for product in products:
                processed += 1
                try:
                    # Parse product line
                    name_article, article, target_price = await self.parse_product_line(product)
                    
                    # Process product
                    result = await self.process_single_product(name_article, article, target_price)
                    
                    # Send notification
                    self.send_notification(result)
                    
                    successful += 1
                    
                except Exception as e:
                    failed += 1
                    logger.error(f"Error processing product: {product} - {e}")
            
            # Print final statistics
            duration = int(time.time() - start_time)
            print("\n📊 Итоговая статистика:")
            print(f"- Всего товаров: {total_products}")
            print(f"- Успешно обработано: {successful}")
            print(f"- Ошибок: {failed}")
            print(f"- Время выполнения: {duration // 60}м {duration % 60}с")
            
        except Exception as e:
            logger.error(f"Error in parser: {e}")