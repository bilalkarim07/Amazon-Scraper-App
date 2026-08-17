"""
Process module - Clean, normalize, and enrich scraped Amazon product data.

Converts raw extracted data into processed ProductData objects with:
- Cleaned price information (extraction of Sale Price, Marked Price, Discount)
- Best Seller Rank extraction
- Keyword information parsing into structured KeywordInformation objects
- URL normalization
- Data validation and standardization
"""

import pandas as pd
import re
import time
from models import ProductData
from utils.logger import logger
from utils.safe_ops import safe_str, is_missing


def _safe_apply(series, func, field_name: str):
    """Apply a transform function row-by-row without aborting on bad values."""
    def wrapper(value):
        try:
            return func(value)
        except Exception as e:
            logger.debug(f"{field_name} processing error for {value!r}: {e}")
            return 'Not Mentioned'
    return series.apply(wrapper)


def stars(content):
    """Clean and standardize ratings format."""
    try:
        if is_missing(content):
            return 'Not Mentioned'
        return safe_str(content).replace(' out of 5 stars', '').strip()
    except Exception:
        return 'Not Mentioned'


def reviews(content):
    """Clean and standardize reviews format."""
    try:
        if is_missing(content):
            return 'Not Mentioned'
        return safe_str(content).replace(' Reviews', '').strip()
    except Exception:
        return 'Not Mentioned'


def refine_store_name(content):
    """Clean and standardize store name."""
    try:
        if is_missing(content):
            return 'Not Mentioned'
        text = safe_str(content)
        if 'Visit the' in text:
            return text.replace('Visit the', '').strip()
        if 'Brand:' in text:
            return text.replace('Brand:', '').strip()
        return text
    except Exception:
        return 'Not Mentioned'


def process_merchant(content):
    """Extract merchant name from structured data."""
    try:
        if is_missing(content):
            return 'Not Mentioned'
        list_of_words = safe_str(content).split('|')
        return list_of_words[-1].strip() if list_of_words else 'Not Mentioned'
    except Exception:
        return 'Not Mentioned'


def keyword_extractor(content, keyword, separator='-------------------------------'):
    """Extract a specific keyword's value from the raw KeyWord column content."""
    try:
        text = safe_str(content, default="")
        keyword_text = safe_str(keyword, default="")
        if not text or text == 'Not Mentioned' or not keyword_text or keyword_text not in text:
            return 'Not Mentioned'

        for segment in text.split(separator):
            segment = segment.strip()
            if keyword_text in segment:
                return segment.replace(f'{keyword_text} |', '').strip()
    except Exception as e:
        logger.debug(f"keyword_extractor error for {keyword!r}: {e}")

    return 'Not Mentioned'


def clean_keyword_column(content: str, separator: str = '-------------------------------') -> str:
    """
    Pre-process the KeyWord column content before keyword extraction.

    Rules (applied per segment, split by separator):
      - If there is NO text before '|'  → remove the segment (no label = useless).
      - If there IS text before '|' but nothing after '|' → keep, append 'Not Mentioned'.
      - If there is text on BOTH sides of '|' → keep as-is.
    
    Returns:
        Cleaned keyword column string ready for parsing into KeywordInformation objects
    """
    try:
        if is_missing(content):
            return 'Not Mentioned'

        segments = safe_str(content).split(separator)
        cleaned = []
        seen_labels = set()

        for segment in segments:
            try:
                segment = segment.strip()
                if not segment:
                    continue

                if '|' not in segment:
                    if segment:
                        label_key = segment.lower()
                        if label_key in seen_labels:
                            continue
                        seen_labels.add(label_key)
                        cleaned.append(f"{segment} | Not Mentioned")
                    continue

                left, *rest = segment.split('|', 1)
                right = rest[0] if rest else ''

                left = left.strip()
                right = right.strip()

                if not left:
                    continue

                label_key = left.lower()
                if label_key in seen_labels:
                    continue
                seen_labels.add(label_key)

                if not right:
                    cleaned.append(f"{left} | Not Mentioned")
                else:
                    cleaned.append(f"{left} | {right}")
            except Exception as e:
                logger.debug(f"clean_keyword_column segment error: {e}")
                continue

        if not cleaned:
            return 'Not Mentioned'

        return (f"\n{separator}\n").join(cleaned)
    except Exception as e:
        logger.debug(f"clean_keyword_column error: {e}")
        return 'Not Mentioned'


def best_seller(content):
    """Extract Best Sellers Rank from Product Information column."""
    try:
        if is_missing(content) or 'Best Sellers Rank' not in safe_str(content):
            return 'Not Mentioned'
        
        result = keyword_extractor(content=content, keyword='Best Sellers Rank', separator='-' * 40)
        if result != 'Not Mentioned':
            return result.split(' ')[0]
    except Exception as e:
        logger.debug(f"best_seller error: {e}")
    return 'Not Mentioned'


def extract_price_info(content, symbol='$'):
    """Extract and parse price information from Price Box content."""
    default = {
        'Sale Price': 'Not Mentioned',
        'Marked Price': 'Not Mentioned',
        'Discount': 'Not Mentioned'
    }

    try:
        if is_missing(content):
            return default.copy()

        content = safe_str(content).lower()

        repeated_pattern = rf"{re.escape(symbol)}([\d.,]+){re.escape(symbol)}\1"
        price_keywords = [
            'rrp', 'list price', 'typical price', 'typical value',
            'list value', 'was', 'msrp', 'original price',
            'suggested retail price', 'bundle list price',
            'lowest price in 30 days', 'one-time price'
        ]

        match = re.search(repeated_pattern, content)
        if match and not any(k in content for k in price_keywords):
            return {
                'Sale Price': f"{symbol}{match.group(1)}",
                'Marked Price': f"{symbol}{match.group(1)}",
                'Discount': '0%'
            }

        result = default.copy()
        parts = content.split()

        if len(parts) >= 1:
            result['Sale Price'] = parts[0]

        if len(parts) >= 3 and parts[2].isdigit():
            result['Discount'] = parts[2] + '%'

        for label in price_keywords:
            if label in content:
                pattern = rf"{re.escape(label)}:\s*{re.escape(symbol)}([\d.,]+)"
                m = re.search(pattern, content)
                if m:
                    result['Marked Price'] = f"{symbol}{m.group(1)}"
                    break

        return result
    except Exception as e:
        logger.debug(f"extract_price_info error: {e}")
        return default.copy()


def append_base(content, base_url='https://www.amazon.com/'):
    """Append base URL to relative links."""
    try:
        if is_missing(content):
            return 'Not Mentioned'
        text = safe_str(content)
        if text.startswith('http'):
            return text
        return base_url + text
    except Exception:
        return 'Not Mentioned'




def _resolve_keyword_column_name(keyword: str, existing_columns) -> str:
    """Pick a safe column name for an extracted keyword."""
    base_name = safe_str(keyword, default="").strip()
    if not base_name:
        return ""

    if base_name not in existing_columns:
        return base_name

    suffix = 2
    while f"{base_name}_{suffix}" in existing_columns:
        suffix += 1

    resolved = f"{base_name}_{suffix}"
    logger.warning(
        f"Keyword column '{base_name}' already exists; using '{resolved}' instead"
    )
    return resolved


def process_data(
    input_file,
    output_file,
    price_symbol='$',
    base_append='https://www.amazon.com/',
    keywords=None
):
    """
    Process extracted Amazon product data.
    
    Converts raw CSV data into processed ProductData objects with:
    - Cleaned and normalized fields
    - Extracted price information
    - Best seller rank extraction
    - Keyword information parsed into KeywordInformation objects
    - All URLs properly formatted
    
    Args:
        input_file: Path to input CSV file (raw extracted data)
        output_file: Path to output CSV file (processed data)
        price_symbol: Currency symbol for price extraction (default: '$')
        base_append: Base URL to prepend to relative links
        keywords: List of keywords to extract from product information
    
    Returns:
        Processed DataFrame
    """
    if keywords is None:
        keywords = []
    
    t1 = time.time()
    print(f"[INFO] Loading data from {input_file}")
    
    try:
        dataframe = pd.read_csv(input_file)
    except Exception as e:
        logger.error(f"Failed to load {input_file}: {e}")
        raise
    
    # Extract price information
    print("[INFO] Extracting price information...")
    try:
        price_results = _safe_apply(
            dataframe['Price Box'],
            lambda x: extract_price_info(x, symbol=price_symbol),
            'Price Box'
        )
        price_df = price_results.apply(pd.Series)
        dataframe[['Sale Price', 'Marked Price', 'Discount']] = price_df
    except Exception as e:
        logger.warning(f"Price extraction failed, using defaults: {e}")
        dataframe['Sale Price'] = 'Not Mentioned'
        dataframe['Marked Price'] = 'Not Mentioned'
        dataframe['Discount'] = 'Not Mentioned'
    
    # Extract best seller rank
    print("[INFO] Extracting best seller rank...")
    if 'Product Information' in dataframe.columns:
        dataframe['Best Seller Rank'] = _safe_apply(
            dataframe['Product Information'], best_seller, 'Best Seller Rank'
        )
    else:
        dataframe['Best Seller Rank'] = 'Not Mentioned'
    
    # Refine ratings and reviews
    print("[INFO] Refining ratings and reviews...")
    if 'Ratings' in dataframe.columns:
        dataframe['Ratings'] = _safe_apply(dataframe['Ratings'], stars, 'Ratings')
    if 'Reviews' in dataframe.columns:
        dataframe['Reviews'] = _safe_apply(dataframe['Reviews'], reviews, 'Reviews')
    
    # Process merchant and store information
    print("[INFO] Processing merchant and store information...")
    if 'Merchant' in dataframe.columns:
        dataframe['Merchant'] = _safe_apply(dataframe['Merchant'], process_merchant, 'Merchant')
    if 'Store Name' in dataframe.columns:
        dataframe['Store Name'] = _safe_apply(dataframe['Store Name'], refine_store_name, 'Store Name')
    if 'Store Link' in dataframe.columns:
        dataframe['Store Link'] = _safe_apply(
            dataframe['Store Link'],
            lambda x: append_base(x, base_url=base_append),
            'Store Link'
        )
    if 'Seller Profile' in dataframe.columns:
        dataframe['Seller Profile'] = _safe_apply(
            dataframe['Seller Profile'],
            lambda x: append_base(x, base_url=base_append),
            'Seller Profile'
        )
    
    # Extract keywords from the KeyWord column if provided
    if keywords:
        print(f"[INFO] Extracting keywords from 'KeyWord' column: {keywords}")

        if 'KeyWord' not in dataframe.columns:
            print("[WARN] 'KeyWord' column not found – initialising with 'Not Mentioned'")
            dataframe['KeyWord'] = 'Not Mentioned'

        print("[INFO] Cleaning KeyWord column segments...")
        dataframe['KeyWord'] = _safe_apply(dataframe['KeyWord'], clean_keyword_column, 'KeyWord')

        seen_keyword_names = set()
        for keyword in keywords:
            try:
                keyword_text = safe_str(keyword, default="").strip()
                if not keyword_text:
                    continue

                if keyword_text.lower() in seen_keyword_names:
                    logger.debug(f"Skipping duplicate keyword request: {keyword_text}")
                    continue
                seen_keyword_names.add(keyword_text.lower())

                column_name = _resolve_keyword_column_name(keyword_text, dataframe.columns)
                if not column_name:
                    continue

                dataframe[column_name] = _safe_apply(
                    dataframe['KeyWord'],
                    lambda x, kw=keyword_text: keyword_extractor(x, keyword=kw),
                    column_name
                )
            except Exception as e:
                logger.warning(f"Failed to extract keyword {keyword!r}: {e}")
                continue
    
    # Save processed data
    # ---------------------------------------------------------
    # FINAL OUTPUT TRANSFORMATIONS
    # ---------------------------------------------------------
    print("[INFO] Finalizing output dataset...")

    try:
        dataframe = finalize_output_dataframe(dataframe)
    except Exception as e:
        logger.error(
            f"Final output transformation failed: {e}"
        )

    # ---------------------------------------------------------
    # SAVE FINAL DATASET
    # ---------------------------------------------------------
    print(f"[INFO] Saving processed data to {output_file}")

    try:
        dataframe.to_csv(
            output_file,
            index=False
        )
    except Exception as e:
        logger.error(
            f"Failed to save processed data to {output_file}: {e}"
        )
        raise
    
    t2 = time.time()
    print(f"[INFO] Processing completed in {t2 - t1:.2f} seconds")
    
    return dataframe


def process_data_with_objects(input_file: str, output_file: str, price_symbol: str = '$',
                              base_append: str = 'https://www.amazon.com/', keywords: list = None):
    """
    Alternative processing function that works with ProductData objects.
    
    This version loads data into ProductData objects and leverages the structured format.
    
    Args:
        input_file: Path to input CSV file
        output_file: Path to output CSV file
        price_symbol: Currency symbol for price extraction
        base_append: Base URL to prepend to relative links
        keywords: List of keywords to extract
    
    Returns:
        List of processed ProductData objects
    """
    df = process_data(input_file, output_file, price_symbol, base_append, keywords)
    
    products = []
    for idx, row in df.iterrows():
        try:
            product = ProductData.from_dict(row.to_dict())
            products.append(product)
        except Exception as e:
            url = safe_str(row.get('Product Link', 'Not Mentioned'))
            logger.warning(f"Row {idx} could not become ProductData ({url}): {e}")
            products.append(ProductData.create_fallback(url=url, error=str(e)))
    
    return products


def format_about_this_item(content):
    """
    Preserve Amazon's bullet-point structure in the final dataframe.
    """

    try:
        if content is None:
            return 'Not Mentioned'

        text = safe_str(content).strip()

        if not text or text == 'Not Mentioned':
            return 'Not Mentioned'

        # Already formatted
        if '• ' in text:
            lines = []

            for line in text.splitlines():
                line = line.strip()

                if not line:
                    continue

                if not line.startswith('•'):
                    line = f'• {line}'

                lines.append(line)

            return '\n'.join(lines) if lines else 'Not Mentioned'

        # Handle common existing separators
        parts = re.split(
            r'\s*(?:\n+|•)\s*',
            text
        )

        parts = [
            part.strip()
            for part in parts
            if part.strip()
        ]

        if not parts:
            return 'Not Mentioned'

        return '\n'.join(
            f'• {part}'
            for part in parts
        )

    except Exception as e:
        logger.debug(
            f"format_about_this_item error: {e}"
        )
        return 'Not Mentioned'

def finalize_output_dataframe(dataframe):
    """
    Perform final output-only transformations after all extraction
    and processing logic has completed.

    This function intentionally runs LAST so it does not interfere
    with existing extraction/processing logic.
    """

    try:
        # ---------------------------------------------------------
        # 1. Remove the original Product Information column
        # ---------------------------------------------------------
        #
        # Best Seller Rank has already been extracted from it by
        # this point, so it is now safe to remove.
        #
        if 'Product Information' in dataframe.columns:
            try:
                dataframe = dataframe.drop(
                    columns=['Product Information']
                )
            except Exception as e:
                logger.warning(
                    f"Could not remove Product Information: {e}"
                )

        # ---------------------------------------------------------
        # 2. Rename KeyWord -> Product Information
        # ---------------------------------------------------------
        if 'KeyWord' in dataframe.columns:
            try:
                dataframe = dataframe.rename(
                    columns={
                        'KeyWord': 'Product Information'
                    }
                )
            except Exception as e:
                logger.warning(
                    f"Could not rename KeyWord column: {e}"
                )
        else:
            # Keep final schema predictable
            dataframe['Product Information'] = 'Not Mentioned'

        # ---------------------------------------------------------
        # 3. Rename Description -> About this item
        # ---------------------------------------------------------
        if 'Description' in dataframe.columns:
            try:
                dataframe = dataframe.rename(
                    columns={
                        'Description': 'About this item'
                    }
                )
            except Exception as e:
                logger.warning(
                    f"Could not rename Description column: {e}"
                )

        # ---------------------------------------------------------
        # 4. Remove unwanted columns
        # ---------------------------------------------------------
        columns_to_remove = [
            'Comments',
            'Availability',
            'Display Features',
            'Price Box'
        ]

        existing_to_remove = [
            column
            for column in columns_to_remove
            if column in dataframe.columns
        ]

        if existing_to_remove:
            try:
                dataframe = dataframe.drop(
                    columns=existing_to_remove
                )
            except Exception as e:
                logger.warning(
                    f"Could not remove final columns: {e}"
                )

        # ---------------------------------------------------------
        # 5. Format About this item
        # ---------------------------------------------------------
        if 'About this item' in dataframe.columns:
            dataframe['About this item'] = _safe_apply(
                dataframe['About this item'],
                format_about_this_item,
                'About this item'
            )

    except Exception as e:
        logger.error(
            f"Final dataframe transformation failed: {e}"
        )

    return dataframe