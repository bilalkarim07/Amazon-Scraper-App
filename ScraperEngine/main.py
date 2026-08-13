"""
Amazon Scraper - Main Usage Examples

This file demonstrates the clean OOP API for the Amazon scraper.
For a cleaner entry point, see: runner/main.py

Usage:
    python main.py (uses old API - simpler but less flexible)
    python runner/main.py (uses new runner - more flexible)
"""

from runner import run_scraping
import time


if __name__ == '__main__':
    t1 = time.time()
    
    # Run scraper with sensible defaults
    output_file = run_scraping(
        listings='amazon.csv',
        output='output.csv',
        mode='extract_process',
        max_threads=4,
        first_page_wait=40,
        next_page_wait=0.95,
        headless=False,
        keywords=[
            'UPC', 'Global Trade Identification Number', 'Model Number', 'Model Name',
            'Manufacturer', 'Item Dimensions D x W x H', 'Product Dimensions',
            'Item Dimensions', 'Brand', 'EAN', 'Operating System', 'Memory Storage Capacity',
            'Screen Size', 'Resolution', 'Ram Memory Installed Size',
            'Refresh Rate', 'CPU Model', 'CPU Speed', 'Material Type',
            'Product Style', 'Mounting Type','Model Year','Warranty Description','Warranty Description','Built-In Media',
            'Wireless Provider','Cellular Technology','Connectivity Technology','Wireless Network Technology'
        ]
    )
    
    t2 = time.time()
    
    print(f"\n{'='*60}")
    print(f"Total time: {t2-t1:.2f} seconds")
    print(f"Output saved to: {output_file}")
    print(f"{'='*60}")
