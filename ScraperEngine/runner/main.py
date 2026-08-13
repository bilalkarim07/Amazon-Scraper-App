"""
Main Entry Point for Amazon Scraper

This is the single, clean entry point for running the scraper.
It provides a simple, easy-to-understand interface for common scraping tasks.

Usage:
    python runner/main.py
    
Or programmatically:
    from runner.main import run_scraping
    run_scraping(
        listings='input.csv',
        output='output.csv',
        mode='extract_process',
        keywords=['UPC', 'Brand']
    )
"""

import sys
import os
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from amazon_scraper import AmazonScraper


def run_scraping(
    listings: str = 'input.csv',
    output: str = 'output.csv',
    mode: str = 'extract_process',
    max_threads: int = 4,
    webdriver_file: Optional[str] = None,
    first_page_wait: int = 40,
    next_page_wait: float = 0.95,
    headless: bool = False,
    price_symbol: str = '$',
    base_append: str = 'https://www.amazon.com/',
    keywords: Optional[List[str]] = None
) -> str:
    """
    Run the Amazon scraper with specified configuration.
    
    Args:
        listings: Path to input CSV with product URLs
        output: Path to output CSV file
        mode: 'extract', 'process', or 'extract_process' (default)
        max_threads: Number of concurrent threads (default 4)
        webdriver_file: Path to chromedriver executable (None to use automatic Selenium Manager)
        first_page_wait: Wait time for first page (seconds)
        next_page_wait: Wait time between subsequent pages (seconds)
        headless: Run browser in headless mode
        price_symbol: Currency symbol for price extraction
        base_append: Base URL for relative links
        keywords: List of keywords to extract
    
    Returns:
        Path to output file
    """
    
    if keywords is None:
        keywords = [
            'UPC', 'Global Trade Identification Number', 'Model Number', 'Model Name',
            'Manufacturer', 'Item Dimensions D x W x H', 'Product Dimensions',
            'Item Dimensions', 'Brand', 'EAN', 'Material', 'Unit Count',
            'Number of Items', 'Recommended Uses For Product', 'Special Features',
            'Special Feature', 'Planter Form', 'Included Components', 'Material Type',
            'Product Style', 'Mounting Type'
        ]
    
    print(f"[MAIN] Initializing AmazonScraper")
    print(f"[MAIN] Listings: {listings}")
    print(f"[MAIN] Mode: {mode}")
    print(f"[MAIN] Threads: {max_threads}")
    
    scraper = AmazonScraper(
        listings=listings,
        max_threads=max_threads,
        webdriver_file=webdriver_file
    )
    
    if mode == 'extract':
        print(f"[MAIN] Running extraction only → {output}")
        return scraper.extract(
            output_file=output,
            first_page_wait=first_page_wait,
            next_page_wait=next_page_wait,
            headless=headless
        )
    
    elif mode == 'process':
        print(f"[MAIN] Running processing only")
        if not os.path.exists(output):
            raise FileNotFoundError(f"Input file not found: {output}")
        return scraper.process(
            input_file=output,
            output_file=f"processed_{output}",
            price_symbol=price_symbol,
            base_append=base_append,
            keywords=keywords
        )
    
    elif mode == 'extract_process':
        print(f"[MAIN] Running extraction + processing → {output}")
        return scraper.extract_process(
            output=output,
            price_symbol=price_symbol,
            base_append=base_append,
            keywords=keywords,
            first_page_wait=first_page_wait,
            next_page_wait=next_page_wait,
            headless=headless
        )
    
    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'extract', 'process', or 'extract_process'")


if __name__ == '__main__':
    """
    Default execution for simple testing.
    Modify the parameters below to match your requirements.
    """
    
    output_file = run_scraping(
        listings='input.csv',
        output='output.csv',
        mode='extract_process',
        max_threads=4,
        first_page_wait=40,
        next_page_wait=0.95,
        headless=False,
        keywords=[
            'UPC', 'Global Trade Identification Number', 'Model Number', 'Model Name',
            'Manufacturer', 'Item Dimensions D x W x H', 'Product Dimensions',
            'Item Dimensions', 'Brand', 'EAN', 'Material', 'Unit Count',
            'Number of Items', 'Recommended Uses For Product', 'Special Features',
            'Special Feature', 'Planter Form', 'Included Components', 'Material Type',
            'Product Style', 'Mounting Type'
        ]
    )
    
    print(f"\n[SUCCESS] Scraping completed successfully!")
    print(f"[SUCCESS] Output saved to: {output_file}")
