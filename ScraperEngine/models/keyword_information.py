"""
KeywordInformation - Data class for parsed keyword-value pairs from the KeyWord column.

The KeyWord column in Amazon data is structured as:
    "Keyword1 | value1-------------------------------Keyword2 | value2"

This class represents a single keyword-value pair extracted from the raw column data.
"""

from typing import Optional

from utils.safe_ops import safe_str
from utils.logger import logger


class KeywordInformation:
    """
    Represents a single keyword-value pair extracted from the KeyWord column.
    
    Attributes:
        keyword: The keyword name (e.g., "UPC", "Brand", "Model Number")
        value: The value associated with the keyword, or "Not Mentioned" if empty
    """
    
    def __init__(self, keyword: str, value: str = "Not Mentioned"):
        """
        Initialize KeywordInformation.
        
        Args:
            keyword: The keyword label
            value: The value for this keyword (default: "Not Mentioned")
        """
        try:
            self.keyword = safe_str(keyword)
            self.value = safe_str(value)
        except Exception as e:
            logger.debug(f"KeywordInformation init error: {e}")
            self.keyword = "Not Mentioned"
            self.value = "Not Mentioned"
    
    def __repr__(self) -> str:
        """String representation of KeywordInformation."""
        return f"KeywordInformation(keyword='{self.keyword}', value='{self.value}')"
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.keyword} | {self.value}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        try:
            return {
                'keyword': self.keyword,
                'value': self.value
            }
        except Exception as e:
            logger.debug(f"KeywordInformation to_dict error: {e}")
            return {'keyword': 'Not Mentioned', 'value': 'Not Mentioned'}
    
    @classmethod
    def from_string(cls, string: str, separator: str = '|') -> Optional['KeywordInformation']:
        """
        Create KeywordInformation from a formatted string "keyword | value".
        
        Args:
            string: Formatted string like "UPC | 123456789"
            separator: Character that separates keyword from value (default: '|')
        
        Returns:
            KeywordInformation instance or None if parsing fails
        """
        try:
            text = safe_str(string, default="")
            if not text or separator not in text:
                return None
            
            parts = text.split(separator, 1)
            if len(parts) != 2:
                return None
            
            keyword = safe_str(parts[0], default="")
            value = safe_str(parts[1], default="Not Mentioned")
            
            if not keyword or keyword == "Not Mentioned":
                return None
            
            return cls(keyword, value)
        except (TypeError, ValueError, AttributeError) as e:
            logger.debug(f"KeywordInformation.from_string error for {string!r}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected KeywordInformation.from_string error: {e}")
            return None
    
    def is_mentioned(self) -> bool:
        """
        Check if the value is actually mentioned (not "Not Mentioned").
        
        Returns:
            True if value is not "Not Mentioned", False otherwise
        """
        try:
            return self.value != "Not Mentioned"
        except Exception:
            return False
