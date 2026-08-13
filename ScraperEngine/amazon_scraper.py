"""
AmazonScraper - Main orchestrator class for Amazon product scraping.

This class provides a clean OOP interface for scraping Amazon products
using multithreading and human-like behavior simulation.

Usage:
    scraper = AmazonScraper(
        listings='input.csv',
        max_threads=3,
        webdriver_file='chromedriver.exe'
    )
    
    # Extract only
    scraper.extract(output_file='output.csv', headless=False)
    
    # Process only
    scraper.process(
        input_file='output.csv',
        output_file='result.csv',
        price_symbol='$'
    )
    
    # Extract + Process
    scraper.extract_process(
        output='final.csv',
        price_symbol='$',
        keywords=['UPC', 'Weight'],
        headless=False
    )
"""

import os
import threading
import pandas as pd
from typing import List, Union

from scraping.thread_worker import ThreadWorker
from utils.logger import logger


class AmazonScraper:
    """
    Main orchestrator for Amazon product scraping.
    
    Coordinates threading, driver management, and data processing
    without exposing internal implementation details.
    """
    
    def __init__(
        self,
        listings: Union[str, List[str]],
        max_threads: int = 3,
        webdriver_file: str = None,
        workspace_dir: str = None
    ):
        """
        Initialize AmazonScraper.
        
        Args:
            listings: Either a CSV file path or a list of product URLs
            max_threads: Number of concurrent threads (default 3, max 5)
            webdriver_file: Path to chromedriver executable (optional)
            workspace_dir: Optional job-specific directory for output isolation.
                           When supplied, thread CSVs go to <workspace_dir>/workspace/
                           and temp files go to <workspace_dir>/raw.csv.
                           When None, legacy "Threads/" and "temp_extracted.csv" are used.
        """
        self.listings = listings
        self.max_threads = min(max(1, max_threads), 5)  # Cap at 5
        self.webdriver_file = webdriver_file

        # Job-scoped isolation: if workspace_dir is provided, all output goes
        # inside that directory. Otherwise fall back to the original global paths.
        if workspace_dir:
            self.thread_folder = os.path.join(workspace_dir, "workspace")
            self._temp_extract_file = os.path.join(workspace_dir, "raw.csv")
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
        
        # Import scrape_product function from scraping module
        from scraping.extractor import scrape_product
        self.scrape_function = scrape_product
        
        # Validate inputs
        self._validate_inputs()
    
    def _validate_inputs(self):
        """Validate constructor inputs."""
        # Check if webdriver exists (only if provided)
        if self.webdriver_file and not os.path.exists(self.webdriver_file):
            raise FileNotFoundError(f"Webdriver not found: {self.webdriver_file}")
        
        # Validate listings
        if isinstance(self.listings, str):
            if not os.path.exists(self.listings):
                raise FileNotFoundError(f"Input CSV not found: {self.listings}")
        elif isinstance(self.listings, list):
            if not self.listings:
                raise ValueError("Listings cannot be an empty list")
        else:
            raise TypeError("Listings must be either a CSV file path or a list of URLs")
    
    def _load_urls(self) -> List[str]:
        """
        Load product URLs from listings.
        
        Returns:
            List of product URLs
        """
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
        """
        Divide URLs across threads.
        
        Args:
            urls: List of all product URLs
        
        Returns:
            List of URL chunks, one per thread
        """
        # Divide URLs round-robin style
        chunks = [urls[i::self.max_threads] for i in range(self.max_threads)]
        
        # Filter out empty chunks
        return [chunk for chunk in chunks if chunk]
    
    def _create_thread_folder(self):
        """Create Threads folder if it doesn't exist."""
        if not os.path.exists(self.thread_folder):
            os.makedirs(self.thread_folder)
            logger.info(f"Created output folder: {self.thread_folder}")
    
    def _merge_results(self, output_file: str):
        """
        Merge all thread CSV files into a single output file.
        
        Args:
            output_file: Path to final merged CSV
        """
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
        headless: bool = False
    ) -> str:
        """
        Extract product data from Amazon using multithreading.
        
        Args:
            output_file: Path to save merged output CSV
            first_page_wait: Wait time for first page load (seconds)
            next_page_wait: Wait time for subsequent pages (seconds)
            headless: Run browser in headless mode (default: False)
        
        Returns:
            Path to output file
        """
        logger.info("=" * 60)
        logger.info("STARTING AMAZON PRODUCT EXTRACTION")
        logger.info("=" * 60)
        
        # Load URLs
        urls = self._load_urls()
        logger.info(f"Loaded {len(urls)} product URLs")
        
        # Create thread folder
        self._create_thread_folder()
        
        # Divide URLs
        url_chunks = self._divide_urls(urls)
        actual_threads = len(url_chunks)
        logger.info(f"Distributing URLs across {actual_threads} threads")
        
        # Create thread workers
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
                headless=headless
            )
            
            thread = threading.Thread(target=worker.run)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        logger.info("Waiting for all threads to complete...")
        for thread in threads:
            thread.join()
        
        logger.info("All threads completed")
        
        # Merge results
        self._merge_results(output_file)
        
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
        """
        Process extracted data (clean, normalize, enrich).
        
        Args:
            input_file: Path to raw extracted CSV
            output_file: Path to save processed CSV
            price_symbol: Currency symbol for price extraction
            base_append: Base URL to prepend to relative links
            keywords: List of keywords to extract from product info
        
        Returns:
            Path to processed output file
        """
        logger.info("=" * 60)
        logger.info("STARTING DATA PROCESSING")
        logger.info("=" * 60)
        
        # Import process_data function
        from processing.process import process_data
        
        # Process the data
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
        price_symbol: str = '$',
        base_append: str = 'https://www.amazon.com/',
        keywords: List[str] = None,
        first_page_wait: int = 150,
        next_page_wait: int = 5,
        headless: bool = False
    ) -> str:
        """
        Combined workflow: extract then process.
        
        Args:
            output: Path to final processed output CSV
            price_symbol: Currency symbol for price extraction
            base_append: Base URL to prepend to relative links
            keywords: List of keywords to extract from product info
            first_page_wait: Wait time for first page load (seconds)
            next_page_wait: Wait time for subsequent pages (seconds)
            headless: Run browser in headless mode (default: False)
        
        Returns:
            Path to final processed output file
        """
        logger.info("=" * 60)
        logger.info("STARTING COMBINED EXTRACT + PROCESS WORKFLOW")
        logger.info("=" * 60)
        
        # Extract — use job-scoped temp file if workspace_dir was set
        temp_extract_file = self._temp_extract_file
        self.extract(
            output_file=temp_extract_file,
            first_page_wait=first_page_wait,
            next_page_wait=next_page_wait,
            headless=headless
        )
        
        # Process
        self.process(
            input_file=temp_extract_file,
            output_file=output,
            price_symbol=price_symbol,
            base_append=base_append,
            keywords=keywords
        )
        
        # Cleanup temp file
        if os.path.exists(temp_extract_file):
            os.remove(temp_extract_file)
            logger.info(f"Cleaned up temporary file: {temp_extract_file}")
        
        logger.info("=" * 60)
        logger.info("COMBINED WORKFLOW COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
        return output
