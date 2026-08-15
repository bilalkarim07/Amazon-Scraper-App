"""
AmazonScraper - Main orchestrator class for Amazon product scraping.
"""

import os
import threading
import pandas as pd
from typing import List, Union, Optional, Callable

from scraping.thread_worker import ThreadWorker
from utils.logger import logger
from scraping.progress_reporter import ProgressReporter


class AmazonScraper:
    def __init__(
        self,
        listings: Union[str, List[str]],
        max_threads: int = 3,
        webdriver_file: str = None,
        workspace_dir: str = None,
        marketplace: str = "US",
        base_url: str = "https://www.amazon.com/",
        currency_code: str = "USD",
        currency_symbol: str = "$",
    ):
        self.listings = listings
        self.max_threads = min(max(1, max_threads), 5)
        self.webdriver_file = webdriver_file

        self.marketplace = marketplace
        self.base_url = base_url
        self.currency_code = currency_code
        self.currency_symbol = currency_symbol

        if workspace_dir:
            self.thread_folder = os.path.join(workspace_dir, "workspace")
            self._temp_extract_file = os.path.join(self.thread_folder, "raw.csv")
        else:
            self.thread_folder = "Threads"
            self._temp_extract_file = "temp_extracted.csv"

        self.columns = [
            "Product Link", "ASIN",
            "Title", "Price Box", "Ratings", "Reviews",
            "Store Name", "Store Link", "Top Highlights", "Item Details", "Description",
            "Product Images",
            "Product Information",
            "Category", "Sub Category",
            "Display Features", "Merchant",
            'Display Features 1','Comments','Main Product Image','BreadCrumb','Seller Profile','Variations', 'Availability',
            'KeyWord'
        ]

        from scraping.extractor import scrape_product
        self.scrape_function = scrape_product

        self._validate_inputs()

    def _validate_inputs(self):
        if self.webdriver_file and not os.path.exists(self.webdriver_file):
            raise FileNotFoundError(f"Webdriver not found: {self.webdriver_file}")
        if isinstance(self.listings, str):
            if not os.path.exists(self.listings):
                raise FileNotFoundError(f"Input CSV not found: {self.listings}")
        elif isinstance(self.listings, list):
            if not self.listings:
                raise ValueError("Listings cannot be an empty list")
        else:
            raise TypeError("Listings must be either a CSV file path or a list of URLs")

    def _load_urls(self) -> List[str]:
        if isinstance(self.listings, list):
            urls = []
            for item in self.listings:
                try:
                    url = str(item).strip()
                    if url:
                        urls.append(url)
                except Exception as e:
                    logger.warning(f"Skipping invalid URL entry {item!r}: {e}")
            if not urls:
                raise ValueError("No valid URLs found in listings list")
            return urls

        df = pd.read_csv(self.listings)
        if 'Product Link' not in df.columns:
            raise ValueError("CSV must contain 'Product Link' column")

        urls = []
        for value in df['Product Link'].dropna().tolist():
            try:
                url = str(value).strip()
                if url:
                    urls.append(url)
            except Exception as e:
                logger.warning(f"Skipping invalid CSV URL {value!r}: {e}")

        if not urls:
            raise ValueError("No valid product URLs found in CSV")
        return urls

    def _divide_urls(self, urls: List[str]) -> List[List[str]]:
        chunks = [urls[i::self.max_threads] for i in range(self.max_threads)]
        return [chunk for chunk in chunks if chunk]

    def _create_thread_folder(self):
        if not os.path.exists(self.thread_folder):
            os.makedirs(self.thread_folder)
            logger.info(f"Created output folder: {self.thread_folder}")

    def _merge_results(self, output_file: str):
        logger.info("Merging thread results...")
        thread_files = []
        for i in range(1, self.max_threads + 1):
            thread_file = os.path.join(self.thread_folder, f"thread_{i}.csv")
            if os.path.exists(thread_file):
                thread_files.append(thread_file)
        if not thread_files:
            logger.warning("No thread files found to merge")
            return
        dfs = []
        for thread_file in thread_files:
            try:
                dfs.append(pd.read_csv(thread_file))
            except Exception as e:
                logger.error(f"Could not read thread file {thread_file}: {e}")
        if not dfs:
            logger.warning("No readable thread files found to merge")
            return
        try:
            final_df = pd.concat(dfs, ignore_index=True)
            final_df.to_csv(output_file, index=False)
            logger.info(f"Merged {len(final_df)} products into {output_file}")
        except Exception as e:
            logger.error(f"Failed to merge thread results into {output_file}: {e}")
            raise

    def extract(
        self,
        output_file: str = 'output.csv',
        first_page_wait: int = 150,
        next_page_wait: int = 5,
        headless: bool = False,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> str:
        logger.info("=" * 60)
        logger.info("STARTING AMAZON PRODUCT EXTRACTION")
        logger.info("=" * 60)

        urls = self._load_urls()
        total_urls = len(urls)
        logger.info(f"Loaded {total_urls} product URLs")

        self._create_thread_folder()

        url_chunks = self._divide_urls(urls)
        actual_threads = len(url_chunks)
        logger.info(f"Distributing URLs across {actual_threads} threads")

        progress_reporter = ProgressReporter(total=total_urls)
        progress_reporter.emit_started()

        # --- Worker exception collection ---
        worker_exceptions = []
        exception_lock = threading.Lock()

        def record_exception(exc):
            with exception_lock:
                worker_exceptions.append(exc)

        # --- Worker result aggregation ---
        total_success = 0
        total_failed = 0
        results_lock = threading.Lock()

        def record_worker_result(success: int, failed: int):
            nonlocal total_success, total_failed
            with results_lock:
                total_success += success
                total_failed += failed

        threads = []
        for i, chunk in enumerate(url_chunks, start=1):
            worker = ThreadWorker(
                thread_id=i,
                urls=chunk,
                webdriver_path=self.webdriver_file,
                output_folder=self.thread_folder,
                columns=self.columns,
                scrape_function=self.scrape_function,
                first_page_wait=first_page_wait,
                next_page_wait=next_page_wait,
                headless=headless,
                progress_reporter=progress_reporter,
                cancel_check=cancel_check,
                base_url=self.base_url,
                exception_callback=record_exception,
                result_callback=record_worker_result,
            )
            thread = threading.Thread(target=worker.run)
            threads.append(thread)
            thread.start()

        logger.info("Waiting for all threads to complete...")
        for idx, thread in enumerate(threads):
            logger.info(f"[runner] BEFORE thread join for thread {idx+1}")
            thread.join()
            logger.info(f"[runner] AFTER thread join for thread {idx+1}")

        logger.info("All threads completed")

        # --- Check for worker exceptions ---
        if worker_exceptions:
            error_msg = f"Worker thread(s) failed: {worker_exceptions[0]}"
            logger.error(error_msg)
            progress_reporter.emit_failed(error_msg)
            raise RuntimeError(error_msg)

        # --- Emit final aggregated completed event ---
        # REPLACED: emit_final_completed with emit_completed_with_counts
        progress_reporter.emit_completed_with_counts(
            success=total_success,
            failed=total_failed,
            total=total_urls
        )

        self._merge_results(output_file)

        # --- If output_file still doesn't exist, raise an error ---
        if not os.path.exists(output_file):
            raise RuntimeError("No output file created – all workers failed or produced no data.")

        logger.info("=" * 60)
        logger.info("EXTRACTION COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)

        return output_file

    def process(
        self,
        input_file: str,
        output_file: str,
        price_symbol: str = '$',
        base_append: str = 'https://www.amazon.com/',
        keywords: List[str] = None
    ) -> str:
        logger.info("=" * 60)
        logger.info("STARTING DATA PROCESSING")
        logger.info("=" * 60)

        from processing.process import process_data
        process_data(
            input_file=input_file,
            output_file=output_file,
            price_symbol=price_symbol,
            base_append=base_append,
            keywords=keywords or []
        )

        logger.info("=" * 60)
        logger.info("PROCESSING COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)

        return output_file

    def extract_process(
        self,
        output: str = 'final_output.csv',
        price_symbol: Optional[str] = None,
        base_append: Optional[str] = None,
        keywords: List[str] = None,
        first_page_wait: int = 150,
        next_page_wait: int = 5,
        headless: bool = False,
        cancel_check: Optional[Callable[[], bool]] = None,
        marketplace: Optional[str] = None,
        base_url: Optional[str] = None,
        currency_code: Optional[str] = None,
        currency_symbol: Optional[str] = None,
    ) -> str:
        final_marketplace = marketplace if marketplace is not None else self.marketplace
        final_base_url = base_url if base_url is not None else self.base_url
        final_currency_code = currency_code if currency_code is not None else self.currency_code
        final_currency_symbol = currency_symbol if currency_symbol is not None else self.currency_symbol

        final_price_symbol = price_symbol if price_symbol is not None else final_currency_symbol
        final_base_append = base_append if base_append is not None else final_base_url

        logger.info("=" * 60)
        logger.info("STARTING COMBINED EXTRACT + PROCESS WORKFLOW")
        logger.info(f"Marketplace: {final_marketplace}, Base URL: {final_base_url}")
        logger.info(f"Currency: {final_currency_code} ({final_currency_symbol})")
        logger.info("=" * 60)

        temp_extract_file = self._temp_extract_file
        self.extract(
            output_file=temp_extract_file,
            first_page_wait=first_page_wait,
            next_page_wait=next_page_wait,
            headless=headless,
            cancel_check=cancel_check,
        )

        self.process(
            input_file=temp_extract_file,
            output_file=output,
            price_symbol=final_price_symbol,
            base_append=final_base_append,
            keywords=keywords
        )

        if os.path.exists(temp_extract_file):
            os.remove(temp_extract_file)
            logger.info(f"Cleaned up temporary file: {temp_extract_file}")

        logger.info("=" * 60)
        logger.info("COMBINED WORKFLOW COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)

        return output