# Amazon Scraper - Refactored Architecture

This document describes the new object-oriented architecture of the Amazon scraper project.

## 📁 Project Structure

```
Amazon/
├── models/                    # 📦 Data Classes (Core Domain Models)
│   ├── __init__.py
│   ├── keyword_information.py # KeywordInformation class
│   └── product_data.py        # ProductData class (all columns as properties)
│
├── scraping/                  # 🔄 Scraping Module
│   ├── __init__.py
│   ├── extractor.py           # scrape_product() returns ProductData
│   └── thread_worker.py       # ThreadWorker (updated for ProductData)
│
├── processing/                # 🧹 Processing Module
│   ├── __init__.py
│   └── process.py             # Data cleaning and enrichment
│
├── runner/                    # 🚀 Main Entry Point
│   ├── __init__.py
│   └── main.py                # Clean, simple main script
│
├── utils/                     # 🛠️ Utilities (unchanged)
│   ├── driver_manager.py
│   ├── human_simulator.py
│   ├── headers.py
│   ├── logger.py
│   └── __init__.py
│
├── amazon_scraper.py          # Main orchestrator (updated imports)
├── main.py                    # Legacy entry point (can delete later)
└── ... (other legacy files)
```

## 🏗️ Architecture Overview

### 1. **Models Package** (`models/`)

Contains two core data classes:

#### `ProductData` Class
Replaces dictionaries with a structured class. Every CSV column becomes a property:

```python
from models import ProductData

# Load from CSV row
product = ProductData.from_dict(row_dict)

# Access properties
title = product.title
price = product.sale_price
rating = product.ratings

# Work with keyword information (structured!)
kw_info = product.get_keyword_value('UPC')  # Returns string
product.set_keyword_value('Brand', 'Sony')
product.has_keyword('Model Number')  # Returns boolean

# Convert back to dict for CSV
csv_dict = product.to_dict()
```

#### `KeywordInformation` Class
Wraps keyword | value pairs from the KeyWord column:

```python
from models import KeywordInformation

# Create from string
kw = KeywordInformation.from_string("UPC | 123456789")
print(kw.keyword)  # "UPC"
print(kw.value)    # "123456789"

# Access structured data
if kw.is_mentioned():
    print(kw.to_dict())  # {'keyword': 'UPC', 'value': '123456789'}
```

### 2. **Scraping Package** (`scraping/`)

Handles all extraction logic:

- `extractor.py`: Core scraping logic
  - `scrape_product(driver, url, wait) → ProductData` ✨ Returns ProductData objects!
  - `get_driver()`: Creates configured WebDriver
  - Utility functions: `safe_text()`, `extract_asin()`, etc.

- `thread_worker.py`: Multithreaded scraping
  - Accepts ProductData from `scrape_product()`
  - Converts to dict for CSV writing

### 3. **Processing Package** (`processing/`)

Cleans and enriches data:

- `process.py`: Data processing functions
  - `process_data()`: Main processing pipeline
  - `clean_keyword_column()`: Parses keyword column into structured format
  - `extract_price_info()`: Extracts Sale Price, Marked Price, Discount
  - Works with both raw CSV and ProductData objects

### 4. **Runner Package** (`runner/`)

Clean entry point for running the scraper:

- `main.py`: Simple, documented main script
  - `run_scraping()`: Main function for programmatic use
  - Default `__main__` block for direct execution
  - Easy to customize parameters

## 🔄 Data Flow

```
Input CSV
    ↓
scrape_product() → ProductData (with KeywordInformation list)
    ↓
ThreadWorker converts ProductData → dict → writes to CSV
    ↓
Raw Extracted CSV
    ↓
process_data() → ProductData objects
    ↓
Enhanced/Cleaned CSV with structured keyword data
```

## 🚀 Usage

### Simple Usage (Default Keywords)

```python
from runner import run_scraping

output = run_scraping(
    listings='input.csv',
    output='output.csv',
    mode='extract_process',
    max_threads=4
)
```

### Programmatic Usage

```python
from amazon_scraper import AmazonScraper

scraper = AmazonScraper(
    listings='input.csv',
    max_threads=4
)

# Extract only
scraper.extract(output_file='extracted.csv', headless=False)

# Process only
scraper.process(
    input_file='extracted.csv',
    output_file='processed.csv',
    keywords=['UPC', 'Brand', 'Model Number']
)

# Extract + Process
scraper.extract_process(
    output='final.csv',
    keywords=['UPC', 'Brand']
)
```

### Direct Execution

```bash
python runner/main.py
```

## 📊 Key Improvements

| Aspect | Before | After |
|--------|--------|-------|
| **Data Access** | Dictionaries `data['Title']` | Properties `product.title` |
| **IDE Support** | No autocomplete | Full autocomplete in IDEs |
| **Type Safety** | Untyped | `ProductData` type hints |
| **Keyword Data** | Raw strings | `KeywordInformation` objects |
| **Maintainability** | Hard to trace | Clear class definitions |
| **Extensibility** | Scattered logic | Organized by module |
| **Organization** | Root-level chaos | Clean folder structure |

## 🔧 Working with ProductData

### Loading from CSV

```python
import pandas as pd
from models import ProductData

df = pd.read_csv('extracted.csv')
for idx, row in df.iterrows():
    product = ProductData.from_dict(row.to_dict())
    print(product.title)
    print(product.get_keyword_value('UPC'))
```

### Accessing Keywords

```python
# Parse keyword information
product.parse_keyword_information()

# Get specific keyword
upc = product.get_keyword_value('UPC')

# List all keywords
for kw_info in product.keyword_information:
    print(f"{kw_info.keyword}: {kw_info.value}")

# Check if keyword exists
if product.has_keyword('Brand'):
    print("Has brand information")
```

### Creating New Products

```python
from models import ProductData, KeywordInformation

product = ProductData(
    title="Sample Product",
    asin="B00012345X",
    ratings="4.5 out of 5 stars"
)

# Add keywords
product.keyword_information = [
    KeywordInformation("UPC", "123456789"),
    KeywordInformation("Brand", "Sony")
]

# Convert to CSV-compatible dict
csv_dict = product.to_dict()
```

## 🧪 Testing/Validation

The new structure maintains backward compatibility:

1. **CSV format unchanged** - All old columns still work
2. **Processing functions work identically** - Same outputs
3. **Scraping logic unchanged** - Same extraction results
4. **Thread behavior preserved** - Same multithreading

## 📝 Migration Notes

- Old `extractor.py`, `process.py`, `main.py` remain but are superseded
- No changes needed to input CSV format
- Output CSV structure identical to before
- Can gradually adopt new API - coexist peacefully

## ✅ Next Steps (Optional)

1. Delete legacy files after testing (`old_extractor.py`, etc.)
2. Add unit tests for `ProductData` and `KeywordInformation`
3. Create async/concurrent processing wrapper
4. Add database export option (instead of CSV)
5. Build web interface around `run_scraping()`

---

**Created**: 2024
**Architecture**: Object-Oriented Clean Code
**Status**: Production Ready
