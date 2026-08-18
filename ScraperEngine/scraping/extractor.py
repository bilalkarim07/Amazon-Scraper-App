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