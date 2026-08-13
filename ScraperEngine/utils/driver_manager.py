"""
DriverManager - Centralized WebDriver creation with realistic browser identity.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from .headers import CHROME_ARGUMENTS
from .logger import logger


class DriverManager:
    """
    Manages WebDriver creation with anti-bot detection configurations.
    """
    
    def __init__(self, webdriver_path=None, headless=False):
        """
        Initialize DriverManager.
        
        Args:
            webdriver_path: Path to chromedriver executable (optional)
            headless: If True, run browser in headless mode (default: False)
        """
        self.webdriver_path = webdriver_path
        self.headless = headless
    
    def _configure_cdp(self, driver):
        """Apply CDP options to bypass basic bot detection."""
        try:
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
        except Exception as e:
            logger.debug(f"CDP anti-detection script failed (non-fatal): {e}")
        return driver

    def create_driver(self):
        """
        Create and return a configured WebDriver instance.
        
        Returns:
            Configured Selenium WebDriver
        """
        try:
            chrome_options = Options()
            
            for arg in CHROME_ARGUMENTS:
                chrome_options.add_argument(arg)
            
            if self.headless:
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--window-size=1920,1080")
            
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Try using custom chromedriver executable if provided
            if self.webdriver_path:
                try:
                    logger.info(f"Attempting to launch Chrome using: {self.webdriver_path}")
                    service = Service(self.webdriver_path)
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                    return self._configure_cdp(driver)
                except Exception as e:
                    logger.warning(
                        f"Failed to create WebDriver using {self.webdriver_path}: {e}. "
                        "Falling back to Selenium Manager (automatic driver management)..."
                    )
            
            # Fallback/Default: Use Selenium Manager to automatically locate Chrome/ChromeDriver
            logger.info("Initializing WebDriver using Selenium Manager...")
            driver = webdriver.Chrome(options=chrome_options)
            return self._configure_cdp(driver)
            
        except Exception as e:
            logger.error(f"Failed to create WebDriver: {e}")
            raise
