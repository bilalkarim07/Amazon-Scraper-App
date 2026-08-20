"""
ProductData - Main data class representing a scraped Amazon product with all extracted columns.

This class provides structured, type-safe access to product information with
properties for each column, replacing direct dictionary/CSV access.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from utils.safe_ops import safe_str, is_missing
from utils.logger import logger
from .keyword_information import KeywordInformation


COLUMN_MAPPING = {
    'Product Link': 'product_link',
    'ASIN': 'asin',
    'Title': 'title',
    'Price Box': 'price_box',
    'Sale Price': 'sale_price',
    'Marked Price': 'marked_price',
    'Discount': 'discount',
    'Ratings': 'ratings',
    'Reviews': 'reviews',
    'Store Name': 'store_name',
    'Store Link': 'store_link',
    'Merchant': 'merchant',
    'Seller Profile': 'seller_profile',
    'Top Highlights': 'top_highlights',
    'Item Details': 'item_details',
    'Description': 'description',
    'Product Images': 'product_images',
    'Main Product Image': 'main_product_image',
    'Category': 'category',
    'Sub Category': 'sub_category',
    'BreadCrumb': 'breadcrumb',
    'Display Features': 'display_features',
    'Display Features 1': 'display_features_1',
    'Product Information': 'product_information',
    'Best Seller Rank': 'best_seller_rank',
    'Comments': 'comments',
    'Variations': 'variations',
    'Availability': 'availability',
    'KeyWord': 'raw_keyword_column',
    # --- Buy Box fields ---
    'BuyBox_Offers': 'buybox_offers',
    'BuyBox_Offer_Count': 'buybox_offer_count',
    'BuyBox_Prices': 'buybox_prices',
    'BuyBox_Sellers': 'buybox_sellers',
    'BuyBox_Title': 'buybox_title',
    'BuyBox_Price': 'buybox_price',
    'BuyBox_Availability': 'buybox_availability',
    'BuyBox_Delivery': 'buybox_delivery',
    'BuyBox_Sold_By': 'buybox_sold_by',
    'BuyBox_Shipped_By': 'buybox_shipped_by',
    'BuyBox_Active_Index': 'buybox_active_index',
    'BuyBox_Success': 'buybox_success',
    'BuyBox_Success_Details': 'buybox_success_details',
    # New field
    'BuyBox Formatted Offers': 'buybox_formatted_offers',
}


@dataclass
class ProductData:
    """
    Represents a complete Amazon product with all scraped and processed data.
    
    Each column from the original CSV/data extraction becomes a property.
    This provides type safety, IDE autocomplete, and better code maintainability.
    """
    
    # Basic Product Info
    product_link: str = "Not Mentioned"
    asin: str = "Not Mentioned"
    title: str = "Not Mentioned"
    
    # Pricing
    price_box: str = "Not Mentioned"
    sale_price: str = "Not Mentioned"
    marked_price: str = "Not Mentioned"
    discount: str = "Not Mentioned"
    
    # Ratings and Reviews
    ratings: str = "Not Mentioned"
    reviews: str = "Not Mentioned"
    
    # Store Information
    store_name: str = "Not Mentioned"
    store_link: str = "Not Mentioned"
    merchant: str = "Not Mentioned"
    seller_profile: str = "Not Mentioned"
    
    # Product Details
    top_highlights: str = "Not Mentioned"
    item_details: str = "Not Mentioned"
    description: str = "Not Mentioned"
    
    # Media
    product_images: str = "Not Mentioned"
    main_product_image: str = "Not Mentioned"
    
    # Categorization
    category: str = "Not Mentioned"
    sub_category: str = "Not Mentioned"
    breadcrumb: str = "Not Mentioned"
    
    # Additional Info
    display_features: str = "Not Mentioned"
    display_features_1: str = "Not Mentioned"
    
    # Product Information (contains structured data)
    product_information: str = "Not Mentioned"
    best_seller_rank: str = "Not Mentioned"
    
    # Other
    comments: str = "Not Mentioned"
    variations: str = "Not Mentioned"
    availability: str = "Not Mentioned"
    
    # Status flags
    is_fallback: bool = False
    is_timeout: bool = False

    # ---- Buy Box fields ----
    buybox: str = 'Not Mentioned'                     # Combined full Buy Box text (optional)
    buybox_offers: str = 'Not Mentioned'              # Condition lines for all offers
    buybox_offer_count: str = 'Not Mentioned'         # Number of offers (as string)
    buybox_prices: str = 'Not Mentioned'              # Price lines for all offers
    buybox_sellers: str = 'Not Mentioned'             # Seller lines for all offers
    buybox_title: str = 'Not Mentioned'               # Primary offer condition
    buybox_price: str = 'Not Mentioned'               # Primary offer price
    buybox_availability: str = 'Not Mentioned'        # Primary offer availability
    buybox_delivery: str = 'Not Mentioned'            # Primary offer delivery
    buybox_sold_by: str = 'Not Mentioned'             # Primary offer sold by
    buybox_shipped_by: str = 'Not Mentioned'          # Primary offer shipped by
    buybox_active_index: str = 'Not Mentioned'        # Index of active offer
    buybox_success: str = 'Not Mentioned'             # "True" or "False"
    buybox_success_details: str = 'Not Mentioned'     # Success details string
    buybox_formatted_offers: str = 'Not Mentioned'    # New formatted field
    
    # Keyword Information - structured as list of KeywordInformation objects
    keyword_information: List[KeywordInformation] = field(default_factory=list)
    raw_keyword_column: str = "Not Mentioned"
    
    @classmethod
    def create_fallback(cls, url: str = "Not Mentioned", error: Optional[str] = None, is_timeout: bool = False) -> 'ProductData':
        """
        Return a minimal ProductData instance when scraping or parsing fails.
        
        Args:
            url: The product URL
            error: Optional error message to store in comments
            is_timeout: Whether this fallback is due to a timeout (default False)
        """
        instance = cls(product_link=safe_str(url))
        instance.is_fallback = True
        instance.is_timeout = is_timeout
        if error:
            instance.comments = f"Scrape error: {safe_str(error, default='Unknown error')}"
        return instance
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductData':
        """
        Create ProductData instance from a dictionary (e.g., from pandas row or CSV dict).
        
        Args:
            data: Dictionary with column names as keys
        
        Returns:
            ProductData instance (never raises; returns fallback on failure)
        """
        if not isinstance(data, dict):
            logger.warning(f"ProductData.from_dict expected dict, got {type(data).__name__}")
            return cls.create_fallback(error="Invalid data type for ProductData.from_dict")
        
        try:
            kwargs = {}
            for csv_col, attr_name in COLUMN_MAPPING.items():
                try:
                    raw_value = data.get(csv_col, "Not Mentioned")
                    kwargs[attr_name] = safe_str(raw_value)
                except Exception as e:
                    logger.debug(f"ProductData field mapping error ({csv_col}): {e}")
                    kwargs[attr_name] = "Not Mentioned"
            
            instance = cls(**kwargs)
            
            if not is_missing(instance.raw_keyword_column):
                try:
                    instance.parse_keyword_information()
                except Exception as e:
                    logger.warning(f"Keyword parsing failed for {instance.product_link}: {e}")
                    instance.keyword_information = []
            
            return instance
        except (TypeError, ValueError) as e:
            url = safe_str(data.get('Product Link', data.get('product_link', 'Not Mentioned')))
            logger.warning(f"ProductData.from_dict failed for {url}: {e}")
            return cls.create_fallback(url=url, error=str(e))
        except Exception as e:
            url = safe_str(data.get('Product Link', data.get('product_link', 'Not Mentioned')))
            logger.error(f"Unexpected ProductData.from_dict error for {url}: {e}")
            return cls.create_fallback(url=url, error=str(e))
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ProductData back to dictionary format compatible with CSV/pandas.
        
        Returns:
            Dictionary with column names as keys
        """
        reverse_mapping = {attr: csv_col for csv_col, attr in COLUMN_MAPPING.items()}
        result = {}
        
        for attr_name, csv_col in reverse_mapping.items():
            try:
                value = getattr(self, attr_name, "Not Mentioned")
                result[csv_col] = safe_str(value)
            except Exception as e:
                logger.debug(f"ProductData.to_dict error for {attr_name}: {e}")
                result[csv_col] = "Not Mentioned"
        
        return result
    
    def _upsert_keyword(self, keyword_info: KeywordInformation) -> None:
        """Add or update a keyword, avoiding duplicate keyword names."""
        keyword_lower = keyword_info.keyword.lower()
        
        for existing in self.keyword_information:
            if existing.keyword.lower() == keyword_lower:
                existing.value = keyword_info.value
                return
        
        self.keyword_information.append(keyword_info)
    
    def parse_keyword_information(self, separator: str = '-------------------------------') -> None:
        """
        Parse raw_keyword_column into structured KeywordInformation objects.
        
        Duplicate keyword labels are merged (last segment wins).
        
        Args:
            separator: Separator used between keyword-value pairs
        """
        if is_missing(self.raw_keyword_column):
            self.keyword_information = []
            return
        
        self.keyword_information = []
        
        try:
            segments = self.raw_keyword_column.split(separator)
        except Exception as e:
            logger.debug(f"Could not split keyword column: {e}")
            return
        
        for segment in segments:
            try:
                segment = safe_str(segment, default="").strip()
                if not segment:
                    continue
                
                keyword_info = KeywordInformation.from_string(segment)
                if keyword_info:
                    self._upsert_keyword(keyword_info)
            except Exception as e:
                logger.debug(f"Skipping malformed keyword segment {segment!r}: {e}")
                continue
    
    def get_keyword_value(self, keyword: str) -> str:
        """
        Get the value for a specific keyword.
        
        Args:
            keyword: The keyword to search for (case-insensitive)
        
        Returns:
            The value associated with the keyword, or "Not Mentioned" if not found
        """
        try:
            keyword_lower = safe_str(keyword, default="").lower()
            if not keyword_lower:
                return "Not Mentioned"
            
            for kw_info in self.keyword_information:
                if kw_info.keyword.lower() == keyword_lower:
                    return kw_info.value
        except Exception as e:
            logger.debug(f"get_keyword_value error for {keyword!r}: {e}")
        
        return "Not Mentioned"
    
    def has_keyword(self, keyword: str) -> bool:
        """
        Check if a specific keyword exists in the keyword information.
        
        Args:
            keyword: The keyword to search for (case-insensitive)
        
        Returns:
            True if keyword exists and has a value, False otherwise
        """
        return self.get_keyword_value(keyword) != "Not Mentioned"
    
    def set_keyword_value(self, keyword: str, value: str) -> None:
        """
        Set or update a keyword value.
        
        Args:
            keyword: The keyword to set
            value: The value to set
        """
        try:
            keyword_text = safe_str(keyword, default="")
            if not keyword_text or keyword_text == "Not Mentioned":
                return
            
            for kw_info in self.keyword_information:
                if kw_info.keyword.lower() == keyword_text.lower():
                    kw_info.value = safe_str(value)
                    return
            
            self.keyword_information.append(KeywordInformation(keyword_text, safe_str(value)))
        except Exception as e:
            logger.debug(f"set_keyword_value error for {keyword!r}: {e}")
    
    def __repr__(self) -> str:
        """String representation."""
        try:
            title_preview = safe_str(self.title, default="")[:50]
            return f"ProductData(asin='{safe_str(self.asin)}', title='{title_preview}...')"
        except Exception:
            return "ProductData(<repr unavailable>)"
    
    def __str__(self) -> str:
        """Human-readable string."""
        try:
            return f"Product: {safe_str(self.title)} (ASIN: {safe_str(self.asin)})"
        except Exception:
            return "Product: <unavailable>"