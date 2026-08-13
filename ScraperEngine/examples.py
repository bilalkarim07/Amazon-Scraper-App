"""
Examples - How to Use the New Architecture

This file demonstrates various ways to use the refactored Amazon scraper
with ProductData and KeywordInformation classes.
"""

# ============================================================================
# Example 1: Simple Extraction and Processing
# ============================================================================

def example_1_simple_run():
    """The simplest way to run the scraper."""
    from runner import run_scraping
    
    output = run_scraping(
        listings='input.csv',
        output='output.csv',
        mode='extract_process',
        max_threads=4
    )
    
    print(f"✓ Scraping completed: {output}")


# ============================================================================
# Example 2: Using ProductData Objects
# ============================================================================

def example_2_product_data():
    """Work directly with ProductData objects."""
    import pandas as pd
    from models import ProductData
    
    # Load CSV
    df = pd.read_csv('output.csv')
    
    # Convert to ProductData objects
    for idx, row in df.iterrows():
        product = ProductData.from_dict(row.to_dict())
        
        # Access properties with autocomplete
        print(f"Title: {product.title}")
        print(f"ASIN: {product.asin}")
        print(f"Price: {product.sale_price}")
        print(f"Ratings: {product.ratings}")
        print(f"---")
        
        # Parse and access keywords
        upc = product.get_keyword_value('UPC')
        brand = product.get_keyword_value('Brand')
        print(f"UPC: {upc}, Brand: {brand}\n")


# ============================================================================
# Example 3: Working with KeywordInformation
# ============================================================================

def example_3_keyword_information():
    """Work with structured keyword data."""
    from models import KeywordInformation
    
    # Create from string
    kw = KeywordInformation.from_string("UPC | 123456789")
    print(f"Keyword: {kw.keyword}")
    print(f"Value: {kw.value}")
    print(f"Is Mentioned: {kw.is_mentioned()}")
    print(f"String Representation: {kw}")
    print(f"Dict: {kw.to_dict()}\n")
    
    # Create manually
    brand_kw = KeywordInformation(keyword="Brand", value="Sony")
    print(f"Brand: {brand_kw.value}\n")
    
    # Handle "Not Mentioned"
    empty_kw = KeywordInformation(keyword="Model", value="")
    print(f"Empty value: {empty_kw.value}")
    print(f"Is Mentioned: {empty_kw.is_mentioned()}")


# ============================================================================
# Example 4: Parsing Keyword Column
# ============================================================================

def example_4_parse_keywords():
    """Parse raw keyword column into structured objects."""
    import pandas as pd
    from models import ProductData
    
    df = pd.read_csv('output.csv')
    
    for idx, row in df.iterrows():
        product = ProductData.from_dict(row.to_dict())
        
        # Parse keywords from raw column
        product.parse_keyword_information()
        
        # List all keywords
        print(f"Product: {product.title}")
        for kw_info in product.keyword_information:
            print(f"  {kw_info.keyword}: {kw_info.value}")
        print()


# ============================================================================
# Example 5: Filtering Products
# ============================================================================

def example_5_filter_products():
    """Filter products based on criteria."""
    import pandas as pd
    from models import ProductData
    
    df = pd.read_csv('output.csv')
    
    results = []
    for idx, row in df.iterrows():
        product = ProductData.from_dict(row.to_dict())
        
        # Filter by price
        if product.sale_price != "Not Mentioned":
            try:
                price = float(product.sale_price.replace('$', ''))
                if price < 100:
                    results.append(product)
            except:
                pass
    
    print(f"Found {len(results)} products under $100")
    for product in results:
        print(f"  {product.title}: {product.sale_price}")


# ============================================================================
# Example 6: Updating Product Data
# ============================================================================

def example_6_update_products():
    """Modify and save product data."""
    import pandas as pd
    from models import ProductData, KeywordInformation
    
    df = pd.read_csv('output.csv')
    updated_products = []
    
    for idx, row in df.iterrows():
        product = ProductData.from_dict(row.to_dict())
        
        # Update properties
        product.title = product.title.upper()
        
        # Add/update keywords
        product.set_keyword_value('Brand', 'Updated Brand')
        product.set_keyword_value('Custom Field', 'Custom Value')
        
        updated_products.append(product)
    
    # Save back to CSV
    rows = [p.to_dict() for p in updated_products]
    new_df = pd.DataFrame(rows)
    new_df.to_csv('updated_output.csv', index=False)
    
    print(f"✓ Saved {len(updated_products)} updated products")


# ============================================================================
# Example 7: Advanced Filtering
# ============================================================================

def example_7_advanced_filtering():
    """Complex filtering with multiple criteria."""
    import pandas as pd
    from models import ProductData
    
    df = pd.read_csv('output.csv')
    
    high_rated_products = []
    
    for idx, row in df.iterrows():
        product = ProductData.from_dict(row.to_dict())
        
        # Check multiple conditions
        try:
            # Has high rating
            rating_str = product.ratings.replace(' out of 5 stars', '')
            rating = float(rating_str)
            
            # Has good reviews
            reviews_str = product.reviews.replace(' Reviews', '')
            review_count = int(reviews_str.replace(',', ''))
            
            # Has required keywords
            has_upc = product.has_keyword('UPC')
            
            # All conditions met
            if rating >= 4.0 and review_count >= 100 and has_upc:
                high_rated_products.append(product)
        except:
            pass
    
    print(f"High-rated products: {len(high_rated_products)}")
    for product in high_rated_products:
        print(f"  {product.title}")


# ============================================================================
# Example 8: Using the AmazonScraper Directly
# ============================================================================

def example_8_direct_scraper():
    """Use AmazonScraper for more control."""
    from amazon_scraper import AmazonScraper
    
    # Create scraper
    scraper = AmazonScraper(
        listings='input.csv',
        max_threads=4
    )
    
    # Extract only
    extracted_file = scraper.extract(
        output_file='extracted.csv',
        first_page_wait=150,
        next_page_wait=5,
        headless=False
    )
    print(f"✓ Extracted: {extracted_file}")
    
    # Process extracted data
    processed_file = scraper.process(
        input_file=extracted_file,
        output_file='processed.csv',
        keywords=['UPC', 'Brand', 'Model Number']
    )
    print(f"✓ Processed: {processed_file}")


# ============================================================================
# Example 9: Batch Operations
# ============================================================================

def example_9_batch_operations():
    """Process multiple products in batch."""
    import pandas as pd
    from models import ProductData
    
    df = pd.read_csv('output.csv')
    
    # Collect stats
    stats = {
        'total': len(df),
        'with_price': 0,
        'with_rating': 0,
        'with_keywords': 0,
    }
    
    for idx, row in df.iterrows():
        product = ProductData.from_dict(row.to_dict())
        
        if product.sale_price != "Not Mentioned":
            stats['with_price'] += 1
        if product.ratings != "Not Mentioned":
            stats['with_rating'] += 1
        if product.keyword_information:
            stats['with_keywords'] += 1
    
    print("Product Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


# ============================================================================
# Run Examples
# ============================================================================

if __name__ == '__main__':
    import sys
    
    examples = {
        '1': ('Simple Run', example_1_simple_run),
        '2': ('ProductData Objects', example_2_product_data),
        '3': ('KeywordInformation', example_3_keyword_information),
        '4': ('Parse Keywords', example_4_parse_keywords),
        '5': ('Filter Products', example_5_filter_products),
        '6': ('Update Products', example_6_update_products),
        '7': ('Advanced Filtering', example_7_advanced_filtering),
        '8': ('Direct Scraper', example_8_direct_scraper),
        '9': ('Batch Operations', example_9_batch_operations),
    }
    
    print("Available Examples:")
    print("-" * 40)
    for key, (name, _) in examples.items():
        print(f"  {key}. {name}")
    print("-" * 40)
    print()
    
    choice = input("Select example to run (1-9, or 'all'): ").strip()
    
    if choice.lower() == 'all':
        for key, (name, func) in examples.items():
            print(f"\n{'='*60}")
            print(f"Running Example {key}: {name}")
            print(f"{'='*60}\n")
            try:
                func()
            except Exception as e:
                print(f"✗ Error: {e}")
    elif choice in examples:
        name, func = examples[choice]
        print(f"Running Example {choice}: {name}\n")
        try:
            func()
        except Exception as e:
            print(f"✗ Error: {e}")
    else:
        print("Invalid choice")
