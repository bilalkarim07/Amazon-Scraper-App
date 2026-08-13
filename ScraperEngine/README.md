# Amazon Product Scraper

A professional, multithreaded Amazon product scraper built with Python and Selenium. Features a clean OOP architecture, anti-bot detection measures, and flexible data processing capabilities.

## Features

✨ **Clean OOP API** - Simple, intuitive interface for scraping and processing  
🧵 **Multithreaded** - Scrape multiple products concurrently (1-5 threads)  
🤖 **Anti-Detection** - Realistic browser behavior to avoid bot detection  
👻 **Headless Mode** - Run browsers in background for automation  
📊 **Progress Logging** - Real-time progress updates for each thread  
💾 **Crash-Safe** - Immediate CSV writing prevents data loss  
🔧 **Flexible Processing** - Configurable price symbols, keywords, and URLs

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Installation

### Prerequisites

- Python 3.7+
- Chrome browser
- ChromeDriver (matching your Chrome version)

### Required Packages

```bash
pip install selenium beautifulsoup4 pandas lxml
```

### Setup

1. **Download ChromeDriver**
   - Download from [ChromeDriver Downloads](https://chromedriver.chromium.org/downloads)
   - Place `chromedriver.exe` in the project directory
   - Ensure it matches your Chrome browser version

2. **Verify Installation**
   ```bash
   python -c "from amazon_scraper import AmazonScraper; print('Setup complete!')"
   ```

---

## Quick Start

### 1. Create Input CSV

Create `input.csv` with product URLs:

```csv
Product Link
https://www.amazon.com/dp/B0DV5DPRKZ
https://www.amazon.com/dp/XXXXXXXXXX
```

### 2. Run the Scraper

```python
from amazon_scraper import AmazonScraper

# Initialize scraper
scraper = AmazonScraper(
    listings='input.csv',
    max_threads=3,
    webdriver_file='chromedriver.exe'
)

# Extract and process products
scraper.extract_process(
    output='products.csv',
    price_symbol='$',
    keywords=['UPC', 'Weight'],
    headless=False
)
```

### 3. Check Results

- **Thread Outputs:** `Threads/thread_1.csv`, `thread_2.csv`, etc.
- **Final Output:** `products.csv` (merged and processed)

---

## Usage Examples

### Example 1: Extract Only

Scrape products without processing:

```python
from amazon_scraper import AmazonScraper

scraper = AmazonScraper(
    listings='input.csv',
    max_threads=3,
    webdriver_file='chromedriver.exe'
)

scraper.extract(
    output_file='raw_data.csv',
    first_page_wait=150,  # Wait 150s for first page
    next_page_wait=5,     # Wait 5s for subsequent pages
    headless=False        # Show browser (set True to hide)
)
```

**Output:** Raw scraped data in `raw_data.csv`

---

### Example 2: Process Existing Data

Process already-scraped data:

```python
from amazon_scraper import AmazonScraper

scraper = AmazonScraper(
    listings=[],  # Not needed for processing
    max_threads=1,
    webdriver_file='chromedriver.exe'
)

scraper.process(
    input_file='raw_data.csv',
    output_file='processed_data.csv',
    price_symbol='$',
    base_append='https://www.amazon.com/',
    keywords=['UPC', 'Weight', 'ASIN', 'Brand']
)
```

**Output:** Processed data with price splitting, URL completion, and keyword extraction

---

### Example 3: Extract + Process (Combined)

One-step workflow:

```python
from amazon_scraper import AmazonScraper

scraper = AmazonScraper(
    listings='input.csv',
    max_threads=3,
    webdriver_file='chromedriver.exe'
)

scraper.extract_process(
    output='final_products.csv',
    price_symbol='$',
    base_append='https://www.amazon.com/',
    keywords=['UPC', 'Weight', 'Package Information'],
    first_page_wait=150,
    next_page_wait=5,
    headless=False
)
```

**Output:** Fully processed data in `final_products.csv`

---

### Example 4: Direct URL List

Pass URLs directly instead of CSV:

```python
from amazon_scraper import AmazonScraper

urls = [
    'https://www.amazon.com/dp/B0DV5DPRKZ',
    'https://www.amazon.com/dp/XXXXXXXXXX',
    'https://www.amazon.com/dp/YYYYYYYYYY'
]

scraper = AmazonScraper(
    listings=urls,  # Pass list directly
    max_threads=2,
    webdriver_file='chromedriver.exe'
)

scraper.extract_process(
    output='products.csv',
    price_symbol='$',
    headless=True  # Run in background
)
```

---

### Example 5: Different Amazon Region

Scrape from Amazon UK:

```python
scraper = AmazonScraper(
    listings='uk_products.csv',
    max_threads=3,
    webdriver_file='chromedriver.exe'
)

scraper.extract_process(
    output='uk_results.csv',
    price_symbol='£',
    base_append='https://www.amazon.co.uk/',
    keywords=['EAN', 'Weight']
)
```

---

## API Reference

### `AmazonScraper` Class

#### Constructor

```python
AmazonScraper(listings, max_threads=3, webdriver_file='chromedriver.exe')
```

**Parameters:**

- `listings` (str or list): CSV file path or list of product URLs
- `max_threads` (int): Number of concurrent threads (1-5, default: 3)
- `webdriver_file` (str): Path to ChromeDriver executable

---

#### `extract()` Method

Scrape Amazon products using multithreading.

```python
extract(
    output_file='output.csv',
    first_page_wait=150,
    next_page_wait=5,
    headless=False
)
```

**Parameters:**

- `output_file` (str): Path to save merged CSV
- `first_page_wait` (int): Wait time for first page load (seconds)
- `next_page_wait` (int): Wait time for subsequent pages (seconds)
- `headless` (bool): Run browser in headless mode

**Returns:** Path to output file

**Extracted Fields (19 total):**

- Product Link, ASIN, Title, Price Box
- Ratings, Reviews, Store Name, Store Link
- Item Details, Description, Product Images
- Product Information, Category, Sub Category
- Display Features, Merchant, Comments
- Main Product Image, BreadCrumb, Seller Profile

---

#### `process()` Method

Process extracted data with cleaning and enrichment.

```python
process(
    input_file,
    output_file,
    price_symbol='$',
    base_append='https://www.amazon.com/',
    keywords=None
)
```

**Parameters:**

- `input_file` (str): Path to raw extracted CSV
- `output_file` (str): Path to save processed CSV
- `price_symbol` (str): Currency symbol for price extraction
- `base_append` (str): Base URL to prepend to relative links
- `keywords` (list): Keywords to extract from product info

**Returns:** Path to processed output file

**Processing Operations:**

- Price splitting (Sale Price, Marked Price, Discount)
- Ratings/Reviews normalization
- Store name refinement
- Merchant parsing
- URL completion (Store Link, Seller Profile)
- Keyword extraction (dynamic based on input)
- Best Seller Rank extraction

---

#### `extract_process()` Method

Combined workflow: extract then process.

```python
extract_process(
    output='final_output.csv',
    price_symbol='$',
    base_append='https://www.amazon.com/',
    keywords=None,
    first_page_wait=150,
    next_page_wait=5,
    headless=False
)
```

**Parameters:** Combination of `extract()` and `process()` parameters

**Returns:** Path to final processed output file

---

## Project Structure

```
Amazon/
│
├── amazon_scraper.py          # Main OOP orchestrator
├── extractor.py               # Core scraping logic (preserved)
├── process.py                 # Data processing functions
├── main.py                    # Usage examples
│
├── utils/                     # Utility modules
│   ├── __init__.py
│   ├── headers.py             # Browser identity config
│   ├── logger.py              # Logging setup
│   ├── driver_manager.py      # WebDriver creation
│   ├── human_simulator.py     # Human behavior simulation
│   └── thread_worker.py       # Thread lifecycle management
│
├── Threads/                   # Thread output folder
│   ├── thread_1.csv
│   ├── thread_2.csv
│   └── thread_3.csv
│
├── chromedriver.exe           # Chrome WebDriver
├── input.csv                  # Input product URLs
├── README.md                  # This file
└── strategy.md                # Architecture documentation
```

---

## Configuration

### Wait Times

Adjust wait times based on your internet speed and Amazon's response time:

```python
scraper.extract(
    first_page_wait=200,  # Increase for slow connections
    next_page_wait=3      # Decrease for faster scraping
)
```

### Thread Count

Balance between speed and resource usage:

```python
scraper = AmazonScraper(
    listings='input.csv',
    max_threads=5  # Maximum allowed
)
```

**Recommendations:**

- **1-2 threads:** Conservative, less detection risk
- **3 threads:** Balanced (default)
- **4-5 threads:** Faster but higher resource usage

### Headless Mode

For automation and background scraping:

```python
scraper.extract(headless=True)  # No browser window shown
```

**Use Cases:**

- Server deployments
- Scheduled tasks
- Background automation
- Resource-constrained environments

---

## Troubleshooting

### Issue: "Webdriver not found"

**Solution:** Ensure `chromedriver.exe` is in the project directory or provide full path:

```python
scraper = AmazonScraper(
    listings='input.csv',
    max_threads=3,
    webdriver_file=r'C:\path\to\chromedriver.exe'
)
```

---

### Issue: "CSV must contain 'Product Link' column"

**Solution:** Ensure your input CSV has the exact column name:

```csv
Product Link
https://www.amazon.com/dp/...
```

---

### Issue: Browser crashes or timeouts

**Solution 1:** Increase wait times:

```python
scraper.extract(first_page_wait=300, next_page_wait=10)
```

**Solution 2:** Reduce thread count:

```python
scraper = AmazonScraper(listings='input.csv', max_threads=1)
```

---

### Issue: CAPTCHA detected

**Symptoms:** Browser shows CAPTCHA or verification page

**Solutions:**

- Increase wait times between pages
- Reduce thread count to 1-2
- Run during off-peak hours
- Use headless=False to manually solve CAPTCHAs

---

### Issue: Missing data ("Not Mentioned")

**Cause:** Amazon's page structure varies by product

**Solution:** This is expected behavior. The scraper safely handles missing data by marking it as "Not Mentioned" rather than crashing.

---

### Issue: Import errors

**Solution:** Install dependencies:

```bash
pip install selenium beautifulsoup4 pandas lxml
```

Verify Python version:

```bash
python --version  # Should be 3.7+
```

---

## Progress Logging

The scraper provides real-time progress updates:

```
2026-01-22 23:13:45 - INFO - ============================================================
2026-01-22 23:13:45 - INFO - STARTING AMAZON PRODUCT EXTRACTION
2026-01-22 23:13:45 - INFO - ============================================================
2026-01-22 23:13:45 - INFO - Loaded 50 product URLs
2026-01-22 23:13:45 - INFO - Distributing URLs across 3 threads
2026-01-22 23:13:46 - INFO - Thread 1 started with 17 URLs
2026-01-22 23:13:46 - INFO - Thread 2 started with 17 URLs
2026-01-22 23:13:46 - INFO - Thread 3 started with 16 URLs
2026-01-22 23:15:12 - INFO - Thread 1 processing 1/17 links
2026-01-22 23:15:15 - INFO - Thread 2 processing 1/17 links
2026-01-22 23:17:20 - INFO - Thread 1 processing 2/17 links
...
2026-01-22 23:45:35 - INFO - All threads completed
2026-01-22 23:45:36 - INFO - Merged 50 products into output.csv
```

---

## Best Practices

### 1. Start Small

Test with 5-10 products before scraping hundreds:

```python
# Test run
test_urls = urls[:10]
scraper = AmazonScraper(listings=test_urls, max_threads=1)
```

### 2. Respect Rate Limits

Use appropriate wait times to avoid detection:

```python
scraper.extract(
    first_page_wait=150,  # Don't go below 30 seconds
    next_page_wait=5      # Don't go below 3 seconds
)
```

### 3. Monitor Threads

Check `Threads/` folder during scraping to verify data is being written.

### 4. Backup Data

Thread CSVs are preserved even if final merge fails - backup this folder regularly.

### 5. Use Headless for Production

During development use `headless=False` to see what's happening. In production, switch to `headless=True`.

---

## License

This project is for educational purposes. Please review Amazon's Terms of Service and robots.txt before scraping.

---

## Support

For issues or questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review `strategy.md` for architecture details
3. Examine `main.py` for usage examples

---

## Changelog

### Version 2.0 (Current)

- ✅ Refactored to OOP architecture
- ✅ Added headless mode support
- ✅ Implemented progress logging
- ✅ Modularized utilities
- ✅ Created clean API

### Version 1.0

- Initial functional implementation
- Basic multithreading
- CSV output
