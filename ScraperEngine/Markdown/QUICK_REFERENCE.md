# Quick Reference Guide - New Architecture

## 🚀 Quick Start

### Old Way (Still works, but outdated)
```python
from amazon_scraper import AmazonScraper

scraper = AmazonScraper(listings='input.csv', max_threads=4)
scraper.extract_process(output='output.csv', keywords=['UPC', 'Brand'])
```

### New Way (Recommended)
```python
from runner import run_scraping

output = run_scraping(
    listings='input.csv',
    output='output.csv',
    keywords=['UPC', 'Brand']
)
```

### Command Line
```bash
# Using new runner (recommended)
python runner/main.py

# Using legacy main (still works)
python main.py
```

---

## 📦 Data Classes

### ProductData - Your Main Interface

```python
from models import ProductData

# Create from CSV row
product = ProductData.from_dict({
    'Product Link': 'https://amazon.com/dp/B001...',
    'Title': 'Product Name',
    'Ratings': '4.5 out of 5 stars',
    # ... all other columns
})

# Access properties with autocomplete
print(product.title)
print(product.asin)
print(product.sale_price)
print(product.ratings)

# Work with structured keyword data
product.parse_keyword_information()
for kw in product.keyword_information:
    print(f"{kw.keyword}: {kw.value}")

# Get specific keyword easily
upc = product.get_keyword_value('UPC')
has_brand = product.has_keyword('Brand')

# Set/update keywords
product.set_keyword_value('Brand', 'Sony')

# Convert back to CSV dict
csv_row = product.to_dict()
```

### KeywordInformation - Structured Keywords

```python
from models import KeywordInformation

# Parse from string
kw = KeywordInformation.from_string("UPC | 123456789")

# Create manually
kw = KeywordInformation(keyword="Brand", value="Sony")

# Use properties
print(kw.keyword)  # "Brand"
print(kw.value)    # "Sony"
print(kw)          # "Brand | Sony"

# Check if value is actually mentioned
if kw.is_mentioned():
    print(kw.to_dict())  # {'keyword': 'Brand', 'value': 'Sony'}
```

---

## 🔄 Processing Pipeline

### Loading and Processing CSV

```python
import pandas as pd
from models import ProductData

# Load raw extracted data
df = pd.read_csv('extracted.csv')

# Convert to ProductData objects
products = []
for idx, row in df.iterrows():
    product = ProductData.from_dict(row.to_dict())
    products.append(product)

# Access product data
for product in products:
    print(f"{product.title}: {product.sale_price}")
    
    # Get keywords
    upc = product.get_keyword_value('UPC')
    brand = product.get_keyword_value('Brand')
```

### Direct Processing

```python
from processing import process_data

# Process raw extracted data
df = process_data(
    input_file='extracted.csv',
    output_file='processed.csv',
    keywords=['UPC', 'Brand', 'Model Number']
)

# Optionally convert to ProductData objects
products = [
    ProductData.from_dict(row.to_dict())
    for idx, row in df.iterrows()
]
```

---

## 📁 File Structure Reference

| File | Purpose |
|------|---------|
| `runner/main.py` | **NEW** - Main entry point, use this! |
| `models/product_data.py` | **NEW** - ProductData class |
| `models/keyword_information.py` | **NEW** - KeywordInformation class |
| `scraping/extractor.py` | **UPDATED** - Now returns ProductData |
| `scraping/thread_worker.py` | **UPDATED** - Works with ProductData |
| `processing/process.py` | **NEW LOCATION** - Moved from root |
| `amazon_scraper.py` | **UPDATED** - Uses new imports |
| `main.py` | **UPDATED** - Now calls runner |

---

## 🛠️ Common Tasks

### Task: Get all product titles
```python
import pandas as pd
from models import ProductData

df = pd.read_csv('output.csv')
for idx, row in df.iterrows():
    product = ProductData.from_dict(row.to_dict())
    print(product.title)
```

### Task: Extract specific keywords
```python
product = ProductData.from_dict(row)
upc = product.get_keyword_value('UPC')
brand = product.get_keyword_value('Brand')
model = product.get_keyword_value('Model Number')
print(f"UPC: {upc}, Brand: {brand}, Model: {model}")
```

### Task: Find products with missing data
```python
if not product.has_keyword('UPC'):
    print(f"Missing UPC for: {product.title}")
```

### Task: Update product data
```python
product.title = "New Title"
product.sale_price = "$99.99"
product.set_keyword_value('Brand', 'NewBrand')
```

### Task: Save modified products back to CSV
```python
import pandas as pd
from models import ProductData

products = [...]  # Your ProductData objects
rows = [p.to_dict() for p in products]
df = pd.DataFrame(rows)
df.to_csv('modified.csv', index=False)
```

---

## ✅ Validation Checklist

- [x] All columns accessible as properties
- [x] Keyword information structured in `KeywordInformation` objects
- [x] No breaking changes to CSV format
- [x] Backwards compatible with old API
- [x] Clean folder organization
- [x] Simple entry point in `runner/main.py`
- [x] Full type hints and docstrings
- [x] IDE autocomplete support

---

## 📚 For More Details

See [ARCHITECTURE.md](./ARCHITECTURE.md) for complete architecture documentation.

---

**Status**: ✅ Production Ready
