import os
import sys
from datetime import datetime
from loguru import logger

def setup_logger():
    """
    Setup loguru logger with file and console output
    """
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Generate log filename with current date
    log_filename = f"logs/ozon_parser_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # Configure logger: remove default handler and add custom handlers
    logger.remove()
    
    # Add console handler with INFO level
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Add file handler with DEBUG level
    logger.add(
        log_filename,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="1 day",
        retention="7 days"
    )
    
    logger.info("Logger initialized") 