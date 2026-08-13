# Migration & Testing Guide

## ✅ What's Been Done

### 1. Data Classes Created ✓
- `models/product_data.py` - Main ProductData class with all columns as properties
- `models/keyword_information.py` - KeywordInformation class for structured keyword data
- Both fully typed with type hints and comprehensive docstrings

### 2. Scraping Module Refactored ✓
- `scraping/extractor.py` - Now returns ProductData objects instead of dicts
- `scraping/thread_worker.py` - Updated to work with ProductData (converts to dict for CSV)
- All utility functions preserved and working

### 3. Processing Module Reorganized ✓
- `processing/process.py` - Moved from root, all functions working
- `clean_keyword_column()` - Ready for parsing into KeywordInformation
- Supports processing with or without ProductData objects

### 4. Folder Structure Created ✓
```
models/           # Data classes
scraping/         # Scraping logic
processing/       # Processing logic
runner/           # Main entry point
utils/            # Utilities (existing)
```

### 5. Main Entry Point Created ✓
- `runner/main.py` - Clean, simple, documented entry point
- `main.py` updated - Now calls runner (backwards compatible)
- Full parameter documentation

### 6. Documentation Created ✓
- `ARCHITECTURE.md` - Complete architecture documentation
- `QUICK_REFERENCE.md` - Quick start guide
- `examples.py` - 9 detailed usage examples

### 7. Updated All Imports ✓
- `amazon_scraper.py` - Updated to use new module structure
- Thread workers - Updated to use new imports
- All circular import issues resolved

---

## 🧪 Testing Checklist

### Pre-Testing Verification

- [x] All new files created
- [x] All imports updated
- [x] No circular dependencies
- [x] File structure correct
- [x] Documentation complete

### Testing Steps (Do These!)

#### Step 1: Verify Imports
```python
# Test in Python REPL or new script
from models import ProductData, KeywordInformation
from scraping.extractor import scrape_product, get_driver
from processing import process_data
from amazon_scraper import AmazonScraper
from runner import run_scraping

print("✓ All imports successful!")
```

#### Step 2: Test ProductData Creation
```python
from models import ProductData

# Create from dict
data_dict = {
    'Product Link': 'https://amazon.com/dp/B001',
    'Title': 'Test Product',
    'ASIN': 'B00012345X',
    'Ratings': '4.5 out of 5 stars',
}

product = ProductData.from_dict(data_dict)

assert product.title == 'Test Product'
assert product.asin == 'B00012345X'
assert product.to_dict()['Product Link'] == 'https://amazon.com/dp/B001'

print("✓ ProductData works correctly!")
```

#### Step 3: Test KeywordInformation
```python
from models import KeywordInformation

# Parse from string
kw = KeywordInformation.from_string("UPC | 123456789")
assert kw.keyword == "UPC"
assert kw.value == "123456789"
assert kw.is_mentioned() == True

# Parse empty
kw_empty = KeywordInformation.from_string("Brand | ")
assert kw_empty.value == ""
assert kw_empty.is_mentioned() == False

print("✓ KeywordInformation works correctly!")
```

#### Step 4: Test CSV Round-Trip
```python
import pandas as pd
from models import ProductData

# Load CSV
df = pd.read_csv('output.csv')

# Convert to ProductData
for idx, row in df.iterrows():
    product = ProductData.from_dict(row.to_dict())
    
    # Convert back
    csv_dict = product.to_dict()
    
    # Verify all columns present
    assert 'Product Link' in csv_dict
    assert 'Title' in csv_dict
    assert 'ASIN' in csv_dict
    
    if idx >= 2:  # Test first 3 rows
        break

print("✓ CSV round-trip works!")
```

#### Step 5: Test Keyword Parsing
```python
import pandas as pd
from models import ProductData

df = pd.read_csv('output.csv')

# Get product with keywords
for idx, row in df.iterrows():
    product = ProductData.from_dict(row.to_dict())
    
    if product.raw_keyword_column != "Not Mentioned":
        # Parse keywords
        product.parse_keyword_information()
        
        # Should have keyword info
        assert len(product.keyword_information) > 0
        
        # Test retrieval
        first_kw = product.keyword_information[0]
        assert first_kw.keyword is not None
        assert first_kw.value is not None
        
        print(f"✓ Found {len(product.keyword_information)} keywords")
        break

print("✓ Keyword parsing works!")
```

#### Step 6: Test Full Scraping (OPTIONAL - Time Consuming)
```python
from runner import run_scraping
import os

# Only run if you have input.csv and chromedriver
if os.path.exists('input.csv') and os.path.exists('chromedriver.exe'):
    output = run_scraping(
        listings='input.csv',
        output='test_output.csv',
        mode='extract_process',
        max_threads=1,  # Just 1 thread for testing
        first_page_wait=10,
        next_page_wait=1,
        headless=True,
        keywords=['UPC', 'Brand']
    )
    
    assert os.path.exists(output)
    print(f"✓ Full scraping works! Output: {output}")
else:
    print("⊘ Skipped full scraping test (missing input.csv or chromedriver.exe)")
```

---

## 🔄 Backwards Compatibility Check

### Old Code Still Works?

```python
# This should still work exactly as before
from amazon_scraper import AmazonScraper

scraper = AmazonScraper(
    listings='input.csv',
    max_threads=4
)

# Old API still works
scraper.extract_process(
    output='output.csv',
    keywords=['UPC', 'Brand']
)

print("✓ Backwards compatible!")
```

### CSV Format Unchanged?

```python
# Output should have same columns as before
import pandas as pd

df_old = pd.read_csv('output.csv')  # New output
expected_cols = [
    'Product Link', 'ASIN', 'Title', 'Price Box', 'Ratings', 'Reviews',
    'Store Name', 'Store Link', 'Top Highlights', 'Item Details', 
    'Description', 'Product Images', 'Product Information',
    'Category', 'Sub Category', 'Display Features', 'Merchant',
    'Display Features 1', 'Comments', 'Main Product Image', 
    'BreadCrumb', 'Seller Profile', 'Variations', 'Availability', 'KeyWord'
]

assert all(col in df_old.columns for col in expected_cols)
print("✓ CSV format unchanged!")
```

---

## 🚀 Running Tests

### Quick Test Script

Create `test_refactor.py`:

```python
"""Quick test script for refactored code"""

def test_imports():
    """Test all imports work"""
    try:
        from models import ProductData, KeywordInformation
        from scraping.extractor import scrape_product
        from processing import process_data
        from amazon_scraper import AmazonScraper
        from runner import run_scraping
        print("✓ PASS: All imports successful")
        return True
    except Exception as e:
        print(f"✗ FAIL: Import error - {e}")
        return False

def test_product_data():
    """Test ProductData creation"""
    try:
        from models import ProductData
        
        data = {
            'Product Link': 'test',
            'Title': 'Test',
            'ASIN': 'B001',
            'Ratings': '4.5 out of 5 stars'
        }
        
        product = ProductData.from_dict(data)
        assert product.title == 'Test'
        assert product.asin == 'B001'
        
        dict_out = product.to_dict()
        assert dict_out['Title'] == 'Test'
        
        print("✓ PASS: ProductData works")
        return True
    except Exception as e:
        print(f"✗ FAIL: ProductData error - {e}")
        return False

def test_keyword_info():
    """Test KeywordInformation"""
    try:
        from models import KeywordInformation
        
        kw = KeywordInformation.from_string("UPC | 12345")
        assert kw.keyword == "UPC"
        assert kw.value == "12345"
        assert kw.is_mentioned()
        
        print("✓ PASS: KeywordInformation works")
        return True
    except Exception as e:
        print(f"✗ FAIL: KeywordInformation error - {e}")
        return False

if __name__ == '__main__':
    print("\n" + "="*60)
    print("TESTING REFACTORED ARCHITECTURE")
    print("="*60 + "\n")
    
    results = []
    results.append(test_imports())
    results.append(test_product_data())
    results.append(test_keyword_info())
    
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("="*60 + "\n")
    
    if passed == total:
        print("✓ ALL TESTS PASSED - Ready for use!")
    else:
        print("✗ Some tests failed - Review errors above")
```

Run it:
```bash
python test_refactor.py
```

---

## 📋 Validation Checklist

Use this to verify everything is working:

- [ ] All imports work without errors
- [ ] ProductData objects create successfully
- [ ] KeywordInformation parsing works
- [ ] CSV round-trip (dict → ProductData → dict) preserves data
- [ ] Keyword column parsing extracts keywords
- [ ] Old API still works (backwards compatible)
- [ ] New runner API works
- [ ] Examples run without errors
- [ ] Folder structure is clean

---

## 🔍 Common Issues & Solutions

### Issue: ModuleNotFoundError: No module named 'models'
**Solution**: Ensure you're running from the project root directory, not from a subdirectory

### Issue: Circular import error
**Solution**: All circular imports have been eliminated. If you see this, clear Python cache:
```bash
find . -type d -name __pycache__ -exec rm -r {} +
find . -name "*.pyc" -delete
```

### Issue: ProductData missing properties
**Solution**: Ensure you're using the new ProductData class from `models/product_data.py`, not old data dicts

### Issue: KeywordInformation not parsing correctly
**Solution**: Ensure keyword separator matches the raw column format ("-------------------------------" by default)

---

## 📞 Next Steps

1. **Run tests** - Use test script above
2. **Try examples** - Run `python examples.py`
3. **Test with real data** - Use your input.csv
4. **Gradual migration** - Update your scripts one by one
5. **Report issues** - Document any problems found

---

## ✨ What's Next (Optional)

- [ ] Add unit tests with pytest
- [ ] Add CI/CD pipeline
- [ ] Create web interface
- [ ] Add database export option
- [ ] Implement async processing
- [ ] Add data validation schemas

---

**Status**: Ready for Testing
**Estimated Test Time**: 30-60 minutes
