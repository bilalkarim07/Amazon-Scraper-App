"""
HumanSimulator - Simulates human browsing behavior to reduce bot detection.
"""

import time
import random
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By


class HumanSimulator:
    """
    Simulates realistic human browsing patterns.
    """
    
    def __init__(self, driver):
        """
        Initialize HumanSimulator.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
    
    def random_sleep(self, min_seconds=2, max_seconds=5):
        """
        Sleep for a random duration.
        
        Args:
            min_seconds: Minimum sleep time
            max_seconds: Maximum sleep time
        """
        duration = random.uniform(min_seconds, max_seconds)
        time.sleep(duration)
    
    def random_mouse_movement(self):
        """
        Perform random mouse movements on the page.
        """
        try:
            actions = ActionChains(self.driver)
            
            # Get window size
            window_size = self.driver.get_window_size()
            width = window_size['width']
            height = window_size['height']
            
            # Move to random positions
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, width - 100)
                y = random.randint(100, height - 100)
                actions.move_by_offset(x - width // 2, y - height // 2)
            
            actions.perform()
        except Exception:
            pass  # Fail silently if mouse movement fails
    
    def random_scroll(self):
        """
        Scroll randomly up and down the page.
        """
        try:
            # Scroll down
            scroll_distance = random.randint(300, 800)
            self.driver.execute_script(f"window.scrollBy(0, {scroll_distance});")
            time.sleep(random.uniform(0.5, 1.5))
            
            # Sometimes scroll back up a bit
            if random.random() > 0.5:
                scroll_back = random.randint(100, 300)
                self.driver.execute_script(f"window.scrollBy(0, -{scroll_back});")
                time.sleep(random.uniform(0.3, 0.8))
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(0.5, 1.0))
        except Exception:
            pass
    
    def click_product_title(self):
        """
        Optionally click the product title (sometimes helps with dynamic loading).
        """
        try:
            title = self.driver.find_element(By.ID, "productTitle")
            if title and random.random() > 0.7:  # 30% chance to click
                title.click()
                time.sleep(random.uniform(0.5, 1.0))
        except Exception:
            pass
    
    def simulate_human_behavior(self, include_scroll=True, include_mouse=False):
        """
        Execute a combination of human-like behaviors.
        
        Args:
            include_scroll: Whether to include scrolling behavior
            include_mouse: Whether to include mouse movements
        """
        behaviors = []
        
        if include_scroll:
            behaviors.append(self.random_scroll)
        
        if include_mouse:
            behaviors.append(self.random_mouse_movement)
        
        # Execute random behaviors
        for behavior in behaviors:
            if random.random() > 0.3:  # 70% chance to execute each
                behavior()
        
        # Always end with a random sleep
        self.random_sleep(2, 4)
