import os
import time
import base64
from twocaptcha import TwoCaptcha
from loguru import logger

class CaptchaSolver:
    """
    Class for solving captchas using 2captcha service
    """
    
    def __init__(self):
        """
        Initialize the captcha solver with API key from environment variables
        """
        self.api_key = os.getenv("CAPTCHA_API_KEY")
        self.solver = TwoCaptcha(self.api_key) if self.api_key else None
    
    def is_available(self) -> bool:
        """
        Check if captcha solving is available
        
        Returns:
            True if API key is set, False otherwise
        """
        return self.api_key is not None and self.solver is not None
    
    async def solve_image_captcha(self, image_path: str) -> str:
        """
        Solve image captcha
        
        Args:
            image_path: Path to the captcha image
            
        Returns:
            Solved captcha text or empty string on failure
        """
        if not self.is_available():
            logger.warning("Captcha solver not available: API key not set")
            return ""
            
        try:
            logger.info("Solving image captcha...")
            result = self.solver.normal(image_path)
            
            if result and "code" in result:
                logger.info("Captcha solved successfully")
                return result["code"]
            else:
                logger.warning("Failed to solve captcha: no code in result")
                return ""
                
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            return ""
    
    async def solve_recaptcha(self, site_key: str, site_url: str) -> str:
        """
        Solve Google reCAPTCHA
        
        Args:
            site_key: reCAPTCHA site key
            site_url: URL of the page with reCAPTCHA
            
        Returns:
            g-recaptcha-response token or empty string on failure
        """
        if not self.is_available():
            logger.warning("Captcha solver not available: API key not set")
            return ""
            
        try:
            logger.info(f"Solving reCAPTCHA for {site_url}...")
            result = self.solver.recaptcha(
                sitekey=site_key,
                url=site_url
            )
            
            if result and "code" in result:
                logger.info("reCAPTCHA solved successfully")
                return result["code"]
            else:
                logger.warning("Failed to solve reCAPTCHA: no code in result")
                return ""
                
        except Exception as e:
            logger.error(f"Error solving reCAPTCHA: {e}")
            return ""
    
    async def solve_base64_captcha(self, base64_image: str) -> str:
        """
        Solve captcha from base64 image string
        
        Args:
            base64_image: Base64-encoded image data
            
        Returns:
            Solved captcha text or empty string on failure
        """
        if not self.is_available():
            logger.warning("Captcha solver not available: API key not set")
            return ""
            
        try:
            logger.info("Solving base64 captcha...")
            result = self.solver.normal(base64_image)
            
            if result and "code" in result:
                logger.info("Captcha solved successfully")
                return result["code"]
            else:
                logger.warning("Failed to solve captcha: no code in result")
                return ""
                
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            return "" 