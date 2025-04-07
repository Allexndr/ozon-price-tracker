import os
import random
import requests
from bs4 import BeautifulSoup
from loguru import logger
from typing import List, Dict, Optional, Union

class ProxyHandler:
    """
    Класс для управления прокси-серверами
    """
    
    def __init__(self):
        """
        Инициализация обработчика прокси
        """
        self.proxy_list = []
        self.working_proxies = []
        self.proxy_list_url = os.getenv("PROXY_LIST_URL", "https://free-proxy-list.net/")
        self.use_proxy = os.getenv("USE_PROXY", "false").lower() == "true"
        
        if self.use_proxy:
            self.load_proxies()
        
        # Захардкоженные прокси для тестов и резервного использования
        self.hardcoded_proxies = [
            # Бесплатные прокси из списка
            "http://31.186.241.6:8888",
            "http://47.243.242.90:808",
            "http://198.52.115.114:3128",
            "http://23.132.185.101:53128",
            "http://142.132.226.173:8080",
            "http://162.214.165.203:80",
            "http://162.223.94.163:80",
            "http://195.154.255.194:8000",
            # SOCKS прокси
            "socks5://72.221.232.152:4145",
            "socks5://47.88.5.58:1080"
        ]
    
    def load_proxies(self) -> bool:
        """
        Загрузка списка прокси-серверов из указанного URL
        
        Returns:
            True, если загрузка успешна, False в противном случае
        """
        if not self.use_proxy:
            return False
            
        try:
            logger.info(f"Загрузка списка прокси с {self.proxy_list_url}")
            response = requests.get(self.proxy_list_url, timeout=10)
            
            if response.status_code == 200:
                # Простой парсинг HTML для извлечения прокси
                # Этот метод зависит от структуры страницы и может потребоваться изменить
                import re
                proxies = re.findall(r'(\d+\.\d+\.\d+\.\d+)\s*</td>\s*<td>(\d+)', response.text)
                
                if proxies:
                    self.proxy_list = [f"{ip}:{port}" for ip, port in proxies]
                    logger.info(f"Загружено {len(self.proxy_list)} прокси-серверов")
                    return True
                else:
                    logger.warning("Не удалось извлечь прокси из ответа")
            else:
                logger.warning(f"Ошибка при загрузке прокси: {response.status_code}")
                
            return False
        
        except Exception as e:
            logger.error(f"Ошибка при загрузке прокси: {e}")
            return False
    
    def get_random_proxy(self) -> Optional[str]:
        """
        Получение случайного прокси из списка
        
        Returns:
            Строка с прокси в формате "ip:port" или None, если прокси недоступны
        """
        if not self.use_proxy or not self.proxy_list:
            return None
            
        # Предпочитаем рабочие прокси, если они есть
        if self.working_proxies:
            return random.choice(self.working_proxies)
            
        # Иначе выбираем случайный прокси из общего списка
        return random.choice(self.proxy_list)
    
    def mark_proxy_as_working(self, proxy: str):
        """
        Отметка прокси как рабочего
        
        Args:
            proxy: Строка с прокси в формате "ip:port"
        """
        if proxy and proxy not in self.working_proxies:
            self.working_proxies.append(proxy)
            logger.debug(f"Прокси {proxy} отмечен как рабочий")
    
    def mark_proxy_as_failed(self, proxy: str):
        """
        Отметка прокси как неработающего
        
        Args:
            proxy: Строка с прокси в формате "ip:port"
        """
        if proxy:
            # Удаляем из списка рабочих прокси
            if proxy in self.working_proxies:
                self.working_proxies.remove(proxy)
                
            # Удаляем из общего списка прокси
            if proxy in self.proxy_list:
                self.proxy_list.remove(proxy)
                
            logger.debug(f"Прокси {proxy} отмечен как неработающий")
    
    def test_proxy(self, proxy: str) -> bool:
        """
        Проверка работоспособности прокси
        
        Args:
            proxy: Строка с прокси в формате "ip:port"
            
        Returns:
            True, если прокси работает, False в противном случае
        """
        if not proxy:
            return False
            
        try:
            proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }
            
            response = requests.get("https://www.ozon.ru", 
                proxies=proxies, 
                timeout=5,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            )
            
            if response.status_code == 200:
                self.mark_proxy_as_working(proxy)
                return True
            else:
                self.mark_proxy_as_failed(proxy)
                return False
                
        except Exception as e:
            self.mark_proxy_as_failed(proxy)
            logger.debug(f"Ошибка при проверке прокси {proxy}: {e}")
            return False
    
    def find_working_proxy(self, max_attempts: int = 5) -> Optional[str]:
        """
        Поиск рабочего прокси путем проверки нескольких случайных прокси
        
        Args:
            max_attempts: Максимальное количество попыток
            
        Returns:
            Строка с рабочим прокси или None, если не найдено
        """
        if not self.use_proxy or not self.proxy_list:
            return None
            
        for _ in range(max_attempts):
            proxy = self.get_random_proxy()
            if self.test_proxy(proxy):
                return proxy
                
        # Если все попытки не удались, обновляем список прокси
        self.load_proxies()
        
        # Еще одна попытка с обновленным списком
        proxy = self.get_random_proxy()
        if proxy and self.test_proxy(proxy):
            return proxy
            
        return None
    
    def is_valid_ip(self, ip: str) -> bool:
        """
        Check if the IP address is valid
        
        Args:
            ip: IP address to check
            
        Returns:
            True if valid, False otherwise
        """
        parts = ip.split(".")
        if len(parts) != 4:
            return False
            
        for part in parts:
            try:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            except ValueError:
                return False
                
        return True
    
    def get_random_proxy_dict(self) -> Optional[Dict[str, str]]:
        """
        Get a random proxy from the list
        
        Returns:
            Random proxy dict or None if no proxies available
        """
        if not self.use_proxy or not self.proxy_list:
            return None
            
        # Предпочитаем рабочие прокси, если они есть
        if self.working_proxies:
            proxy = random.choice(self.working_proxies)
            parts = proxy.split(":")
            if len(parts) == 2:
                return {
                    "ip": parts[0],
                    "port": parts[1],
                    "url": proxy
                }
            
        # Иначе выбираем случайный прокси из общего списка
        proxy = random.choice(self.proxy_list)
        parts = proxy.split(":")
        if len(parts) == 2:
            return {
                "ip": parts[0],
                "port": parts[1],
                "url": f"http://{parts[0]}:{parts[1]}"
            }
            
        return None
    
    async def get_working_proxy(self) -> Optional[Dict[str, str]]:
        """
        Get a working proxy
        
        Returns:
            Working proxy dict or None if no working proxy found
        """
        # Fetch proxies if none available
        if not self.use_proxy or not self.proxy_list:
            await self.load_proxies()
            
        # Try a few random proxies
        for _ in range(min(5, len(self.proxy_list))):
            proxy = self.get_random_proxy()
            if proxy and self.test_proxy(proxy):
                logger.info(f"Found working proxy: {proxy}")
                return self.get_random_proxy_dict()
                
        logger.warning("No working proxy found")
        return None
        
    def get_proxy(self) -> Optional[str]:
        """
        Получить прокси в формате для undetected-chromedriver
        
        Returns:
            Строка с прокси в формате 'http://ip:port' или 'socks5://ip:port' или None
        """
        # Для простоты тестирования используем захардкоженные прокси
        if self.hardcoded_proxies:
            proxy = random.choice(self.hardcoded_proxies)
            logger.info(f"Используем захардкоженный прокси: {proxy}")
            return proxy
            
        # Если есть список прокси, берём случайный
        if self.proxy_list:
            proxy = self.get_random_proxy()
            if proxy:
                proxy_url = f"http://{proxy}"
                logger.info(f"Используем прокси из списка: {proxy_url}")
                return proxy_url
                
        logger.warning("Прокси не найден")
        return None 