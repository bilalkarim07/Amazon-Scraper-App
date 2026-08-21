"""
Extractor module - Scrapes Amazon product pages and returns ProductData objects.
This module handles all page extraction logic, converting raw HTML/page data into
structured ProductData objects.
"""

import os
import re
import time
import logging
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
import json
from models import ProductData
from utils.logger import logger
from utils.safe_ops import safe_str

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ============================================================================
# Utility Functions for Text/Attribute Extraction
# ============================================================================

def safe_text(tag):
    """Safely extract text from a BeautifulSoup tag."""
    try:
        if tag:
            txt = tag.get_text(strip=True)
            return txt if txt else "Not Mentioned"
    except:
        pass
    return "Not Mentioned"


def safe_attr(tag, attr):
    """Safely extract an attribute from a BeautifulSoup tag."""
    try:
        if tag and tag.has_attr(attr):
            val = tag.get(attr, "").strip()
            return val if val else "Not Mentioned"
    except:
        pass
    return "Not Mentioned"


def extract_asin(url):
    """Extract ASIN from Amazon product URL."""
    try:
        m = re.search(r"/dp/([A-Z0-9]{10})", url)
        return m.group(1) if m else "Not Mentioned"
    except:
        return "Not Mentioned"


def boundary_format(pairs, separator: str = "-" * 40):
    """Format key-value pairs with boundary separators."""
    if not pairs:
        return "Not Mentioned"
    out = []
    for pair in pairs:
        try:
            k, v = pair
            k = safe_str(k, default="")
            v = safe_str(v, default="")
            if k and v and k != "Not Mentioned" and v != "Not Mentioned":
                out.append(f"{k} | {v}")
                out.append(separator)
        except (TypeError, ValueError) as e:
            logger.debug(f"boundary_format skipped invalid pair {pair!r}: {e}")
            continue
        except Exception as e:
            logger.debug(f"boundary_format error for pair {pair!r}: {e}")
            continue
    result = "\n".join(out).rstrip(separator).rstrip("\n")
    return result if result else "Not Mentioned"

def extract_top_highlight_container(soup):
    """
    Extract both Top Highlights and About this item from
    Amazon's #topHighlight container.

    Amazon's structure can contain:

        #topHighlight
            |
            +-- .product-facts-detail
            |       |
            |       +-- span.a-color-base  -> key
            |       +-- span.a-color-base  -> value
            |
            +-- h3.product-facts-title
            |       About this item
            |
            +-- ul.a-unordered-list
                    |
                    +-- li -> About this item bullet

    Returns:
        tuple:
            (
                top_highlights,
                about_this_item
            )
    """

    top_highlights = "Not Mentioned"
    about_this_item = "Not Mentioned"

    try:

        # -----------------------------------------------------------
        # Locate the complete Amazon topHighlight container
        # -----------------------------------------------------------
        container = soup.find(
            "div",
            id="topHighlight"
        )

        if not container:
            return (
                top_highlights,
                about_this_item
            )

        logger.info(
            "[worker] topHighlight container found; "
            "extracting Top Highlights + About this item"
        )

        # ===========================================================
        # PART 1
        # TOP HIGHLIGHTS
        #
        # .product-facts-detail
        #       ↓
        # span.a-color-base
        #       ↓
        # key + value
        # ===========================================================

        try:

            item_pairs = []

            fact_blocks = container.find_all(
                "div",
                class_="product-facts-detail"
            )

            for block in fact_blocks:

                try:

                    spans = block.find_all(
                        "span",
                        class_="a-color-base"
                    )

                    if len(spans) < 2:
                        continue

                    key = safe_text(
                        spans[0]
                    )

                    value = safe_text(
                        spans[1]
                    )

                    if (
                        key != "Not Mentioned"
                        and value != "Not Mentioned"
                        and key.strip()
                        and value.strip()
                    ):

                        item_pairs.append(
                            (
                                key.strip(),
                                value.strip()
                            )
                        )

                except Exception as e:

                    logger.debug(
                        "[worker] topHighlight "
                        f"fact block parse error: {e}"
                    )

                    continue

            if item_pairs:

                top_highlights = boundary_format(
                    item_pairs
                )

                logger.info(
                    "[worker] topHighlight: extracted "
                    f"{len(item_pairs)} fact pair(s)"
                )

        except Exception as e:

            logger.warning(
                "[worker] topHighlight facts extraction "
                f"failed: {e}"
            )

        # ===========================================================
        # PART 2
        # ABOUT THIS ITEM
        #
        # Inside the SAME #topHighlight container:
        #
        # h3.product-facts-title
        #       "About this item"
        #
        # followed by:
        #
        # ul.a-unordered-list
        #       ↓
        # li
        #       ↓
        # span.a-list-item
        #
        # We deliberately scope this search to `container`.
        # ===========================================================

        try:

            # Find the UL specifically inside topHighlight.
            about_list = container.find(
                "ul",
                class_=re.compile(
                    r"\ba-unordered-list\b"
                )
            )

            if about_list:

                bullets = []

                for li in about_list.find_all(
                    "li"
                ):

                    try:

                        # Prefer the actual Amazon list-item span.
                        span = li.find(
                            "span",
                            class_=re.compile(
                                r"\ba-list-item\b"
                            )
                        )

                        if span:

                            bullet = safe_text(
                                span
                            )

                        else:

                            bullet = safe_text(
                                li
                            )

                        if (
                            bullet
                            and bullet != "Not Mentioned"
                            and bullet not in bullets
                        ):

                            bullets.append(
                                bullet
                            )

                    except Exception as e:

                        logger.debug(
                            "[worker] topHighlight "
                            f"About this item li parse error: {e}"
                        )

                        continue

                if bullets:

                    # Keep the actual bullet representation.
                    about_this_item = "\n".join(
                        f"• {bullet}"
                        for bullet in bullets
                    )

                    logger.info(
                        "[worker] topHighlight: extracted "
                        f"{len(bullets)} About this item bullet(s)"
                    )

        except Exception as e:

            logger.warning(
                "[worker] topHighlight About this item "
                f"extraction failed: {e}"
            )

        return (
            top_highlights,
            about_this_item
        )

    except Exception as e:

        logger.warning(
            "[worker] extract_top_highlight_container "
            f"failed: {e}"
        )

        return (
            "Not Mentioned",
            "Not Mentioned"
        )

# ============================================================================
# BUY BOX EXTRACTION (ENHANCED)
# ============================================================================

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------

NOT_MENTIONED = "Not Mentioned"

BUYBOX_ID = "buyBoxAccordion"
BUYBOX_ATTRIBUTE = "buybox-accordion"
OFFER_ROW_ATTRIBUTE = "data-buying-option-index"

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def clean_text(value):
    """
    Normalize text safely.
    """
    if value is None:
        return NOT_MENTIONED

    try:
        text = value.get_text(" ", strip=True)
    except AttributeError:
        text = str(value).strip()

    text = re.sub(r"\s+", " ", text).strip()

    return text if text else NOT_MENTIONED


def is_valid(value):
    """
    Determine whether an extracted value is actually usable.
    """
    if value is None:
        return False

    value = str(value).strip()

    if not value:
        return False

    return value.lower() not in {
        "not mentioned",
        "none",
        "null",
        "nan",
        "n/a",
        "na",
    }


def first_valid(*values):
    """
    Return the first usable value.
    """
    for value in values:
        if is_valid(value):
            return str(value).strip()

    return NOT_MENTIONED


# ----------------------------------------------------------------------------
# Buy Box Detection
# ----------------------------------------------------------------------------

def detect_buybox_exact(soup):
    """
    LOGIC #1: Exact Amazon Buy Box ID.
    """
    container = soup.find("div", id=BUYBOX_ID)
    if container:
        logger.info("[BUYBOX SUCCESS #1] Exact #buyBoxAccordion detected.")
    return container


def detect_buybox_attribute(soup):
    """
    LOGIC #2: Amazon Buy Box semantic attribute.
    """
    container = soup.find(
        "div",
        attrs={"data-a-accordion-name": BUYBOX_ATTRIBUTE}
    )
    if container:
        logger.info(
            "[BUYBOX SUCCESS #2] data-a-accordion-name='buybox-accordion' detected."
        )
    return container


def detect_buybox_structure(soup):
    """
    LOGIC #3: Structural fallback.
    Requires: a-box-group, a-accordion, and data-buying-option-index.
    """
    candidates = soup.find_all(
        "div",
        class_=lambda classes: (
            classes
            and "a-box-group" in classes
            and "a-accordion" in classes
        )
    )

    for candidate in candidates:
        rows = candidate.find_all(
            "div",
            attrs={OFFER_ROW_ATTRIBUTE: True}
        )
        if rows:
            logger.info(
                "[BUYBOX SUCCESS #3] Structural Buy Box detected with %d offer row(s).",
                len(rows)
            )
            return candidate

    return None


def detect_single_buybox_offer(soup):
    """
    LOGIC #4: Detect single (non-accordion) buy box scenarios.
    
    When a product has ONLY ONE offer/seller, Amazon sometimes:
    - Omits the data-buying-option-index attribute
    - Uses simplified HTML structure
    - Still maintains a-box-group and a-accordion classes
    
    This detector identifies these single-offer containers.
    
    Returns:
        BeautifulSoup tag if single offer detected, None otherwise
    """
    try:
        # Pattern 1: Look for containers with accordion-like classes
        candidates = soup.find_all(
            "div",
            class_=lambda c: (
                c 
                and "a-box-group" in c 
                and "a-accordion" in c
            )
        )
        
        logger.debug(f"[BUYBOX SINGLE] Scanning {len(candidates)} potential container(s)")
        
        for container in candidates:
            try:
                # Count rows with data-buying-option-index (indicates multi-accordion)
                indexed_rows = container.find_all(
                    "div", 
                    attrs={OFFER_ROW_ATTRIBUTE: True}
                )
                
                # If it has indexed rows, it's multi-accordion (skip)
                if indexed_rows:
                    logger.debug(f"[BUYBOX SINGLE] Container has {len(indexed_rows)} indexed row(s); not single")
                    continue
                
                # Pattern 1a: Look for single offer box
                offer_boxes = container.find_all(
                    "div",
                    class_=lambda c: (
                        c 
                        and ("a-box" in c or "offer-card" in c)
                    )
                )
                
                # Heuristic: single box without sub-boxes
                if len(offer_boxes) == 1:
                    logger.info(
                        "[BUYBOX SINGLE] Single offer box detected "
                        "(no data-buying-option-index, single .a-box)"
                    )
                    return container
                
                # Pattern 1b: Alternative detection via price + title pattern
                # (useful if structure doesn't have clear .a-box wrapper)
                if not indexed_rows:
                    price_tag = container.find(
                        "span",
                        class_=re.compile(r"a-price")
                    )
                    title_tag = container.find(
                        "span",
                        class_=re.compile(r"a-text-bold")
                    )
                    
                    # Both price and title present = likely single offer
                    if price_tag and title_tag:
                        logger.info(
                            "[BUYBOX SINGLE] Single offer detected via "
                            "price + title pattern (no indexed rows)"
                        )
                        return container
                
            except Exception as e:
                logger.debug(f"[BUYBOX SINGLE] Container scan error: {e}")
                continue
        
        # ---- NEW: relaxed detection for any div containing price and title ----
        # This catches renewed products that might not have a-box-group/a-accordion.
        all_divs = soup.find_all("div")
        for div in all_divs:
            try:
                # Skip obvious non-buybox containers
                if div.get("id") in ("corePriceDisplay_desktop_feature_div", "price", "productTitle"):
                    continue
                # Must contain a price element
                price_tag = div.find("span", class_=re.compile(r"a-price"))
                if not price_tag:
                    continue
                # Must contain a bold title or a text that looks like "Renewed" etc.
                title_tag = div.find("span", class_=re.compile(r"a-text-bold"))
                if not title_tag:
                    # Maybe it's a span with class "a-size-base a-color-base" or similar
                    title_tag = div.find("span", class_=re.compile(r"a-size-base"))
                if not title_tag:
                    continue
                # Also check for seller or delivery info to confirm it's the buy box
                seller = div.find(id="sfsb_accordion_head") or div.find(id="sellerProfileTriggerId")
                delivery = div.find(id="deliveryBlockSmallMessage") or div.find(id="deliveryBlockMessage")
                availability = div.find(id="availability")
                if seller or delivery or availability:
                    logger.info(
                        "[BUYBOX SINGLE] Single offer detected via relaxed content-based scan "
                        "(price + title + seller/delivery/availability)"
                    )
                    return div
            except Exception as e:
                continue
        
        logger.debug("[BUYBOX SINGLE] No single offer container detected")
        return None
        
    except Exception as e:
        logger.debug(f"[BUYBOX SINGLE] Detection function error: {e}")
        return None


def wrap_single_offer_as_row(container):
    """
    For single buy box without data-buying-option-index attribute,
    create a synthetic row wrapper to reuse existing extract_single_offer().
    
    This bridges the gap between single-offer HTML and the extraction
    logic designed for multi-row scenarios.
    
    Args:
        container (BeautifulSoup): The detected single-offer container
    
    Returns:
        BeautifulSoup: A wrapper div with synthetic data-buying-option-index
                       or None if wrapping fails
    """
    try:
        if not container:
            logger.warning("[BUYBOX SINGLE] No container provided for wrapping")
            return None
        
        # Strategy 1: If container already has an indexed row, use it
        indexed_row = container.find("div", attrs={OFFER_ROW_ATTRIBUTE: True})
        if indexed_row:
            logger.debug("[BUYBOX SINGLE] Container already has indexed row; using directly")
            return indexed_row
        
        # Strategy 2: Find the offer box and wrap it
        offer_box = container.find(
            "div",
            class_=lambda c: (
                c 
                and ("a-box" in c or "offer-card" in c)
            )
        )
        
        if not offer_box:
            # Strategy 3: Use the entire container as the row
            logger.debug("[BUYBOX SINGLE] No .a-box found; using container as row")
            offer_box = container
        
        # Create a shallow copy to avoid modifying original
        # (BeautifulSoup tags can be copied)
        try:
            wrapper = offer_box
        except Exception as e:
            logger.warning(f"[BUYBOX SINGLE] Copy failed ({e}); using original")
            wrapper = offer_box
        
        # Inject synthetic index attribute if missing
        if not wrapper.get(OFFER_ROW_ATTRIBUTE):
            wrapper[OFFER_ROW_ATTRIBUTE] = "0"
            logger.info(
                "[BUYBOX SINGLE] Synthetic data-buying-option-index='0' "
                "created for single offer"
            )
        
        logger.debug("[BUYBOX SINGLE] Wrapper created successfully")
        return wrapper
        
    except Exception as e:
        logger.warning(f"[BUYBOX SINGLE] Wrapping failed: {e}")
        return None


def find_buybox_container(soup):
    """
    Try multiple detection patterns to find the buy box container.
    NOW SUPPORTS: Existing patterns + Single offer detection + Content-based fallback
    
    Detection order:
    1. Exact Amazon Buy Box ID (#buyBoxAccordion)
    2. Amazon Buy Box semantic attribute (data-a-accordion-name='buybox-accordion')
    3. Structural pattern for multi-accordion
    4. Single offer pattern (relaxed)
    5. Content-based fallback (NEW) - finds any div with price + seller/delivery
    """
    
    detection_patterns = [
        ("exact ID", lambda: detect_buybox_exact(soup)),
        ("accordion attribute", lambda: detect_buybox_attribute(soup)),
        ("structural multi-accordion", lambda: detect_buybox_structure(soup)),
        ("single offer (relaxed)", lambda: detect_single_buybox_offer(soup)),  # UPDATED
        ("content-based fallback", lambda: detect_single_buybox_offer(soup)),  # same function now covers both
    ]
    
    for pattern_name, detector_func in detection_patterns:
        try:
            container = detector_func()
            if container:
                logger.info(
                    "[BUYBOX] Buy box container detected via: %s",
                    pattern_name
                )
                return container
        
        except Exception as e:
            logger.debug(
                "[BUYBOX] Detection pattern '%s' failed: %s",
                pattern_name,
                e
            )
            continue
    
    logger.warning(
        "[BUYBOX] No buy box container could be detected "
        "(tried 5 patterns: exact ID, attribute, structural, single, content-based)"
    )
    return None


# ----------------------------------------------------------------------------
# Offer Row Detection
# ----------------------------------------------------------------------------

def find_offer_rows(container):
    """
    Find actual Amazon buying-option rows.
    NOW SUPPORTS: Multi-accordion (existing) + Single offer (new)
    
    We require data-buying-option-index for multi-accordion.
    For single offers, we create a synthetic row wrapper.
    """
    try:
        if not container:
            logger.warning("[BUYBOX] Container is None")
            return []
        
        # ============================================================
        # STRATEGY 1: Multi-Accordion Rows (Existing Logic)
        # ============================================================
        rows = container.find_all(
            "div",
            attrs={OFFER_ROW_ATTRIBUTE: True}
        )
        
        if rows:
            # Sort by numeric index
            def row_index(row):
                raw = row.get(OFFER_ROW_ATTRIBUTE)
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    return 999999
            
            rows.sort(key=row_index)
            logger.info(
                "[BUYBOX] Found %d multi-accordion row(s) with %s attribute",
                len(rows),
                OFFER_ROW_ATTRIBUTE
            )
            return rows
        
        # ============================================================
        # STRATEGY 2: Single Offer Fallback (New Logic)
        # ============================================================
        logger.info(
            "[BUYBOX] No indexed rows found (%s); checking for single offer...",
            OFFER_ROW_ATTRIBUTE
        )
        
        synthetic_row = wrap_single_offer_as_row(container)
        
        if synthetic_row:
            try:
                # Validate that this row has recognizable offer elements
                has_price = bool(synthetic_row.select_one(".a-price"))
                has_title = bool(synthetic_row.select_one("span.a-text-bold"))
                
                logger.debug(
                    "[BUYBOX SINGLE] Validation: price=%s, title=%s",
                    has_price,
                    has_title
                )
                
                # At least one of price/title should exist
                if has_price or has_title:
                    logger.info(
                        "[BUYBOX SINGLE] Single offer validated; "
                        "returning as synthetic row"
                    )
                    return [synthetic_row]
                else:
                    logger.warning(
                        "[BUYBOX SINGLE] Synthetic row has no recognizable "
                        "price or title elements"
                    )
            
            except Exception as e:
                logger.debug(f"[BUYBOX SINGLE] Validation error: {e}")
        
        logger.warning(
            "[BUYBOX] No valid offer rows found "
            "(neither multi-accordion nor single offer)"
        )
        return []
        
    except Exception as e:
        logger.exception(f"[BUYBOX] find_offer_rows() exception: {e}")
        return []


# ----------------------------------------------------------------------------
# Condition / Offer Name
# ----------------------------------------------------------------------------

def extract_condition(row):
    """
    Extract condition / offer title.
    Primary: .accordion-caption .a-text-bold
    Fallbacks: .accordion-caption, span.a-text-bold
    """
    # Strategy 1
    tag = row.select_one(".accordion-caption .a-text-bold")
    value = clean_text(tag)
    if is_valid(value):
        logger.info("[BUYBOX FIELD SUCCESS] Condition strategy 1: %s", value)
        return value

    # Strategy 2
    tag = row.select_one(".accordion-caption")
    value = clean_text(tag)
    if is_valid(value):
        logger.info("[BUYBOX FIELD SUCCESS] Condition strategy 2: %s", value)
        return value

    # Strategy 3
    for tag in row.find_all("span", class_="a-text-bold"):
        value = clean_text(tag)
        if is_valid(value):
            logger.info("[BUYBOX FIELD SUCCESS] Condition strategy 3: %s", value)
            return value

    logger.warning("[BUYBOX FIELD FAILURE] Condition not found.")
    return NOT_MENTIONED


# ----------------------------------------------------------------------------
# Price
# ----------------------------------------------------------------------------

def extract_price(row):
    """
    Extract price.
    Multiple Amazon‑compatible strategies.
    """
    # Strategy 1: #corePrice_feature_div .a-price .a-offscreen
    tag = row.select_one("#corePrice_feature_div .a-price .a-offscreen")
    value = clean_text(tag)
    if is_valid(value):
        logger.info("[BUYBOX FIELD SUCCESS] Price strategy 1: %s", value)
        return value

    # Strategy 2: Any .a-price .a-offscreen
    tag = row.select_one(".a-price .a-offscreen")
    value = clean_text(tag)
    if is_valid(value):
        logger.info("[BUYBOX FIELD SUCCESS] Price strategy 2: %s", value)
        return value

    # Strategy 3: Build price from Amazon components
    price = row.select_one(".a-price")
    if price:
        symbol = clean_text(price.select_one(".a-price-symbol"))
        whole = clean_text(price.select_one(".a-price-whole"))
        fraction = clean_text(price.select_one(".a-price-fraction"))

        if is_valid(whole) and whole != NOT_MENTIONED:
            whole = re.sub(r"\D+$", "", whole)
            if is_valid(fraction):
                value = f"{symbol if is_valid(symbol) else '$'}{whole}.{fraction}"
            else:
                value = f"{symbol if is_valid(symbol) else '$'}{whole}"

            if is_valid(value):
                logger.info("[BUYBOX FIELD SUCCESS] Price strategy 3: %s", value)
                return value

    # Strategy 4: Regex over price text
    price_text = clean_text(row.select_one(".a-price"))
    if is_valid(price_text):
        match = re.search(r"[$€£₹]\s*[\d,]+(?:\.\d{1,2})?", price_text)
        if match:
            value = match.group(0)
            logger.info("[BUYBOX FIELD SUCCESS] Price strategy 4: %s", value)
            return value

    logger.warning("[BUYBOX FIELD FAILURE] Price not found.")
    return NOT_MENTIONED


# ----------------------------------------------------------------------------
# Availability
# ----------------------------------------------------------------------------

def extract_availability(row):
    """
    Extract stock/availability information.
    ENHANCED: Better support for single-offer scenarios via regex patterns
    
    Multiple strategies:
    1. Explicit ID-based selectors (#availability, .primary-availability-message)
    2. Text-based regex patterns (useful for single box with direct text)
    3. Class-based fallback (elements with availability-related classes)
    """
    try:
        # ============================================================
        # Strategy 1: Standard ID/Class-based selectors (existing)
        # ============================================================
        standard_selectors = [
            "#availability .primary-availability-message",
            ".primary-availability-message",
            "#availability"
        ]
        
        for selector in standard_selectors:
            tag = row.select_one(selector)
            if tag:
                value = clean_text(tag)
                if is_valid(value):
                    logger.info(
                        "[BUYBOX FIELD] Availability (selector '%s'): %s",
                        selector,
                        value
                    )
                    return value
        
        # ============================================================
        # Strategy 2: Text-based regex matching (NEW - for single box)
        # ============================================================
        # These patterns handle common Amazon availability messages
        text = clean_text(row)
        
        regex_patterns = [
            # Specific "Only X left" pattern
            (r"Only \d+ left[^.]*(?:order soon|soon)", None),
            # General "Only X left"
            (r"Only \d+ left[^.]*", None),
            # Standard stock phrases
            (r"\b(?:In Stock|Out of Stock|Currently unavailable|Temporarily out of stock)\b", None),
            # Generic "Available"
            (r"\bAvailable\b", None),
        ]
        
        for pattern, _ in regex_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(0).strip()
                logger.info(
                    "[BUYBOX FIELD] Availability (regex pattern '%s'): %s",
                    pattern,
                    value
                )
                return value
        
        # ============================================================
        # Strategy 3: Class-based fallback (for single box)
        # ============================================================
        # Look for divs with availability-related class names
        availability_divs = row.find_all(
            "div",
            class_=re.compile(r"availability|stock|supply", re.I)
        )
        
        for div in availability_divs:
            value = clean_text(div)
            if is_valid(value):
                # Check if it actually contains availability keywords
                text_lower = value.lower()
                if any(keyword in text_lower for keyword in ["stock", "available", "left", "order"]):
                    logger.info(
                        "[BUYBOX FIELD] Availability (class-based): %s",
                        value
                    )
                    return value
        
    except Exception as e:
        logger.debug(f"[BUYBOX FIELD] Availability extraction error: {e}")
    
    logger.warning("[BUYBOX FIELD FAILURE] Availability not found.")
    return NOT_MENTIONED


# ----------------------------------------------------------------------------
# Delivery
# ----------------------------------------------------------------------------

def extract_delivery(row):
    """
    Extract delivery information.
    """
    selectors = [
        "#deliveryBlockSmallMessage span[data-csa-c-type='element']",
        "#deliveryBlockMessage span[data-csa-c-type='element']",
        "#deliveryBlockSmallMessage",
        "#deliveryBlockMessage",
    ]

    for idx, selector in enumerate(selectors, start=1):
        tag = row.select_one(selector)
        value = clean_text(tag)
        if is_valid(value):
            logger.info("[BUYBOX FIELD SUCCESS] Delivery strategy %d: %s", idx, value)
            return value

    # Keyword fallback
    for tag in row.find_all("span"):
        value = clean_text(tag)
        if not is_valid(value):
            continue
        lower = value.lower()
        if any(kw in lower for kw in ["delivery", "arrives", "get it by", "shipping"]):
            logger.info("[BUYBOX FIELD SUCCESS] Delivery keyword fallback: %s", value)
            return value

    return NOT_MENTIONED


# ----------------------------------------------------------------------------
# Seller / Shipper
# ----------------------------------------------------------------------------

def extract_seller_info(row):
    """
    Extract: Sold by, Ships from
    Primary pattern: #sfsb_accordion_head -> div.a-row -> span labels/values
    """
    sold_by = NOT_MENTIONED
    shipped_by = NOT_MENTIONED

    # STRATEGY 1: sfsb_accordion_head
    sfsb = row.select_one("#sfsb_accordion_head")
    if sfsb:
        for line in sfsb.select("div.a-row"):
            spans = line.select("span.a-size-small")
            if len(spans) < 2:
                continue
            label = clean_text(spans[0])
            value = clean_text(spans[1])
            if not is_valid(value):
                continue
            label_lower = label.lower()
            if "sold by" in label_lower and sold_by == NOT_MENTIONED:
                sold_by = value
                logger.info("[BUYBOX FIELD SUCCESS] Seller strategy 1: %s", sold_by)
            if "ships from" in label_lower and shipped_by == NOT_MENTIONED:
                shipped_by = value
                logger.info("[BUYBOX FIELD SUCCESS] Shipper strategy 1: %s", shipped_by)

    # STRATEGY 2: merchantInfoFeature_feature_div
    if sold_by == NOT_MENTIONED:
        merchant = row.select_one("#merchantInfoFeature_feature_div")
        if merchant:
            seller_link = merchant.select_one("a#sellerProfileTriggerId")
            if seller_link:
                value = clean_text(seller_link)
                if is_valid(value):
                    sold_by = value
                    logger.info("[BUYBOX FIELD SUCCESS] Seller strategy 2: %s", sold_by)

    # STRATEGY 3: fulfillerInfoFeature_feature_div
    if shipped_by == NOT_MENTIONED:
        fulfiller = row.select_one("#fulfillerInfoFeature_feature_div")
        if fulfiller:
            value_tag = fulfiller.select_one(".offer-display-feature-text-message")
            value = clean_text(value_tag)
            if is_valid(value):
                shipped_by = value
                logger.info("[BUYBOX FIELD SUCCESS] Shipper strategy 2: %s", shipped_by)

    # STRATEGY 4: Seller profile link
    if sold_by == NOT_MENTIONED:
        seller_link = row.select_one("a[href*='/gp/help/seller']")
        if seller_link:
            value = clean_text(seller_link)
            if is_valid(value):
                sold_by = value
                logger.info("[BUYBOX FIELD SUCCESS] Seller strategy 3: %s", sold_by)

    # STRATEGY 5: Regex fallback
    if sold_by == NOT_MENTIONED or shipped_by == NOT_MENTIONED:
        text = clean_text(sfsb if sfsb else row)
        if sold_by == NOT_MENTIONED:
            match = re.search(r"Sold by:\s*(.+?)(?=\s+Ships from:|$)", text, re.IGNORECASE)
            if match:
                sold_by = match.group(1).strip()
                logger.info("[BUYBOX FIELD SUCCESS] Seller regex fallback: %s", sold_by)
        if shipped_by == NOT_MENTIONED:
            match = re.search(r"Ships from:\s*(.+?)(?=\s+Sold by:|$)", text, re.IGNORECASE)
            if match:
                shipped_by = match.group(1).strip()
                logger.info("[BUYBOX FIELD SUCCESS] Shipper regex fallback: %s", shipped_by)

    return sold_by, shipped_by


# ----------------------------------------------------------------------------
# Returns
# ----------------------------------------------------------------------------

def extract_returns(row):
    """
    Extract return policy information from the offer row.
    Strategies:
      1. Look for <span id="creturns-policy-anchor-text"> – usually contains "FREE Returns"
      2. Look for offer-display-feature-name="desktop-return-info" label/value
      3. Look for any text containing "Returns" in offer-display-feature
      4. Regex fallback on row text
    """
    # Strategy 1: explicit anchor
    anchor = row.select_one("#creturns-policy-anchor-text")
    if anchor:
        value = clean_text(anchor)
        if is_valid(value):
            logger.info("[BUYBOX FIELD SUCCESS] Returns strategy 1: %s", value)
            return value

    # Strategy 2: offer-display-feature-name="desktop-return-info"
    feature = row.select_one('[offer-display-feature-name="desktop-return-info"]')
    if feature:
        # The value is usually in .offer-display-feature-text-message
        value_tag = feature.select_one(".offer-display-feature-text-message")
        if value_tag:
            value = clean_text(value_tag)
            if is_valid(value):
                logger.info("[BUYBOX FIELD SUCCESS] Returns strategy 2: %s", value)
                return value
        # or fallback to the whole feature text
        value = clean_text(feature)
        if is_valid(value):
            logger.info("[BUYBOX FIELD SUCCESS] Returns strategy 2 (fallback): %s", value)
            return value

    # Strategy 3: any span with "Returns" label and a value nearby
    for label in row.select("span.a-color-tertiary"):
        if "Return" in label.get_text():
            # Look for next sibling or parent's next div with feature text
            parent = label.parent
            if parent:
                value_tag = parent.find_next("div", class_="offer-display-feature-text")
                if value_tag:
                    value = clean_text(value_tag)
                    if is_valid(value):
                        logger.info("[BUYBOX FIELD SUCCESS] Returns strategy 3: %s", value)
                        return value

    # Strategy 4: text regex
    text = clean_text(row)
    match = re.search(r"Returns[:\s]*([^\n]+)", text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        if is_valid(value):
            logger.info("[BUYBOX FIELD SUCCESS] Returns strategy 4: %s", value)
            return value

    logger.warning("[BUYBOX FIELD FAILURE] Returns not found.")
    return NOT_MENTIONED


# ----------------------------------------------------------------------------
# Payment
# ----------------------------------------------------------------------------

def extract_payment(row):
    """
    Extract payment/security information.
    Strategies:
      1. offer-display-feature-name="desktop-secure-transaction"
      2. Visible "Secure transaction" text
      3. Any span with "Payment" label
      4. Regex fallback
    """
    # Strategy 1: feature name
    feature = row.select_one('[offer-display-feature-name="desktop-secure-transaction"]')
    if feature:
        # Often the value is in .offer-display-feature-text-message
        value_tag = feature.select_one(".offer-display-feature-text-message")
        if value_tag:
            value = clean_text(value_tag)
            if is_valid(value):
                logger.info("[BUYBOX FIELD SUCCESS] Payment strategy 1: %s", value)
                return value
        value = clean_text(feature)
        if is_valid(value):
            logger.info("[BUYBOX FIELD SUCCESS] Payment strategy 1 (fallback): %s", value)
            return value

    # Strategy 2: any anchor with "Secure transaction" text
    for anchor in row.select("a.a-popover-trigger"):
        if "Secure transaction" in anchor.get_text():
            value = clean_text(anchor)
            if is_valid(value):
                logger.info("[BUYBOX FIELD SUCCESS] Payment strategy 2: %s", value)
                return value

    # Strategy 3: label "Payment" and value
    for label in row.select("span.a-color-tertiary"):
        if "Payment" in label.get_text():
            parent = label.parent
            if parent:
                value_tag = parent.find_next("div", class_="offer-display-feature-text")
                if value_tag:
                    value = clean_text(value_tag)
                    if is_valid(value):
                        logger.info("[BUYBOX FIELD SUCCESS] Payment strategy 3: %s", value)
                        return value

    # Strategy 4: regex
    text = clean_text(row)
    match = re.search(r"Payment[:\s]*([^\n]+)", text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        if is_valid(value):
            logger.info("[BUYBOX FIELD SUCCESS] Payment strategy 4: %s", value)
            return value

    logger.warning("[BUYBOX FIELD FAILURE] Payment not found.")
    return NOT_MENTIONED


# ----------------------------------------------------------------------------
# Product Support
# ----------------------------------------------------------------------------

def extract_product_support(row):
    """
    Extract product support information.
    Strategies:
      1. offer-display-feature-name="desktop-support-info"
      2. Any "Product support included" text
      3. Regex fallback
    """
    feature = row.select_one('[offer-display-feature-name="desktop-support-info"]')
    if feature:
        value_tag = feature.select_one(".offer-display-feature-text-message")
        if value_tag:
            value = clean_text(value_tag)
            if is_valid(value):
                logger.info("[BUYBOX FIELD SUCCESS] Product support strategy 1: %s", value)
                return value
        value = clean_text(feature)
        if is_valid(value):
            logger.info("[BUYBOX FIELD SUCCESS] Product support strategy 1 (fallback): %s", value)
            return value

    # Label approach
    for label in row.select("span.a-color-tertiary"):
        if "Support" in label.get_text():
            parent = label.parent
            if parent:
                value_tag = parent.find_next("div", class_="offer-display-feature-text")
                if value_tag:
                    value = clean_text(value_tag)
                    if is_valid(value):
                        logger.info("[BUYBOX FIELD SUCCESS] Product support strategy 2: %s", value)
                        return value

    text = clean_text(row)
    match = re.search(r"Product support[:\s]*([^\n]+)", text, re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        if is_valid(value):
            logger.info("[BUYBOX FIELD SUCCESS] Product support strategy 3: %s", value)
            return value

    logger.warning("[BUYBOX FIELD FAILURE] Product support not found.")
    return NOT_MENTIONED


# ----------------------------------------------------------------------------
# Offer Title Link
# ----------------------------------------------------------------------------

def extract_title_link(row):
    """
    Extract an offer-specific URL associated with the title/condition.
    Strategies:
      1. Look for an anchor inside .accordion-caption or nearby that is not a popover trigger.
      2. Look for an anchor with href containing '/dp/' or '/gp/offer-listing/' inside the row.
      3. Look for any link in offer-display-features container.
      4. Fallback to generic product link? No, we avoid that.
    """
    # Strategy 1: Find anchor in accordion-caption
    caption = row.select_one(".accordion-caption")
    if caption:
        for a in caption.find_all("a", href=True):
            href = a.get("href")
            if href and "javascript" not in href and href != "#":
                # It might be relative, but we'll return it as is – caller can normalize if needed
                value = href.strip()
                if is_valid(value):
                    logger.info("[BUYBOX FIELD SUCCESS] Title link strategy 1: %s", value)
                    return value

    # Strategy 2: Search entire row for a link that looks like an offer link
    for a in row.find_all("a", href=True):
        href = a.get("href")
        if href and ("/dp/" in href or "/gp/offer-listing/" in href or "/gp/product/" in href):
            # Avoid popover triggers (usually have href="javascript:void(0)" or "#")
            if "javascript" not in href and href != "#":
                value = href.strip()
                if is_valid(value):
                    logger.info("[BUYBOX FIELD SUCCESS] Title link strategy 2: %s", value)
                    return value

    # Strategy 3: Look for any link in offer-display-features container
    feature_container = row.select_one(".offer-display-features-container")
    if feature_container:
        for a in feature_container.find_all("a", href=True):
            href = a.get("href")
            if href and "javascript" not in href and href != "#":
                value = href.strip()
                if is_valid(value):
                    logger.info("[BUYBOX FIELD SUCCESS] Title link strategy 3: %s", value)
                    return value

    # Strategy 4: Look for a link inside any element with class "a-link-normal" that seems offer-related
    for a in row.select("a.a-link-normal"):
        href = a.get("href")
        if href and "javascript" not in href and href != "#":
            # Avoid seller profile links (they contain seller ID)
            if "/gp/help/seller" not in href:
                value = href.strip()
                if is_valid(value):
                    logger.info("[BUYBOX FIELD SUCCESS] Title link strategy 4: %s", value)
                    return value

    logger.warning("[BUYBOX FIELD FAILURE] Title link not found.")
    return NOT_MENTIONED


# ----------------------------------------------------------------------------
# Active Buy Box Detection
# ----------------------------------------------------------------------------

def is_active_buybox_row(row):
    """
    Determine whether Amazon marked this buying option as active.
    """
    classes = row.get("class", [])
    if "a-accordion-active" in classes:
        return True
    if row.get("data-csa-c-is-in-initial-active-row") == "true":
        return True
    if row.select_one('[data-csa-c-is-in-initial-active-row="true"]'):
        return True
    return False


# ----------------------------------------------------------------------------
# Offer Validation
# ----------------------------------------------------------------------------

def validate_offer(offer):
    """
    Validate an extracted offer.
    A valid Amazon offer should have at least:
        condition/title OR price OR seller
    """
    successful_fields = []

    if is_valid(offer.get("title")):
        successful_fields.append("condition")
    if is_valid(offer.get("price")):
        successful_fields.append("price")
    if is_valid(offer.get("availability")):
        successful_fields.append("availability")
    if is_valid(offer.get("delivery")):
        successful_fields.append("delivery")
    if is_valid(offer.get("sold_by")):
        successful_fields.append("seller")
    if is_valid(offer.get("shipped_by")):
        successful_fields.append("shipper")

    valid = len(successful_fields) >= 2

    if valid:
        logger.info("[BUYBOX SUCCESS #8] Offer validated: %s", ", ".join(successful_fields))
    else:
        logger.warning("[BUYBOX FAILURE] Offer rejected. Only detected: %s", ", ".join(successful_fields))

    return valid, successful_fields


# ----------------------------------------------------------------------------
# Single Offer Extraction
# ----------------------------------------------------------------------------

def extract_single_offer(row):
    """
    Extract one Amazon buying option, including all fields needed for the formatted output.
    """
    index = row.get(OFFER_ROW_ATTRIBUTE, NOT_MENTIONED)

    # Existing basic fields
    title = extract_condition(row)
    price = extract_price(row)
    availability = extract_availability(row)
    delivery = extract_delivery(row)
    sold_by, shipped_by = extract_seller_info(row)

    # New fields
    title_link = extract_title_link(row)
    returns = extract_returns(row)
    payment = extract_payment(row)
    product_support = extract_product_support(row)

    offer = {
        "index": index,
        "title": title,
        "title_link": title_link,
        "price": price,
        "availability": availability,
        "delivery": delivery,
        "sold_by": sold_by,
        "shipped_by": shipped_by,
        "condition": title,               # Usually same as title, but kept explicit
        "returns": returns,
        "payment": payment,
        "product_support": product_support,
        "active": is_active_buybox_row(row),
    }

    valid, successful_fields = validate_offer(offer)
    offer["valid"] = valid
    offer["successful_fields"] = successful_fields

    return offer


# ----------------------------------------------------------------------------
# High‑Level Buy Box Extraction
# ----------------------------------------------------------------------------

def extract_buybox(soup):
    """
    Main Buy Box extraction function.
    NOW SUPPORTS: Multi-accordion (existing) + Single offer (new)
    
    ENHANCEMENTS:
    - Robust exception handling (doesn't crash on malformed HTML)
    - Detailed logging for single-offer detection
    - Proper deduplication for both scenarios
    
    Returns:
        dict with keys: offers, primary, active_index, offer_count, 
                       success, success_details
    """
    result = {
        "offers": [],
        "primary": None,
        "active_index": NOT_MENTIONED,
        "offer_count": 0,
        "success": False,
        "success_details": [],
        "detection_mode": None,  # NEW: track if single or multi
    }

    try:
        # ============================================================
        # STEP 1: Find container (now supports single detection)
        # ============================================================
        container = find_buybox_container(soup)
        if not container:
            logger.warning("[BUYBOX] No container found")
            return result

        result["success_details"].append("Buy Box container detected")

        # ============================================================
        # STEP 2: Validate container and detect mode
        # ============================================================
        has_buybox_attribute = container.get("data-a-accordion-name") == BUYBOX_ATTRIBUTE
        has_buying_rows = bool(container.find("div", attrs={OFFER_ROW_ATTRIBUTE: True}))
        is_single_offer = not has_buying_rows  # NEW: single-offer indicator
        
        if has_buybox_attribute:
            result["success_details"].append("Amazon buybox-accordion attribute validated")
        
        if has_buying_rows:
            result["success_details"].append("Multi-accordion buying-option rows validated")
            result["detection_mode"] = "multi-accordion"
        else:
            result["success_details"].append("Single offer mode (no indexed rows)")
            result["detection_mode"] = "single-offer"

        # ============================================================
        # STEP 3: Get rows (handles both multi and single)
        # ============================================================
        rows = find_offer_rows(container)
        if not rows:
            logger.warning("[BUYBOX] No offer rows found after detection")
            return result

        # ============================================================
        # STEP 4: Extract offers with exception handling
        # ============================================================
        seen_indexes = set()

        for row_idx, row in enumerate(rows):
            try:
                offer = extract_single_offer(row)
                if not offer.get("valid"):
                    logger.debug(
                        "[BUYBOX] Row %d marked invalid: %s",
                        row_idx,
                        offer.get("successful_fields", [])
                    )
                    continue

                # Deduplicate based on index
                idx = offer.get("index", NOT_MENTIONED)
                if idx is None or idx == NOT_MENTIONED:
                    logger.warning("[BUYBOX] Offer row has no index; skipping")
                    continue

                if idx in seen_indexes:
                    logger.debug("[BUYBOX] Duplicate accordion row skipped: %s", idx)
                    continue

                seen_indexes.add(idx)
                result["offers"].append(offer)

                logger.info(
                    "[BUYBOX OFFER %s] title=%s | price=%s | avail=%s | seller=%s | shipped=%s",
                    idx,
                    offer.get("title"),
                    offer.get("price"),
                    offer.get("availability"),
                    offer.get("sold_by"),
                    offer.get("shipped_by"),
                )

            except Exception as exc:
                logger.warning(
                    "[BUYBOX] Row %d extraction failed: %s",
                    row_idx,
                    exc
                )
                # Don't crash; continue to next row
                continue

        # ============================================================
        # STEP 5: Count offers
        # ============================================================
        result["offer_count"] = len(result["offers"])
        if result["offer_count"] > 0:
            result["success_details"].append(
                f"{result['offer_count']} valid offer(s) extracted"
            )

        # ============================================================
        # STEP 6: Find primary offer
        # ============================================================
        if result["offers"]:
            # Prefer active offer, fallback to first
            active_offer = next(
                (o for o in result["offers"] if o.get("active")),
                None
            )

            if active_offer:
                result["primary"] = active_offer
                result["active_index"] = active_offer.get("index", NOT_MENTIONED)
                result["success_details"].append("Active offer identified")
            else:
                result["primary"] = result["offers"][0]
                result["active_index"] = result["offers"][0].get("index", NOT_MENTIONED)
                result["success_details"].append("First offer used as primary (no explicit active)")

        # ============================================================
        # STEP 7: Final success determination
        # ============================================================
        if result["offer_count"] > 0 and result["primary"] is not None:
            result["success"] = True
            logger.info(
                "[BUYBOX SUCCESS] Offers=%d | ActiveIndex=%s | Mode=%s",
                result["offer_count"],
                result["active_index"],
                result.get("detection_mode", "unknown")
            )
        else:
            logger.warning("[BUYBOX] No valid offers extracted")

        return result

    except Exception as exc:
        logger.exception(f"[BUYBOX] Unexpected error in extract_buybox(): {exc}")
        result["success_details"].append(f"Exception: {str(exc)}")
        return result


# ----------------------------------------------------------------------------
# Output Formatters
# ----------------------------------------------------------------------------

def format_offer_lines(offers, field):
    values = []
    for offer in offers:
        value = offer.get(field, NOT_MENTIONED)
        if is_valid(value):
            values.append(str(value).strip())
    return "\n".join(values) if values else NOT_MENTIONED


def format_buybox_full(offers):
    if not offers:
        return NOT_MENTIONED

    blocks = []
    for number, offer in enumerate(offers, start=1):
        blocks.append(
            "\n".join([
                f"Offer {number}",
                f"Index: {offer.get('index', NOT_MENTIONED)}",
                f"Condition: {offer.get('title', NOT_MENTIONED)}",
                f"Price: {offer.get('price', NOT_MENTIONED)}",
                f"Availability: {offer.get('availability', NOT_MENTIONED)}",
                f"Delivery: {offer.get('delivery', NOT_MENTIONED)}",
                f"Sold by: {offer.get('sold_by', NOT_MENTIONED)}",
                f"Shipped by: {offer.get('shipped_by', NOT_MENTIONED)}",
                f"Active: {offer.get('active', False)}",
            ])
        )

    return "\n\n" + ("\n\n----------------------------------------\n\n").join(blocks)


def format_buybox_formatted_offers(offers):
    """
    Format a list of offer dicts into a rich human-readable string.
    Each offer is displayed with all fields except Link and Payment (removed per user request).
    """
    if not offers:
        return NOT_MENTIONED

    blocks = []
    for number, offer in enumerate(offers, start=1):
        block_lines = [
            f"Offer {number}",
            f"Title: {offer.get('title', NOT_MENTIONED)}",
            f"Price: {offer.get('price', NOT_MENTIONED)}",
            f"Ships from: {offer.get('shipped_by', NOT_MENTIONED)}",
            f"Sold by: {offer.get('sold_by', NOT_MENTIONED)}",
            f"Condition: {offer.get('condition', NOT_MENTIONED)}",
            f"Returns: {offer.get('returns', NOT_MENTIONED)}",
            f"Delivery: {offer.get('delivery', NOT_MENTIONED)}",
            f"Availability: {offer.get('availability', NOT_MENTIONED)}",
            f"Product Support: {offer.get('product_support', NOT_MENTIONED)}",
        ]
        blocks.append("\n".join(block_lines))

    return "\n\n----------------------------------------\n\n".join(blocks)


# ----------------------------------------------------------------------------
# Product Data Mapping
# ----------------------------------------------------------------------------

def map_buybox_to_product_data(data, buybox):
    """
    Populate all BuyBox fields in the data dictionary.
    This includes the new "BuyBox Formatted Offers" column.
    """
    offers = buybox.get("offers", [])
    primary = buybox.get("primary")

    # Initialize all fields
    data["BuyBox"] = NOT_MENTIONED
    data["BuyBox_Offers"] = NOT_MENTIONED
    data["BuyBox_Offer_Count"] = 0
    data["BuyBox_Prices"] = NOT_MENTIONED
    data["BuyBox_Sellers"] = NOT_MENTIONED

    data["BuyBox_Title"] = NOT_MENTIONED
    data["BuyBox_Price"] = NOT_MENTIONED
    data["BuyBox_Availability"] = NOT_MENTIONED
    data["BuyBox_Delivery"] = NOT_MENTIONED
    data["BuyBox_Sold_By"] = NOT_MENTIONED
    data["BuyBox_Shipped_By"] = NOT_MENTIONED

    data["BuyBox_Active_Index"] = NOT_MENTIONED
    data["BuyBox_Success"] = False
    data["BuyBox_Success_Details"] = NOT_MENTIONED

    # New field
    data["BuyBox Formatted Offers"] = NOT_MENTIONED

    if not offers:
        return data

    # All offers
    data["BuyBox"] = format_buybox_full(offers)
    data["BuyBox_Offers"] = format_offer_lines(offers, "title")
    data["BuyBox_Offer_Count"] = len(offers)
    data["BuyBox_Prices"] = format_offer_lines(offers, "price")
    data["BuyBox_Sellers"] = format_offer_lines(offers, "sold_by")

    # New formatted offers (without Link and Payment)
    data["BuyBox Formatted Offers"] = format_buybox_formatted_offers(offers)

    # Primary/active offer
    if primary:
        data["BuyBox_Title"] = primary.get("title", NOT_MENTIONED)
        data["BuyBox_Price"] = primary.get("price", NOT_MENTIONED)
        data["BuyBox_Availability"] = primary.get("availability", NOT_MENTIONED)
        data["BuyBox_Delivery"] = primary.get("delivery", NOT_MENTIONED)
        data["BuyBox_Sold_By"] = primary.get("sold_by", NOT_MENTIONED)
        data["BuyBox_Shipped_By"] = primary.get("shipped_by", NOT_MENTIONED)
        data["BuyBox_Active_Index"] = primary.get("index", NOT_MENTIONED)

    # Success
    data["BuyBox_Success"] = True
    details = buybox.get("success_details", [])
    if details:
        data["BuyBox_Success_Details"] = " | ".join(details)

    logger.info(
        "[BUYBOX PRODUCT DATA SUCCESS] Offers=%s | Prices=%s | Sellers=%s",
        data["BuyBox_Offer_Count"],
        data["BuyBox_Prices"],
        data["BuyBox_Sellers"]
    )

    return data

# ============================================================================
# Specialized Extraction Functions
# ============================================================================

def extract_item_details(item_detail_element):
    """Extract all key-value rows from an Amazon 'item_details' section element."""
    pairs = []
    try:
        try:
            raw_html = item_detail_element.get_attribute("outerHTML")
        except Exception as e:
            logging.debug(f"Could not read element HTML: {e}")
            return "Not Mentioned"
        try:
            soup = BeautifulSoup(raw_html, "lxml")
        except Exception as e:
            logging.debug(f"BeautifulSoup parse error: {e}")
            return "Not Mentioned"
        table = soup.find("table", class_=re.compile(r"a-keyvalue"))
        if not table:
            return "Not Mentioned"
        rows = table.find_all("tr")
        if not rows:
            return "Not Mentioned"
        for row in rows:
            try:
                th = row.find("th")
                td = row.find("td")
                if not th or not td:
                    continue
                key = safe_text(th)
                # Special case: Best Sellers Rank
                if "best sellers rank" in key.lower():
                    try:
                        items = td.find_all("li")
                        if items:
                            rank_parts = []
                            for li in items:
                                rank_text = re.sub(r"\s+", " ", li.get_text(" ", strip=True))
                                rank_parts.append(rank_text)
                            value = " | ".join(rank_parts)
                        else:
                            value = safe_text(td)
                    except Exception as e:
                        logging.debug(f"Best Sellers Rank parse error: {e}")
                        value = safe_text(td)
                # Special case: Customer Reviews
                elif "customer reviews" in key.lower():
                    try:
                        star_tag = td.find(attrs={"title": re.compile(r"\d+\.\d+ out of \d+ stars")})
                        count_tag = td.find(attrs={"aria-label": re.compile(r"\d+ Reviews", re.I)})
                        stars = star_tag.get("title", "").strip() if star_tag else ""
                        count = count_tag.get("aria-label", "").strip() if count_tag else ""
                        if not stars:
                            raw = td.get_text(" ", strip=True)
                            m = re.search(r"(\d+\.\d+)\s+out of\s+\d+\s+stars", raw, re.I)
                            stars = f"{m.group(1)} out of 5 stars" if m else ""
                        if not count:
                            raw = td.get_text(" ", strip=True)
                            m = re.search(r"\((\d+)\)", raw)
                            count = f"{m.group(1)} Reviews" if m else ""
                        parts = [p for p in [stars, count] if p]
                        value = ", ".join(parts) if parts else safe_text(td)
                    except Exception as e:
                        logging.debug(f"Customer Reviews parse error: {e}")
                        value = safe_text(td)
                else:
                    value = safe_text(td)
                if key != "Not Mentioned" and value != "Not Mentioned":
                    pairs.append((key, value))
            except Exception as e:
                logging.debug(f"Row parse error: {e}")
                continue
    except Exception as e:
        logging.debug(f"Unexpected error in extract_item_details: {e}")
        return "Not Mentioned"
    return boundary_format(pairs)


def scrape_tr_table(soup) -> str:
    """Parse all <tr> tags from a BeautifulSoup object into keyword format."""
    try:
        rows = soup.find_all("tr")
    except Exception as e:
        logger.debug(f"scrape_tr_table could not find rows: {e}")
        return "Not Mentioned"
    lines = []
    seen_labels = set()
    for tr in rows:
        try:
            ths = tr.find_all("th")
            tds = tr.find_all("td")
            if ths and tds:
                left = ths[0].get_text(strip=True)
                right = tds[0].get_text(strip=True)
            elif len(tds) >= 2:
                left = tds[0].get_text(strip=True)
                right = tds[1].get_text(strip=True)
            elif len(ths) >= 2:
                left = ths[0].get_text(strip=True)
                right = ths[1].get_text(strip=True)
            elif ths:
                left = ths[0].get_text(strip=True)
                right = ""
            elif tds:
                left = ""
                right = tds[0].get_text(strip=True)
            else:
                continue
            left = safe_str(left, default="")
            right = safe_str(right, default="Not Mentioned")
            if not left and not right:
                continue
            label_key = left.lower()
            if label_key in seen_labels:
                continue
            seen_labels.add(label_key)
            lines.append(f"{left} | {right}")
        except Exception as e:
            logger.debug(f"scrape_tr_table row parse error: {e}")
            continue
    separator = "\n" + "-" * 31 + "\n"
    result = separator.join(lines)
    return result if result else "Not Mentioned"


def extract_variation_asins(source, base_url="https://www.amazon.com"):
    """Extract variation ASINs from product page."""
    try:
        soup = source
        twister = soup.find("div", id="twister_feature_div")
        if not twister:
            return "Not Mentioned"
        script = twister.find("script", attrs={"type": "a-state"})
        if not script:
            return "Not Mentioned"
        data = json.loads(script.string)
        variations = data.get("sortedDimValuesForAllDims", {})
        asins = set()
        for dim_name, options in variations.items():
            for opt in options:
                asin = opt.get("defaultAsin")
                if asin:
                    asins.add(asin)
                page_url = opt.get("pageLoadURL")
                if page_url and "/dp/" in page_url:
                    parts = page_url.split("/dp/")
                    if len(parts) > 1:
                        asin_from_url = parts[1].split("/")[0]
                        asins.add(asin_from_url)
        if not asins:
            return "Not Mentioned"
        return "\n".join([f"{base_url}/dp/{asin}" for asin in asins])
    except:
        return "Not Mentioned"


# ============================================================================
# Main Scraping Function with Timeout and Cancellation Support
# ============================================================================

def scrape_product(driver, url: str, wait: int = 150, cancel_check=None, **kwargs) -> ProductData:
    """
    Scrape a single Amazon product page and return a ProductData object.
    
    Parameters:
        driver: selenium.webdriver.Chrome WebDriver instance
        url: Product URL to scrape
        wait: Wait time in seconds before starting extraction
        cancel_check: Optional callable that returns True if cancellation requested
        url_timeout: Maximum time allowed for the entire URL processing (default 60)
    
    Returns:
        ProductData: Structured product data object
    """
    url = safe_str(url, default="Not Mentioned")
    url_timeout = kwargs.get('url_timeout', 60)
    try:
        return _scrape_product_page(driver, url, wait, cancel_check, url_timeout)
    except Exception as e:
        logger.error(f"scrape_product failed for {url}: {e}")
        return ProductData.create_fallback(url=url, error=str(e))

def extract_store_fallback(soup):
    """
    Fallback Store extraction.

    Order:
    1. "Visit the..." anchor with a-link-normal class
    2. Brand label/value
    3. Not Mentioned

    Returns:
        tuple: (store_name, store_link)
    """
    try:
        # ---------------------------------------------------------
        # FALLBACK 1: "Visit the..." anchor
        # ---------------------------------------------------------
        anchors = soup.find_all(
            "a",
            class_="a-link-normal"
        )

        for anchor in anchors:
            try:
                text = safe_text(anchor)

                if (
                    text != "Not Mentioned"
                    and "visit the" in text.lower()
                ):
                    href = safe_attr(
                        anchor,
                        "href"
                    )

                    return text, href

            except Exception as e:
                logger.debug(
                    f"Store Visit-the anchor parse error: {e}"
                )
                continue

        # ---------------------------------------------------------
        # FALLBACK 2: Brand
        # ---------------------------------------------------------
        for tr in soup.find_all("tr"):
            try:
                tds = tr.find_all("td")

                if len(tds) >= 2:
                    label = safe_text(tds[0]).strip()
                    value = safe_text(tds[1]).strip()

                    if (
                        label.lower() == "brand"
                        and value != "Not Mentioned"
                    ):
                        return value, "Not Mentioned"

            except Exception as e:
                logger.debug(
                    f"Store Brand fallback parse error: {e}"
                )
                continue

        # ---------------------------------------------------------
        # Nothing found
        # ---------------------------------------------------------
        return "Not Mentioned", "Not Mentioned"

    except Exception as e:
        logger.warning(
            f"Store fallback extraction failed: {e}"
        )

        return "Not Mentioned", "Not Mentioned"


def extract_brand_fallback(soup):
    """
    Fallback extraction for Brand.

    Looks for a Brand label in Amazon's product information/detail
    sections and returns the associated value.

    Returns:
        str: Brand name or "Not Mentioned"
    """
    try:
        # ---------------------------------------------------------
        # Strategy 1: productOverview_feature_div
        # ---------------------------------------------------------
        overview = soup.find(
            "div",
            id="productOverview_feature_div"
        )

        if overview:
            for tr in overview.find_all("tr"):
                try:
                    tds = tr.find_all("td")

                    if len(tds) >= 2:
                        label = safe_text(tds[0]).strip()
                        value = safe_text(tds[1]).strip()

                        if (
                            label.lower() == "brand"
                            and value != "Not Mentioned"
                        ):
                            return value

                except Exception as e:
                    logger.debug(
                        f"Brand overview row parse error: {e}"
                    )
                    continue

        # ---------------------------------------------------------
        # Strategy 2: product details tables
        # ---------------------------------------------------------
        for tr in soup.find_all("tr"):
            try:
                tds = tr.find_all("td")

                if len(tds) >= 2:
                    label = safe_text(tds[0]).strip()
                    value = safe_text(tds[1]).strip()

                    if (
                        label.lower() == "brand"
                        and value != "Not Mentioned"
                    ):
                        return value

            except Exception as e:
                logger.debug(
                    f"Brand table row parse error: {e}"
                )
                continue

        # ---------------------------------------------------------
        # Strategy 3: common Amazon detail elements
        # ---------------------------------------------------------
        brand_label = soup.find(
            string=lambda text: (
                text
                and text.strip().lower() == "brand"
            )
        )

        if brand_label:
            try:
                parent = brand_label.parent

                if parent:
                    # Look for nearby value
                    value_element = parent.find_next()

                    if value_element:
                        value = safe_text(value_element)

                        if value != "Not Mentioned":
                            return value

            except Exception as e:
                logger.debug(
                    f"Brand label fallback parse error: {e}"
                )

    except Exception as e:
        logger.warning(
            f"Brand fallback extraction failed: {e}"
        )

    return "Not Mentioned"


def _scrape_product_page(driver, url: str, wait: int, cancel_check=None, url_timeout: int = 60) -> ProductData:
    """
    Internal scrape implementation; callers should use scrape_product().
    """
    # --- Diagnostic logging ---
    logger.info(f"[worker] Starting URL: {url}")

    # Set page load and script timeouts using the provided url_timeout
    driver.set_page_load_timeout(url_timeout)  # Use the passed timeout
    driver.set_script_timeout(url_timeout)     # Same timeout for scripts

    # --- Navigation ---
    logger.info("[worker] Calling driver.get()")
    try:
        driver.get(url)
        logger.info("[worker] driver.get() returned")
    except TimeoutException as e:
        logger.error(f"[worker] Page load timed out after {url_timeout}s: {url}")
        # Re-raise the TimeoutException so the worker can handle it
        raise
    except WebDriverException as e:
        logger.error(f"[worker] WebDriver error during navigation: {e}")
        raise RuntimeError(f"WebDriver error loading page: {e}") from e
    except Exception as e:
        logger.error(f"[worker] Unexpected error during navigation: {e}")
        raise RuntimeError(f"Could not load page: {e}") from e

    # Check cancellation after page load
    if cancel_check and cancel_check():
        logger.info("[worker] Cancellation detected after navigation")
        raise RuntimeError("Scraping cancelled during page load")

    # --- Progressive wait with cancellation checks ---
    if wait > 0:
        logger.info(f"[worker] Starting page wait: {wait} seconds")
        interval = 1  # Check cancellation every second
        elapsed = 0
        while elapsed < wait:
            if cancel_check and cancel_check():
                logger.info("[worker] Cancellation detected during wait")
                raise RuntimeError("Scraping cancelled during wait")
            time.sleep(min(interval, wait - elapsed))
            elapsed += interval
        logger.info("[worker] Page wait completed")

    # --- Page extraction ---
    logger.info("[worker] Starting page extraction")

    # Read page source with a timeout (using JavaScript to get HTML if needed)
    logger.info("[worker] extraction: reading page_source - START")
    try:
        # Set a short timeout for page_source retrieval
        source = driver.page_source
        logger.info("[worker] extraction: reading page_source - DONE")
    except Exception as e:
        logger.error(f"[worker] Failed to get page source: {e}")
        raise RuntimeError(f"Could not get page source: {e}")

    try:
        soup = BeautifulSoup(source, "lxml")
        logger.info("[worker] extraction: BeautifulSoup parsing - DONE")
    except Exception as e:
        logger.error(f"[worker] Failed to parse page HTML: {e}")
        raise RuntimeError(f"Could not parse page HTML: {e}")

    # Initialize with all defaults
    data = {
        'Product Link': url,
        'ASIN': extract_asin(url),
    }

    # --- Title ---
    logger.info("[worker] extraction: locating title - START")
    title_tag = soup.find("span", id="productTitle")
    data['Title'] = safe_text(title_tag)
    logger.info("[worker] extraction: locating title - DONE")

    # --- Store information ---
    # logger.info("[worker] extraction: locating store - START")
    # store = soup.find("a", id="bylineInfo")
    # data['Store Name'] = safe_text(store)
    # href = safe_attr(store, "href")
    # data['Store Link'] = href if href != "Not Mentioned" else "Not Mentioned"
    # logger.info("[worker] extraction: locating store - DONE")
    
    # --- Store information ---
    logger.info("[worker] extraction: locating store - START")

    try:
        # PRIMARY STRATEGY — preserve existing logic
        store = soup.find(
            "a",
            id="bylineInfo"
        )

        store_name = safe_text(store)
        store_link = safe_attr(
            store,
            "href"
        )

        # ---------------------------------------------------------
        # FALLBACK STRATEGY
        #
        # 1. Visit the...
        # 2. Brand
        # ---------------------------------------------------------
        if (
            store_name == "Not Mentioned"
            or store_link == "Not Mentioned"
        ):
            fallback_name, fallback_link = (
                extract_store_fallback(soup)
            )

            if (
                store_name == "Not Mentioned"
                and fallback_name != "Not Mentioned"
            ):
                store_name = fallback_name

            if (
                store_link == "Not Mentioned"
                and fallback_link != "Not Mentioned"
            ):
                store_link = fallback_link

        data['Store Name'] = store_name
        data['Store Link'] = store_link

    except Exception as e:
        logger.warning(
            f"[worker] Store extraction failed: {e}"
        )

        data['Store Name'] = "Not Mentioned"
        data['Store Link'] = "Not Mentioned"

    logger.info(
        "[worker] extraction: locating store - DONE"
    )

    # --- Ratings ---
    logger.info("[worker] extraction: locating ratings - START")
    rating = soup.find("span", id="acrPopover")
    if rating:
        data['Ratings'] = rating.get("title") or safe_text(rating.find("a"))
    else:
        data['Ratings'] = "Not Mentioned"
    logger.info("[worker] extraction: locating ratings - DONE")

    # --- Reviews ---
    logger.info("[worker] extraction: locating reviews - START")
    reviews = soup.find("span", id="acrCustomerReviewText")
    data['Reviews'] = safe_attr(reviews, "aria-label")
    logger.info("[worker] extraction: locating reviews - DONE")

    # --- Price ---
    logger.info("[worker] extraction: locating price - START")
    price = soup.find("div", id="corePriceDisplay_desktop_feature_div")
    data['Price Box'] = safe_text(price)
    logger.info("[worker] extraction: locating price - DONE")


        # --- Description ---
    logger.info(
        "[worker] extraction: locating description - START"
    )

    try:
        bullets = soup.find(
            "div",
            id="feature-bullets"
        )

        if bullets:
            ul = bullets.find("ul")

            if ul:
                bullet_items = []

                for li in ul.find_all("li"):
                    try:
                        value = safe_text(li)

                        if (
                            value != "Not Mentioned"
                            and value.strip()
                        ):
                            bullet_items.append(
                                f"• {value.strip()}"
                            )

                    except Exception as e:
                        logger.debug(
                            f"Description bullet parse error: {e}"
                        )
                        continue

                data['Description'] = (
                    "\n".join(bullet_items)
                    if bullet_items
                    else safe_text(ul)
                )

            else:
                data['Description'] = safe_text(
                    bullets
                )

        else:
            data['Description'] = "Not Mentioned"

    except Exception as e:
        logger.warning(
            f"[worker] Description extraction failed: {e}"
        )

        data['Description'] = "Not Mentioned"

    logger.info(
        "[worker] extraction: locating description - DONE"
    )


    # --- Top Highlights from poExpander (requires JavaScript click) ---
    logger.info(
        "[worker] extraction: top highlights - START"
    )

    item_pairs = []
    top_highlight_value = "Not Mentioned"

    try:

        # -------------------------------------------------------------
        # 1. Locate the toggle button
        # -------------------------------------------------------------
        logger.info(
            "[worker] extraction: looking for poToggleButton - START"
        )

        try:

            toggle_div = driver.find_element(
                By.ID,
                "poToggleButton"
            )

            toggle_anchor = (
                toggle_div.find_element(
                    By.TAG_NAME,
                    "a"
                )
                if toggle_div
                else None
            )

        except NoSuchElementException:

            toggle_div = None
            toggle_anchor = None

        except Exception as e:

            logger.warning(
                "[worker] Error locating poToggleButton: "
                f"{e}"
            )

            toggle_div = None
            toggle_anchor = None

        logger.info(
            "[worker] extraction: looking for poToggleButton - DONE"
        )


        # -------------------------------------------------------------
        # 2. Click the toggle if available
        # -------------------------------------------------------------
        if toggle_anchor:

            logger.info(
                "[worker] extraction: attempting to click toggle - START"
            )

            try:

                wait_obj = WebDriverWait(
                    driver,
                    10
                )

                clickable_toggle = wait_obj.until(
                    EC.element_to_be_clickable(
                        toggle_anchor
                    )
                )

                driver.execute_script(
                    "arguments[0].click();",
                    clickable_toggle
                )

                logger.info(
                    "[worker] extraction: toggle clicked successfully"
                )

                # Give Amazon time to render expanded content.
                time.sleep(1)

                # -----------------------------------------------------
                # IMPORTANT:
                #
                # soup was created BEFORE the JavaScript click.
                #
                # Refresh it so the expanded Amazon HTML becomes
                # available to BeautifulSoup.
                # -----------------------------------------------------
                try:

                    source = driver.page_source

                    soup = BeautifulSoup(
                        source,
                        "lxml"
                    )

                    logger.info(
                        "[worker] extraction: refreshed page source "
                        "after top highlights expansion"
                    )

                except Exception as e:

                    logger.warning(
                        "[worker] Failed to refresh soup after "
                        f"top highlights expansion: {e}"
                    )

            except TimeoutException:

                logger.warning(
                    "[worker] Toggle click timed out, "
                    "proceeding without expanding"
                )

            except Exception as e:

                logger.warning(
                    "[worker] Toggle click failed: "
                    f"{e}, proceeding without expanding"
                )

            logger.info(
                "[worker] extraction: attempting to click toggle - DONE"
            )


        # -------------------------------------------------------------
        # 3. EXISTING STRATEGY:
        # poExpander
        # -------------------------------------------------------------
        try:

            expander = soup.find(
                "div",
                id="poExpander"
            )

            if expander:

                logger.info(
                    "[worker] extraction: found poExpander"
                )

                for tr in expander.find_all("tr"):

                    try:

                        tds = tr.find_all("td")

                        if len(tds) == 2:

                            key = safe_text(
                                tds[0]
                            )

                            value = safe_text(
                                tds[1]
                            )

                            if (
                                key != "Not Mentioned"
                                and value != "Not Mentioned"
                            ):

                                item_pairs.append(
                                    (
                                        key,
                                        value
                                    )
                                )

                    except Exception as e:

                        logger.debug(
                            "[worker] Error processing "
                            f"poExpander row: {e}"
                        )

                        continue

            else:

                # -----------------------------------------------------
                # 4. EXISTING FALLBACK:
                # po rows / a-spacing-small
                # -----------------------------------------------------
                logger.info(
                    "[worker] extraction: poExpander not found, "
                    "trying po rows fallback"
                )

                try:

                    rows = soup.find_all(
                        "tr",
                        class_=re.compile(
                            "a-spacing-small"
                        ),
                        role="listitem"
                    )

                    for r in rows:

                        try:

                            if "po" not in r.get(
                                "class",
                                []
                            ):
                                continue

                            spans = r.find_all(
                                "span"
                            )

                            if len(spans) >= 2:

                                key = safe_text(
                                    spans[0]
                                )

                                value = safe_text(
                                    spans[1]
                                )

                                if (
                                    key != "Not Mentioned"
                                    and value != "Not Mentioned"
                                ):

                                    item_pairs.append(
                                        (
                                            key,
                                            value
                                        )
                                    )

                        except Exception as e:

                            logger.debug(
                                "[worker] Error processing po row: "
                                f"{e}"
                            )

                            continue

                except Exception as e:

                    logger.warning(
                        "[worker] po rows fallback failed: "
                        f"{e}"
                    )

        except Exception as e:

            logger.warning(
                "[worker] poExpander extraction failed: "
                f"{e}"
            )


        # -------------------------------------------------------------
        # 5. EXISTING FALLBACK:
        # productOverview_feature_div
        # -------------------------------------------------------------
        if not item_pairs:

            logger.info(
                "[worker] extraction: no Top Highlights from "
                "poExpander/po rows, trying productOverview_feature_div"
            )

            try:

                overview = soup.find(
                    "div",
                    id="productOverview_feature_div"
                )

                if overview:

                    for tr in overview.find_all("tr"):

                        try:

                            tds = tr.find_all("td")

                            if len(tds) == 2:

                                key = safe_text(
                                    tds[0]
                                )

                                value = safe_text(
                                    tds[1]
                                )

                                if (
                                    key != "Not Mentioned"
                                    and value != "Not Mentioned"
                                ):

                                    item_pairs.append(
                                        (
                                            key,
                                            value
                                        )
                                    )

                        except Exception as e:

                            logger.debug(
                                "[worker] Error processing "
                                f"productOverview row: {e}"
                            )

                            continue

            except Exception as e:

                logger.warning(
                    "[worker] productOverview_feature_div "
                    f"fallback failed: {e}"
                )


        # -------------------------------------------------------------
        # 6. NEW STRATEGY:
        #
        # #topHighlight contains BOTH:
        #
        #   A. Top Highlights
        #      product-facts-detail
        #
        #   B. About this item
        #      ul -> li -> span.a-list-item
        #
        # IMPORTANT:
        #
        # This does NOT replace any existing strategy.
        #
        # It only runs when the existing Top Highlights strategies
        # did not produce item_pairs.
        # -------------------------------------------------------------
        if not item_pairs:

            logger.info(
                "[worker] extraction: no Top Highlights found "
                "using existing strategies, trying combined "
                "#topHighlight strategy"
            )

            try:

                (
                    combined_top_highlight,
                    combined_about_this_item
                ) = extract_top_highlight_container(
                    soup
                )

                # -----------------------------------------------------
                # 6A. Top Highlights from #topHighlight
                # -----------------------------------------------------
                if (
                    combined_top_highlight
                    and combined_top_highlight
                    != "Not Mentioned"
                ):

                    top_highlight_value = (
                        combined_top_highlight
                    )

                    logger.info(
                        "[worker] extraction: Top Highlights "
                        "found using #topHighlight strategy"
                    )

                # -----------------------------------------------------
                # 6B. About this item from #topHighlight
                #
                # Only use it if the existing Description extraction
                # did NOT already find usable data.
                # -----------------------------------------------------
                if (
                    combined_about_this_item
                    and combined_about_this_item
                    != "Not Mentioned"
                ):

                    existing_description = data.get(
                        "Description",
                        "Not Mentioned"
                    )

                    # Treat all of these as missing:
                    #
                    # None
                    # null
                    # NaN
                    # ""
                    # whitespace
                    # Not Mentioned
                    #
                    description_missing = (
                        existing_description is None
                        or str(
                            existing_description
                        ).strip() == ""
                        or str(
                            existing_description
                        ).strip().lower()
                        in {
                            "none",
                            "null",
                            "nan",
                            "not mentioned",
                        }
                    )

                    if description_missing:

                        data["Description"] = (
                            combined_about_this_item
                        )

                        logger.info(
                            "[worker] extraction: About this item "
                            "found using #topHighlight strategy"
                        )

                    else:

                        logger.debug(
                            "[worker] extraction: existing Description "
                            "already contains data; preserving it"
                        )

            except Exception as e:

                logger.warning(
                    "[worker] #topHighlight combined strategy failed: "
                    f"{e}"
                )


        # -------------------------------------------------------------
        # 7. EXISTING topHighlight FALLBACK
        #
        # IMPORTANT:
        #
        # We KEEP your original extract_top_highlight_div()
        # strategy.
        #
        # It only runs if the new combined strategy did not find
        # Top Highlights.
        # -------------------------------------------------------------
        if (
            not item_pairs
            and top_highlight_value == "Not Mentioned"
        ):

            logger.info(
                "[worker] extraction: trying existing "
                "extract_top_highlight_div fallback"
            )

            try:

                fallback_top_highlight = (
                    extract_top_highlight_div(
                        soup
                    )
                )

                if (
                    fallback_top_highlight
                    and fallback_top_highlight
                    != "Not Mentioned"
                ):

                    top_highlight_value = (
                        fallback_top_highlight
                    )

                    logger.info(
                        "[worker] extraction: Top Highlights "
                        "found using existing topHighlight fallback"
                    )

                else:

                    logger.info(
                        "[worker] extraction: existing "
                        "topHighlight fallback did not "
                        "contain usable data"
                    )

            except Exception as e:

                logger.warning(
                    "[worker] existing topHighlight fallback failed: "
                    f"{e}"
                )

                top_highlight_value = "Not Mentioned"


    except Exception as e:

        logger.warning(
            "[worker] Top highlights extraction failed: "
            f"{e}"
        )

        # -------------------------------------------------------------
        # SAFETY:
        #
        # A failure in Top Highlights extraction must NEVER break
        # extraction of the rest of the product.
        # -------------------------------------------------------------
        item_pairs = []

        if not top_highlight_value:
            top_highlight_value = "Not Mentioned"


    # -------------------------------------------------------------
    # 8. FINAL TOP HIGHLIGHTS VALUE
    # -------------------------------------------------------------
    try:

        if item_pairs:

            # ---------------------------------------------------------
            # Existing successful strategies won.
            # ---------------------------------------------------------
            data['Top Highlights'] = (
                boundary_format(
                    item_pairs
                )
            )

        elif (
            top_highlight_value
            and top_highlight_value
            != "Not Mentioned"
        ):

            # ---------------------------------------------------------
            # #topHighlight or existing helper fallback.
            # ---------------------------------------------------------
            data['Top Highlights'] = (
                top_highlight_value
            )

        else:

            data['Top Highlights'] = (
                "Not Mentioned"
            )

    except Exception as e:

        logger.warning(
            "[worker] Failed to format Top Highlights: "
            f"{e}"
        )

        data['Top Highlights'] = (
            "Not Mentioned"
        )


    logger.info(
        "[worker] extraction: top highlights - DONE"
    )

    # --- Item Details (using Selenium find_element with timeout) ---
    logger.info("[worker] extraction: item details - START")
    item_details_el = None
    try:
        item_details_el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "item_details"))
        )
    except TimeoutException:
        logger.warning("[worker] Item details element not found within 10 seconds")
    except Exception as e:
        logger.warning(f"[worker] Error finding item details: {e}")
    data['Item Details'] = extract_item_details(item_details_el) if item_details_el else "Not Mentioned"
    logger.info("[worker] extraction: item details - DONE")

    # --- Variations ---
    logger.info("[worker] extraction: variations - START")
    data['Variations'] = extract_variation_asins(source=soup)
    logger.info("[worker] extraction: variations - DONE")

    # --- Product Information ---
    logger.info("[worker] extraction: product information - START")
    info_pairs = []
    prod = soup.find("div", id="prodDetails")
    if prod:
        for tr in prod.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                info_pairs.append((safe_text(th), safe_text(td)))
    if not info_pairs:
        prod_alt = soup.find("div", id="productDetails_feature_div")
        if prod_alt:
            for tr in prod_alt.find_all("tr"):
                th = tr.find("th")
                td = tr.find("td")
                if th and td:
                    info_pairs.append((safe_text(th), safe_text(td)))
    data['Product Information'] = boundary_format(info_pairs)
    logger.info("[worker] extraction: product information - DONE")

    # --- Breadcrumbs and Categories ---
    logger.info("[worker] extraction: breadcrumbs - START")
    breadcrumbs = soup.find("div", id="wayfinding-breadcrumbs_feature_div")
    if breadcrumbs:
        spans = breadcrumbs.find_all("span", class_="a-list-item")
        data['Category'] = safe_text(spans[-3]) if len(spans) >= 2 else "Not Mentioned"
        data['Sub Category'] = safe_text(spans[-1]) if spans else "Not Mentioned"
        ul = breadcrumbs.find("ul")
        data['BreadCrumb'] = safe_text(ul)
    else:
        data['Category'] = "Not Mentioned"
        data['Sub Category'] = "Not Mentioned"
        data['BreadCrumb'] = "Not Mentioned"
    logger.info("[worker] extraction: breadcrumbs - DONE")

    # --- Display Features ---
    logger.info("[worker] extraction: display features - START")
    display = soup.find("div", id="offer-display-features")
    data['Display Features'] = safe_text(display)
    logger.info("[worker] extraction: display features - DONE")

    # --- Display Features 1 (detailed) ---
    logger.info("[worker] extraction: display features 1 - START")
    display_features = []
    try:
        display = soup.find("div", id="offer-display-features")
        if display:
            containers = display.find_all("div", class_=re.compile("offer-display-features-container"))
            for container in containers:
                feature_divs = container.find_all("div", recursive=False)
                for feature in feature_divs:
                    try:
                        label_div = feature.find("div", class_=re.compile("offer-display-feature-label"))
                        value_div = feature.find("div", class_=re.compile("offer-display-feature-text"))
                        if not label_div or not value_div:
                            continue
                        label = safe_text(label_div)
                        first_child = value_div.find(recursive=False)
                        value = safe_text(first_child) if first_child else safe_text(value_div)
                        if label != "Not Mentioned" or value != "Not Mentioned":
                            display_features.append(f"{label} | {value}")
                    except:
                        continue
        data['Display Features 1'] = "\n".join(display_features) if display_features else "Not Mentioned"
    except Exception as e:
        logger.warning(f"[worker] Error extracting display features 1: {e}")
        data['Display Features 1'] = "Not Mentioned"
    logger.info("[worker] extraction: display features 1 - DONE")

    # --- Merchant ---
    logger.info("[worker] extraction: merchant - START")
    data['Merchant'] = "Not Mentioned"
    try:
        offer_display = soup.find("div", id="offer-display-features")
        if offer_display:
            merchant = offer_display.find("div", id="merchantInfoFeature_feature_div")
            if merchant:
                divs = merchant.find_all("div", recursive=False)
                if len(divs) >= 2:
                    attr = safe_text(divs[0])
                    value = "Not Mentioned"
                    first_child = divs[1].find(recursive=False)
                    if first_child:
                        value = safe_text(first_child)
                    else:
                        value = safe_text(divs[1])
                    if attr != "Not Mentioned" or value != "Not Mentioned":
                        data['Merchant'] = f"{attr} | {value}"
                else:
                    data['Merchant'] = safe_text(merchant)
            else:
                data['Merchant'] = safe_text(merchant)
    except Exception as e:
        logger.warning(f"[worker] Error extracting merchant: {e}")
        data['Merchant'] = "Not Mentioned"
    logger.info("[worker] extraction: merchant - DONE")

    # --- Product Images ---
    logger.info("[worker] extraction: product images - START")
    data['Product Images'] = "Not Mentioned"
    data['Main Product Image'] = "Not Mentioned"
    try:
        main_img = soup.select_one("#imgTagWrapperId img")
        if main_img:
            dynamic = main_img.get("data-a-dynamic-image")
            if dynamic:
                try:
                    image_dict = json.loads(dynamic)
                    if isinstance(image_dict, dict) and len(image_dict) > 0:
                        img_list = list(image_dict.keys())
                        data['Main Product Image'] = img_list[0]
                        data['Product Images'] = ", ".join(img_list)
                except:
                    pass
            if data['Product Images'] == "Not Mentioned":
                old_hires = main_img.get("data-old-hires")
                if old_hires and "m.media-amazon.com/images" in old_hires:
                    data['Main Product Image'] = old_hires
                    data['Product Images'] = old_hires
        if data['Product Images'] == "Not Mentioned":
            imgs = []
            img_tags = soup.find_all("img", src=True)
            for img in img_tags:
                src = img.get("src", "")
                if re.search(r"https://m\.media-amazon\.com/images/", src):
                    imgs.append(src)
            if imgs:
                data['Main Product Image'] = imgs[0]
                data['Product Images'] = ", ".join(imgs)
    except Exception as e:
        logger.warning(f"[worker] Error extracting product images: {e}")
    logger.info("[worker] extraction: product images - DONE")

    # --- Comments ---
    logger.info("[worker] extraction: comments - START")
    comments = soup.find_all("div", class_="a-row a-spacing-small review-data")
    data['Comments'] = ",\n".join(safe_text(c) for c in comments[:7]) if comments else "Not Mentioned"
    logger.info("[worker] extraction: comments - DONE")

    # --- Seller Profile ---
    logger.info("[worker] extraction: seller profile - START")
    data['Seller Profile'] = "Not Mentioned"
    try:
        sellerProfile = soup.find("a", id="sellerProfileTriggerId")
        if sellerProfile:
            href = sellerProfile.get("href", "").strip()
            if href:
                data['Seller Profile'] = href
    except Exception as e:
        logger.warning(f"[worker] Error extracting seller profile: {e}")
    logger.info("[worker] extraction: seller profile - DONE")

    # --- Availability ---
    logger.info("[worker] extraction: availability - START")
    availability_tag = soup.find("div", id="availability")
    avail_text = safe_text(availability_tag)
    data['Availability'] = "Available" if "In Stock" in avail_text and data['Price Box'] != "Not Mentioned" else "Not Available"
    logger.info("[worker] extraction: availability - DONE")

    # --- KeyWord column (all tr table data) ---
    logger.info("[worker] extraction: keyword - START")
    try:
        data['KeyWord'] = scrape_tr_table(soup)
    except Exception as e:
        logger.warning(f"[worker] Error extracting keyword: {e}")
        data['KeyWord'] = 'Not Mentioned'
    logger.info("[worker] extraction: keyword - DONE")

    # ============================================================================
    # BUY BOX EXTRACTION (ENHANCED)
    # ============================================================================
    buybox_data = extract_buybox(soup)
    data = map_buybox_to_product_data(data, buybox_data)

    logger.info(
        "[BUYBOX DEBUG] Formatted offers length=%d",
        len(data.get("BuyBox Formatted Offers", ""))
    )

    # Create and return ProductData object from dictionary
    try:
        product = ProductData.from_dict(data)
        logger.info("[worker] extraction: ProductData creation successful")
        return product
    except Exception as e:
        logger.error(f"[worker] ProductData instantiation failed for {url}: {e}")
        return ProductData.create_fallback(url=url, error=str(e))


def get_driver(chromedriver_path: str = "chromedriver.exe", headless: bool = False):
    """
    Create a Chrome WebDriver instance with appropriate options.
    Legacy helper kept for direct/manual scraping workflows.
    """
    from utils.driver_manager import DriverManager
    manager = DriverManager(webdriver_path=chromedriver_path, headless=headless)
    return manager.create_driver()