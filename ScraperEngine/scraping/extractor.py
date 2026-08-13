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
from selenium.common.exceptions import TimeoutException, WebDriverException
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

def scrape_product(driver, url: str, wait: int = 150, cancel_check=None) -> ProductData:
    """
    Scrape a single Amazon product page and return a ProductData object.
    
    Parameters:
        driver: selenium.webdriver.Chrome WebDriver instance
        url: Product URL to scrape
        wait: Wait time in seconds before starting extraction
        cancel_check: Optional callable that returns True if cancellation requested
    
    Returns:
        ProductData: Structured product data object
    """
    url = safe_str(url, default="Not Mentioned")
    try:
        return _scrape_product_page(driver, url, wait, cancel_check)
    except Exception as e:
        logger.error(f"scrape_product failed for {url}: {e}")
        return ProductData.create_fallback(url=url, error=str(e))


def _scrape_product_page(driver, url: str, wait: int, cancel_check=None) -> ProductData:
    """
    Internal scrape implementation; callers should use scrape_product().
    """
    # --- Diagnostic logging ---
    logger.info(f"[worker] Starting URL: {url}")

    # Set page load timeout to prevent indefinite blocking
    driver.set_page_load_timeout(60)  # 60 seconds max for page load

    # --- Navigation ---
    logger.info("[worker] Calling driver.get()")
    try:
        driver.get(url)
        logger.info("[worker] driver.get() returned")
    except TimeoutException:
        logger.error(f"[worker] Page load timed out after 60s: {url}")
        raise RuntimeError(f"Page load timeout after 60 seconds: {url}")
    except WebDriverException as e:
        logger.error(f"[worker] WebDriver error during navigation: {e}")
        raise RuntimeError(f"WebDriver error loading page: {e}")
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
    try:
        soup = BeautifulSoup(driver.page_source, "lxml")
    except Exception as e:
        logger.error(f"[worker] Failed to parse page HTML: {e}")
        raise RuntimeError(f"Could not parse page HTML: {e}") from e

    # Initialize with all defaults
    data = {
        'Product Link': url,
        'ASIN': extract_asin(url),
    }
    
    # Title
    data['Title'] = safe_text(soup.find("span", id="productTitle"))
    
    # Store information
    store = soup.find("a", id="bylineInfo")
    data['Store Name'] = safe_text(store)
    href = safe_attr(store, "href")
    data['Store Link'] = href if href != "Not Mentioned" else "Not Mentioned"
    
    # Ratings
    rating = soup.find("span", id="acrPopover")
    if rating:
        data['Ratings'] = rating.get("title") or safe_text(rating.find("a"))
    else:
        data['Ratings'] = "Not Mentioned"
    
    # Reviews
    reviews = soup.find("span", id="acrCustomerReviewText")
    data['Reviews'] = safe_attr(reviews, "aria-label")
    
    # Price
    price = soup.find("div", id="corePriceDisplay_desktop_feature_div")
    data['Price Box'] = safe_text(price)
    
    # Description (Top Highlights)
    bullets = soup.find("div", id="feature-bullets")
    data['Description'] = safe_text(bullets.find("ul")) if bullets else "Not Mentioned"
    
    # Top Highlights from poExpander
    item_pairs = []
    try:
        toggle = soup.find("div", id="poToggleButton")
        if toggle:
            try:
                driver.execute_script("arguments[0].click();", toggle.find("a"))
                time.sleep(1)
            except:
                pass
        expander = soup.find("div", id="poExpander")
        if expander:
            for tr in expander.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) == 2:
                    item_pairs.append((safe_text(tds[0]), safe_text(tds[1])))
        else:
            rows = soup.find_all("tr", class_=re.compile("a-spacing-small"), role="listitem")
            for r in rows:
                if "po" in r.get("class", []):
                    spans = r.find_all("span")
                    if len(spans) >= 2:
                        item_pairs.append((safe_text(spans[0]), safe_text(spans[1])))
        # Fallback if not item_pairs
        if not item_pairs:
            overview = soup.find("div", id="productOverview_feature_div")
            if overview:
                for tr in overview.find_all("tr"):
                    tds = tr.find_all("td")
                    if len(tds) == 2:
                        item_pairs.append((safe_text(tds[0]), safe_text(tds[1])))
    except:
        pass
    data['Top Highlights'] = boundary_format(item_pairs)
    
    # Item Details
    item_details_el = None
    try:
        item_details_el = driver.find_element(By.ID, "item_details")
    except:
        pass
    data['Item Details'] = extract_item_details(item_details_el) if item_details_el else "Not Mentioned"
    
    # Variations
    data['Variations'] = extract_variation_asins(source=soup)
    
    # Product Information
    info_pairs = []
    prod = soup.find("div", id="prodDetails")
    if prod:
        for tr in prod.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                info_pairs.append((safe_text(th), safe_text(td)))
    # Fallback if not info_pairs
    if not info_pairs:
        prod_alt = soup.find("div", id="productDetails_feature_div")
        if prod_alt:
            for tr in prod_alt.find_all("tr"):
                th = tr.find("th")
                td = tr.find("td")
                if th and td:
                    info_pairs.append((safe_text(th), safe_text(td)))
    data['Product Information'] = boundary_format(info_pairs)
    
    # Breadcrumbs and Categories
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
    
    # Display Features
    display = soup.find("div", id="offer-display-features")
    data['Display Features'] = safe_text(display)
    
    # Display Features 1 (detailed)
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
    except:
        data['Display Features 1'] = "Not Mentioned"
    
    # Merchant
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
    except:
        data['Merchant'] = "Not Mentioned"
    
    # Product Images
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
    except:
        pass
    
    # Comments
    comments = soup.find_all("div", class_="a-row a-spacing-small review-data")
    data['Comments'] = ",\n".join(safe_text(c) for c in comments[:7]) if comments else "Not Mentioned"
    
    # Seller Profile
    data['Seller Profile'] = "Not Mentioned"
    try:
        sellerProfile = soup.find("a", id="sellerProfileTriggerId")
        if sellerProfile:
            href = sellerProfile.get("href", "").strip()
            if href:
                data['Seller Profile'] = href
    except:
        pass
    
    # Availability
    availability_tag = soup.find("div", id="availability")
    avail_text = safe_text(availability_tag)
    data['Availability'] = "Available" if "In Stock" in avail_text and data['Price Box'] != "Not Mentioned" else "Not Available"
    
    # KeyWord column (all tr table data)
    try:
        data['KeyWord'] = scrape_tr_table(soup)
    except:
        data['KeyWord'] = 'Not Mentioned'
    
    # Create and return ProductData object from dictionary
    try:
        return ProductData.from_dict(data)
    except Exception as e:
        logger.error(f"ProductData instantiation failed for {url}: {e}")
        return ProductData.create_fallback(url=url, error=str(e))

    # Extraction completed log
    logger.info("[worker] Page extraction completed")


def get_driver(chromedriver_path: str = "chromedriver.exe", headless: bool = False):
    """
    Create a Chrome WebDriver instance with appropriate options.
    Legacy helper kept for direct/manual scraping workflows.
    """
    from utils.driver_manager import DriverManager
    manager = DriverManager(webdriver_path=chromedriver_path, headless=headless)
    return manager.create_driver()