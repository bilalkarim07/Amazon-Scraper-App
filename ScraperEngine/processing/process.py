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
        # ---------------------------------------------------------------
    # FINAL DATASET CLEANUP
    # ---------------------------------------------------------------
    print("[INFO] Preparing final dataset...")

    try:
        # -----------------------------------------------------------
        # Remove columns that should not appear in the final
        # client-facing dataset.
        # -----------------------------------------------------------
        columns_to_remove = [
            'Comments',
            'Availability',
            'Display Features',
            'Price Box',
            'Product Information',
        ]

        dataframe.drop(
            columns=[
                column
                for column in columns_to_remove
                if column in dataframe.columns
            ],
            inplace=True,
            errors='ignore'
        )

        # -----------------------------------------------------------
        # Rename final columns.
        #
        # KeyWord -> Product Information
        # Description -> About this item
        # -----------------------------------------------------------
        rename_map = {}

        if 'KeyWord' in dataframe.columns:
            rename_map['KeyWord'] = 'Product Information'

        if 'Description' in dataframe.columns:
            rename_map['Description'] = 'About this item'

        if rename_map:
            dataframe.rename(
                columns=rename_map,
                inplace=True
            )

        # -----------------------------------------------------------
        # FINAL ABOUT THIS ITEM REPAIR
        #
        # This runs AFTER:
        #   - extraction
        #   - processing
        #   - column removal
        #   - column renaming
        #
        # Therefore repair_about_this_item() works directly with
        # the final column names.
        # -----------------------------------------------------------
        try:
            dataframe = repair_about_this_item(
                dataframe
            )

        except Exception as e:
            logger.warning(
                "[processor] Final About this item repair "
                f"failed: {e}"
            )

    except Exception as e:
        logger.warning(
            "[processor] Final dataset cleanup failed: "
            f"{e}"
        )

    # ---------------------------------------------------------------
    # SAVE FINAL PROCESSED DATA
    # ---------------------------------------------------------------
    print(
        f"[INFO] Saving processed data to {output_file}"
    )

    try:
        dataframe.to_csv(
            output_file,
            index=False
        )

    except Exception as e:
        logger.error(
            f"Failed to save processed data to "
            f"{output_file}: {e}"
        )
        raise


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



def repair_about_this_item(df):
    """
    Final-stage repair for 'About this item'.

    This runs AFTER:
        1. Extraction
        2. Processing
        3. Column removal
        4. Column renaming

    Rules:
        - Never overwrite an existing About this item value.
        - Only repair rows where About this item is missing.
        - Top Highlights must contain a usable value.
        - Product Information-style key/value data is NOT treated
          as About this item.
        - Valid bullet-style Top Highlights can be transferred
          into About this item.
        - After successful transfer, Top Highlights is changed
          to 'Not Mentioned'.
        - Every operation is protected by exception handling.
    """

    try:

        # -----------------------------------------------------------
        # Validate required columns
        # -----------------------------------------------------------
        if "About this item" not in df.columns:

            logger.warning(
                "[processor] 'About this item' column "
                "not found; skipping repair"
            )

            return df

        if "Top Highlights" not in df.columns:

            logger.warning(
                "[processor] 'Top Highlights' column "
                "not found; skipping repair"
            )

            return df

        # -----------------------------------------------------------
        # Helper: determine whether a value is missing
        # -----------------------------------------------------------
        def is_missing(value):

            try:

                if value is None:
                    return True

                if pd.isna(value):
                    return True

                value = str(value).strip()

                return (
                    value == ""
                    or value.lower() in {
                        "none",
                        "null",
                        "nan",
                        "not mentioned",
                    }
                )

            except Exception as e:

                logger.debug(
                    "[processor] is_missing() failed: "
                    f"{e}"
                )

                return True

        # -----------------------------------------------------------
        # Helper: split Product Information into sections
        #
        # Example:
        #
        # Brand | Apple
        # ----------------------------------------
        # Operating System | iOS 16
        # ----------------------------------------
        # RAM | 8 GB
        # -----------------------------------------------------------
        def split_product_information(value):

            try:

                text = str(value).strip()

                if not text:
                    return []

                sections = [
                    section.strip()
                    for section in re.split(
                        r"-{5,}",
                        text
                    )
                    if section.strip()
                ]

                return sections

            except Exception as e:

                logger.debug(
                    "[processor] split_product_information() "
                    f"failed: {e}"
                )

                return []

        # -----------------------------------------------------------
        # Helper: detect Product Information
        #
        # We are specifically looking for multiple:
        #
        # Key | Value
        #
        # pairs separated by horizontal boundaries.
        # -----------------------------------------------------------
        def looks_like_product_information(value):

            try:

                sections = split_product_information(
                    value
                )

                # Product Information should contain multiple
                # sections.
                if len(sections) < 2:
                    return False

                key_value_count = 0

                for section in sections:

                    try:

                        if "|" not in section:
                            continue

                        left, right = section.split(
                            "|",
                            1
                        )

                        if (
                            left.strip()
                            and right.strip()
                        ):
                            key_value_count += 1

                    except Exception as e:

                        logger.debug(
                            "[processor] Product Information "
                            f"section parse failed: {e}"
                        )

                        continue

                return key_value_count >= 2

            except Exception as e:

                logger.debug(
                    "[processor] "
                    "looks_like_product_information() failed: "
                    f"{e}"
                )

                return False

        # -----------------------------------------------------------
        # Helper: detect bullet-style About this item
        #
        # Examples:
        #
        # • Fully unlocked...
        # • Inspected and guaranteed...
        # • Successfully passed...
        # -----------------------------------------------------------
        def looks_like_about_this_item(value):

            try:

                text = str(value).strip()

                if not text:
                    return False

                # Never classify Product Information as
                # About this item.
                if looks_like_product_information(
                    text
                ):
                    return False

                lines = [
                    line.strip()
                    for line in text.splitlines()
                    if line.strip()
                ]

                if not lines:
                    return False

                bullet_prefixes = (
                    "•",
                    "▪",
                    "●",
                    "○",
                    "◦",
                    "- ",
                    "* ",
                )

                bullet_lines = [
                    line
                    for line in lines
                    if line.startswith(
                        bullet_prefixes
                    )
                ]

                return len(bullet_lines) >= 1

            except Exception as e:

                logger.debug(
                    "[processor] "
                    "looks_like_about_this_item() failed: "
                    f"{e}"
                )

                return False

        # -----------------------------------------------------------
        # Counters for diagnostics
        # -----------------------------------------------------------
        repaired_count = 0
        product_information_count = 0
        invalid_top_highlight_count = 0

        logger.info(
            "[processor] Starting final "
            "About this item validation"
        )

        # -----------------------------------------------------------
        # Process every row independently
        # -----------------------------------------------------------
        for index in df.index:

            try:

                about_value = df.at[
                    index,
                    "About this item"
                ]

                top_highlight_value = df.at[
                    index,
                    "Top Highlights"
                ]

                # -------------------------------------------------
                # CASE 1:
                # About this item already has a value.
                #
                # DO NOTHING.
                # -------------------------------------------------
                if not is_missing(
                    about_value
                ):
                    continue

                # -------------------------------------------------
                # CASE 2:
                # About this item is missing and Top Highlights
                # is also missing.
                #
                # Nothing can be repaired.
                # -------------------------------------------------
                if is_missing(
                    top_highlight_value
                ):
                    continue

                # -------------------------------------------------
                # CASE 3:
                # Top Highlights contains Product Information.
                #
                # Example:
                #
                # Brand | Apple
                # ----------------------------------------
                # Operating System | iOS 16
                # ----------------------------------------
                # RAM | 8 GB
                #
                # DO NOT copy this into About this item.
                # -------------------------------------------------
                if looks_like_product_information(
                    top_highlight_value
                ):

                    product_information_count += 1

                    logger.warning(
                        "[processor] About this item missing "
                        "but Top Highlights contains "
                        "Product Information. "
                        f"Row index={index}"
                    )

                    logger.warning(
                        "[processor] Product Information "
                        f"candidate at row {index}: "
                        f"{str(top_highlight_value)[:500]}"
                    )

                    continue

                # -------------------------------------------------
                # CASE 4:
                # Top Highlights contains valid bullet-style
                # About this item content.
                #
                # Transfer:
                #
                # Top Highlights
                #       ↓
                # About this item
                #
                # Then clear Top Highlights.
                # -------------------------------------------------
                if looks_like_about_this_item(
                    top_highlight_value
                ):

                    # Copy Top Highlights into About this item.
                    df.at[
                        index,
                        "About this item"
                    ] = top_highlight_value

                    # We successfully used Top Highlights to
                    # repair About this item.
                    #
                    # Therefore remove the duplicate value from
                    # Top Highlights.
                    df.at[
                        index,
                        "Top Highlights"
                    ] = "Not Mentioned"

                    repaired_count += 1

                    logger.info(
                        "[processor] Repaired About this item "
                        f"from Top Highlights at row {index}; "
                        "Top Highlights reset to Not Mentioned"
                    )

                    continue

                # -------------------------------------------------
                # CASE 5:
                # Top Highlights exists but does not match a
                # recognized About this item format.
                #
                # Don't guess.
                # -------------------------------------------------
                invalid_top_highlight_count += 1

                logger.warning(
                    "[processor] About this item missing "
                    "but Top Highlights did not match "
                    "a recognized About this item format. "
                    f"Row index={index}"
                )

            except Exception as e:

                # -------------------------------------------------
                # IMPORTANT:
                # One bad row must NEVER stop processing.
                # -------------------------------------------------
                logger.warning(
                    "[processor] Failed to process "
                    f"About this item row {index}: {e}"
                )

                continue

        # -----------------------------------------------------------
        # Final diagnostics
        # -----------------------------------------------------------
        logger.info(
            "[processor] Final About this item validation "
            "completed | "
            f"repaired={repaired_count} | "
            f"product_information={product_information_count} | "
            f"unrecognized={invalid_top_highlight_count}"
        )

        return df

    except Exception as e:

        # -----------------------------------------------------------
        # Global safety net.
        #
        # Even if something unexpected happens inside the repair
        # function, return the original dataframe rather than
        # breaking the scraper/process pipeline.
        # -----------------------------------------------------------
        logger.warning(
            "[processor] Final About this item validation "
            f"failed: {e}"
        )

        return df