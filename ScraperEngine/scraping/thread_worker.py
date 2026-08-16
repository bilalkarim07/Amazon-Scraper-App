"""
ThreadWorker - Encapsulates one thread's scraping lifecycle.
"""

import os
import csv
import time
import json
from typing import Optional, Callable
from selenium.common.exceptions import TimeoutException

from models import ProductData
from utils.driver_manager import DriverManager
from utils.human_simulator import HumanSimulator
from utils.logger import logger
from .progress_reporter import ProgressReporter


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
        base_url: str = "https://www.amazon.com/",
        exception_callback: Optional[Callable[[Exception], None]] = None,
        result_callback: Optional[Callable[[int, int, int], None]] = None,  # (success, timeout, failure)
        url_timeout: int = 60,
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
        self.base_url = base_url
        self.exception_callback = exception_callback
        self.result_callback = result_callback
        self.url_timeout = url_timeout

    def _create_driver(self):
        try:
            driver_manager = DriverManager(self.webdriver_path, headless=self.headless)
            self.driver = driver_manager.create_driver()
            self.driver.set_page_load_timeout(self.url_timeout)
            self.driver.set_script_timeout(self.url_timeout)
            self.human_simulator = HumanSimulator(self.driver)
            return self.driver
        except Exception as e:
            logger.error(f"Thread {self.thread_id} failed to create driver: {e}")
            raise

    def _recover_driver_if_needed(self):
        """
        Check if the current driver is still usable. If not, quit and create a new one.
        This is called after a timeout to ensure the thread can continue with the next URL.
        """
        try:
            _ = self.driver.current_url
            logger.info(f"[Thread {self.thread_id}] Driver is still healthy after timeout.")
        except Exception:
            logger.warning(f"[Thread {self.thread_id}] Driver appears stuck; recovering.")
            try:
                self.driver.quit()
            except Exception:
                pass
            self._create_driver()
            logger.info(f"[Thread {self.thread_id}] Driver recovered successfully.")

    def _write_fallback_row(self, writer, url: str, error: str, is_timeout: bool = False):
        """Write a fallback row, optionally marking it as a timeout."""
        try:
            fallback = ProductData.create_fallback(url=url, error=error, is_timeout=is_timeout)
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
        success_count = 0
        failure_count = 0
        timeout_count = 0
        total_urls = len(self.urls)

        try:
            self._create_driver()

            logger.info(f"Thread {self.thread_id} visiting homepage: {self.base_url}")
            self.driver.get(self.base_url)
            time.sleep(self.first_page_wait)
            logger.info(f"Thread {self.thread_id} homepage wait complete")

            output_path = self._get_output_path()
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.columns)
                writer.writeheader()

                for idx, url in enumerate(self.urls, start=1):
                    if self.cancel_check and self.cancel_check():
                        logger.info(f"Thread {self.thread_id} cancelled before URL {idx}.")
                        break

                    logger.info(f"Thread {self.thread_id} processing {idx}/{total_urls} links")
                    wait = self.next_page_wait
                    start_time = time.time()

                    try:
                        product_data = self.scrape_function(
                            self.driver,
                            url,
                            wait,
                            cancel_check=self.cancel_check,
                            url_timeout=self.url_timeout
                        )

                        elapsed = time.time() - start_time
                        if elapsed >= self.url_timeout:
                            raise TimeoutException(
                                f"URL processing exceeded {self.url_timeout}s (took {elapsed:.2f}s)"
                            )

                        is_fallback = getattr(product_data, 'is_fallback', False)
                        if is_fallback:
                            failure_count += 1
                        else:
                            success_count += 1

                        data_dict = product_data.to_dict()
                        row_data = {col: data_dict.get(col, "Not Mentioned") for col in self.columns}
                        writer.writerow(row_data)
                        f.flush()
                        logger.info(f"[Thread {self.thread_id}] URL completed in {elapsed:.2f}s")

                    except TimeoutException as e:
                        elapsed = time.time() - start_time
                        logger.warning(
                            f"[Thread {self.thread_id}] URL timeout after {elapsed:.2f}s: {url}"
                        )
                        timeout_count += 1
                        self._write_fallback_row(writer, url, f"Timeout after {self.url_timeout}s", is_timeout=True)
                        f.flush()
                        self._recover_driver_if_needed()
                        # Continue to next URL

                    except Exception as e:
                        logger.error(f"Thread {self.thread_id} error on URL {url}: {e}")
                        self._write_fallback_row(writer, url, str(e), is_timeout=False)
                        f.flush()
                        failure_count += 1

                    finally:
                        if self.progress_reporter:
                            self.progress_reporter.increment()

            logger.info(
                f"Thread {self.thread_id} completed. "
                f"Success: {success_count}, Timeout: {timeout_count}, Failed: {failure_count}"
            )

            # --- Call the result callback with three separate counts ---
            if self.result_callback:
                self.result_callback(success_count, timeout_count, failure_count)

            if self.progress_reporter:
                self.progress_reporter.emit_completed_with_counts(
                    success=success_count,
                    failed=failure_count + timeout_count,  # legacy: treat timeouts as failures
                    total=total_urls
                )

        except Exception as e:
            logger.error(f"Thread {self.thread_id} fatal error: {e}")
            if self.exception_callback:
                self.exception_callback(e)
            raise
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info(f"Thread {self.thread_id} driver closed")
                except Exception as e:
                    logger.warning(f"Thread {self.thread_id} error closing driver: {e}")