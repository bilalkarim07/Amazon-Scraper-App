"""
Shared helpers for safe value coercion during scraping and processing.
"""

from typing import Any

DEFAULT_MISSING = "Not Mentioned"


def is_missing(value: Any) -> bool:
    """Return True when a value should be treated as absent."""
    if value is None:
        return True

    try:
        import pandas as pd
        if pd.isna(value):
            return True
    except (ImportError, TypeError, ValueError):
        pass

    if isinstance(value, str):
        return value.strip() in ("", DEFAULT_MISSING, "N/A", "nan", "NaN")

    return False


def safe_str(value: Any, default: str = DEFAULT_MISSING) -> str:
    """Coerce any value to a safe string for ProductData fields."""
    if is_missing(value):
        return default

    try:
        if isinstance(value, str):
            text = value.strip()
            return text if text else default

        if isinstance(value, (int, float, bool)):
            return str(value).strip()

        text = str(value).strip()
        if text.lower() in ("nan", "none", ""):
            return default
        return text
    except Exception:
        return default
