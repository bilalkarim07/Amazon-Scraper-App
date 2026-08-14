"""
ThreadWorker - Encapsulates one thread's scraping lifecycle.
"""

import os
import csv
import time
from models import ProductData
from utils.driver_manager import DriverManager
from utils.human_simulator import HumanSimulator
from utils.logger import logger
from .progress_reporter import ProgressReporter
from typing import Optional, Callable


class ThreadWorker:
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
        headless=False,
        progress_reporter: Optional[ProgressReporter] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        base_url: str = "https://www.amazon.com/",   # NEW
    ):
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
        self.progress_reporter = progress_reporter or ProgressReporter()
        self.cancel_check = cancel_check

    def _create_driver(self):
        try:
            driver_manager = DriverManager(self.webdriver_path, headless=self.headless)
            self.driver = driver_manager.create_driver()
            self.human_simulator = HumanSimulator(self.driver)
            return self.driver   # <-- ADD THIS LINE
        except Exception as e:
            logger.error(f"Thread {self.thread_id} failed to create driver: {e}")
            raise

    def _write_fallback_row(self, writer, url: str, error: str):
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
        return os.path.join(self.output_folder, f"thread_{self.thread_id}.csv")


    def run(self):
        try:
            self._create_driver()   # driver is created and stored in self.driver

            logger.info(f"Thread {self.thread_id} visiting homepage: {self.base_url}")
            self.driver.get(self.base_url)
            time.sleep(self.first_page_wait)
            logger.info(f"Thread {self.thread_id} homepage wait complete")

            output_path = self._get_output_path()
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.columns)
                writer.writeheader()

                total_urls = len(self.urls)
                for idx, url in enumerate(self.urls, start=1):
                    if self.cancel_check and self.cancel_check():
                        logger.info(f"Thread {self.thread_id} cancelled before URL {idx}.")
                        break

                    logger.info(f"Thread {self.thread_id} processing {idx}/{total_urls} links")
                    wait = self.next_page_wait   # product pages use next_page_wait

                    try:
                        product_data = self.scrape_function(
                            self.driver,
                            url,
                            wait,
                            cancel_check=self.cancel_check
                        )
                        if not isinstance(product_data, ProductData):
                            raise TypeError(f"Expected ProductData, got {type(product_data).__name__}")

                        data_dict = product_data.to_dict()
                        row_data = {col: data_dict.get(col, "Not Mentioned") for col in self.columns}
                        writer.writerow(row_data)
                        f.flush()

                    except Exception as e:
                        logger.error(f"Thread {self.thread_id} error on URL {url}: {e}")
                        self._write_fallback_row(writer, url, str(e))
                        f.flush()

                    finally:
                        if self.progress_reporter:
                            self.progress_reporter.increment()

                logger.info(f"Thread {self.thread_id} completed successfully")

        except Exception as e:
            logger.error(f"Thread {self.thread_id} fatal error: {e}")
            raise
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info(f"Thread {self.thread_id} driver closed")
                except Exception as e:
                    logger.warning(f"Thread {self.thread_id} error closing driver: {e}")