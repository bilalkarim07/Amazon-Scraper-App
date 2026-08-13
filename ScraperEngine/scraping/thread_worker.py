"""
ThreadWorker - Encapsulates one thread's scraping lifecycle.
Each thread owns one browser instance and writes to one CSV file.
"""

import os
import csv
import time
from models import ProductData
from utils.driver_manager import DriverManager
from utils.human_simulator import HumanSimulator
from utils.logger import logger


class ThreadWorker:
    """
    Manages a single thread's scraping workflow.
    Works with ProductData objects and converts them to CSV rows.
    """
    
    def __init__(
        self,
        thread_id,
        urls,
        webdriver_path,
        output_folder,
        columns,
        scrape_function,
        first_page_wait=150,
        next_page_wait=5,
        headless=False
    ):
        """
        Initialize ThreadWorker.
        
        Args:
            thread_id: Unique thread identifier (e.g., 1, 2, 3)
            urls: List of product URLs to scrape
            webdriver_path: Path to chromedriver executable
            output_folder: Folder to save CSV output
            columns: List of column names for CSV
            scrape_function: Function to scrape a single product (returns ProductData)
            first_page_wait: Wait time for first page load (seconds)
            next_page_wait: Wait time for subsequent pages (seconds)
            headless: Whether to run browser in headless mode
        """
        self.thread_id = thread_id
        self.urls = urls
        self.webdriver_path = webdriver_path
        self.output_folder = output_folder
        self.columns = columns
        self.scrape_function = scrape_function
        self.first_page_wait = first_page_wait
        self.next_page_wait = next_page_wait
        self.headless = headless
        self.driver = None
        self.human_simulator = None
    
    def _create_driver(self):
        """Create WebDriver instance for this thread."""
        try:
            driver_manager = DriverManager(self.webdriver_path, headless=self.headless)
            self.driver = driver_manager.create_driver()
            self.human_simulator = HumanSimulator(self.driver)
        except Exception as e:
            logger.error(f"Thread {self.thread_id} failed to create driver: {e}")
            raise
    
    def _write_fallback_row(self, writer, url: str, error: str):
        """Write a minimal CSV row when scraping fails so the URL is not lost."""
        try:
            fallback = ProductData.create_fallback(url=url, error=error)
            row = fallback.to_dict()
            for col in self.columns:
                if col not in row:
                    row[col] = "Not Mentioned"
            writer.writerow({col: row.get(col, "Not Mentioned") for col in self.columns})
        except Exception as e:
            logger.error(f"Thread {self.thread_id} could not write fallback row for {url}: {e}")
    
    def _get_output_path(self):
        """Get output CSV file path for this thread."""
        return os.path.join(self.output_folder, f"thread_{self.thread_id}.csv")
    
    def run(self):
        """
        Execute the scraping workflow for this thread.
        """
        try:
            self._create_driver()
        except Exception as e:
            logger.error(f"Thread {self.thread_id} cannot start without driver: {e}")
            return

        logger.info(f"Thread {self.thread_id} started with {len(self.urls)} URLs")
        
        output_path = self._get_output_path()
        
        try:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.columns)
                writer.writeheader()
                
                total_urls = len(self.urls)
                
                for idx, url in enumerate(self.urls, start=1):
                    logger.info(f"Thread {self.thread_id} processing {idx}/{total_urls} links")
                    
                    wait = self.first_page_wait if idx == 1 else self.next_page_wait
                    
                    try:
                        product_data = self.scrape_function(self.driver, url, wait)
                        
                        if not isinstance(product_data, ProductData):
                            raise TypeError(
                                f"scrape_function returned {type(product_data).__name__}, expected ProductData"
                            )
                        
                        data_dict = product_data.to_dict()
                        
                        if idx < total_urls and self.human_simulator:
                            try:
                                self.human_simulator.random_sleep(2, 4)
                            except Exception:
                                pass
                        
                        writer.writerow({col: data_dict.get(col, "Not Mentioned") for col in self.columns})
                        f.flush()
                        
                    except Exception as e:
                        logger.error(f"Thread {self.thread_id} error on URL {url}: {e}")
                        self._write_fallback_row(writer, url, str(e))
                        f.flush()
                        continue
            
            logger.info(f"Thread {self.thread_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Thread {self.thread_id} fatal error: {e}")
        
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info(f"Thread {self.thread_id} driver closed")
                except Exception:
                    pass
