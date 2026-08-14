"""marketplace_config.py — Centralized marketplace configuration."""

from typing import Dict, Any, Optional

MARKETPLACES: Dict[str, Dict[str, Any]] = {
    "US": {
        "label": "United States",
        "domain": "amazon.com",
        "base_url": "https://www.amazon.com/",
        "currency_code": "USD",
        "currency_symbol": "$"
    },
    "CA": {
        "label": "Canada",
        "domain": "amazon.ca",
        "base_url": "https://www.amazon.ca/",
        "currency_code": "CAD",
        "currency_symbol": "C$"
    },
    "UK": {
        "label": "United Kingdom",
        "domain": "amazon.co.uk",
        "base_url": "https://www.amazon.co.uk/",
        "currency_code": "GBP",
        "currency_symbol": "£"
    },
    "FR": {
        "label": "France",
        "domain": "amazon.fr",
        "base_url": "https://www.amazon.fr/",
        "currency_code": "EUR",
        "currency_symbol": "€"
    },
    "DE": {
        "label": "Germany",
        "domain": "amazon.de",
        "base_url": "https://www.amazon.de/",
        "currency_code": "EUR",
        "currency_symbol": "€"
    },
    "IT": {
        "label": "Italy",
        "domain": "amazon.it",
        "base_url": "https://www.amazon.it/",
        "currency_code": "EUR",
        "currency_symbol": "€"
    },
    "ES": {
        "label": "Spain",
        "domain": "amazon.es",
        "base_url": "https://www.amazon.es/",
        "currency_code": "EUR",
        "currency_symbol": "€"
    },
    "NL": {
        "label": "Netherlands",
        "domain": "amazon.nl",
        "base_url": "https://www.amazon.nl/",
        "currency_code": "EUR",
        "currency_symbol": "€"
    },
    "PL": {
        "label": "Poland",
        "domain": "amazon.pl",
        "base_url": "https://www.amazon.pl/",
        "currency_code": "PLN",
        "currency_symbol": "zł"
    },
    "SE": {
        "label": "Sweden",
        "domain": "amazon.se",
        "base_url": "https://www.amazon.se/",
        "currency_code": "SEK",
        "currency_symbol": "kr"
    },
    "BE": {
        "label": "Belgium",
        "domain": "amazon.com.be",
        "base_url": "https://www.amazon.com.be/",
        "currency_code": "EUR",
        "currency_symbol": "€"
    },
    "IE": {
        "label": "Ireland",
        "domain": "amazon.ie",
        "base_url": "https://www.amazon.ie/",
        "currency_code": "EUR",
        "currency_symbol": "€"
    },
    "TR": {
        "label": "Turkey",
        "domain": "amazon.com.tr",
        "base_url": "https://www.amazon.com.tr/",
        "currency_code": "TRY",
        "currency_symbol": "₺"
    },
    "JP": {
        "label": "Japan",
        "domain": "amazon.co.jp",
        "base_url": "https://www.amazon.co.jp/",
        "currency_code": "JPY",
        "currency_symbol": "¥"
    },
    "IN": {
        "label": "India",
        "domain": "amazon.in",
        "base_url": "https://www.amazon.in/",
        "currency_code": "INR",
        "currency_symbol": "₹"
    },
    "SG": {
        "label": "Singapore",
        "domain": "amazon.sg",
        "base_url": "https://www.amazon.sg/",
        "currency_code": "SGD",
        "currency_symbol": "S$"
    },
    "AU": {
        "label": "Australia",
        "domain": "amazon.com.au",
        "base_url": "https://www.amazon.com.au/",
        "currency_code": "AUD",
        "currency_symbol": "A$"
    },
    "AE": {
        "label": "United Arab Emirates",
        "domain": "amazon.ae",
        "base_url": "https://www.amazon.ae/",
        "currency_code": "AED",
        "currency_symbol": "د.إ"
    },
    "SA": {
        "label": "Saudi Arabia",
        "domain": "amazon.sa",
        "base_url": "https://www.amazon.sa/",
        "currency_code": "SAR",
        "currency_symbol": "﷼"
    },
    "EG": {
        "label": "Egypt",
        "domain": "amazon.eg",
        "base_url": "https://www.amazon.eg/",
        "currency_code": "EGP",
        "currency_symbol": "E£"
    },
    "MX": {
        "label": "Mexico",
        "domain": "amazon.com.mx",
        "base_url": "https://www.amazon.com.mx/",
        "currency_code": "MXN",
        "currency_symbol": "Mex$"
    },
    "BR": {
        "label": "Brazil",
        "domain": "amazon.com.br",
        "base_url": "https://www.amazon.com.br/",
        "currency_code": "BRL",
        "currency_symbol": "R$"
    },
    "ALL_EUROPE": {
        "label": "All Europe",
        "domain": "auto",
        "base_url": "auto",
        "currency_code": "AUTO",
        "currency_symbol": "AUTO",
        "is_europe_union": True
    }
}

# Domain → currency mapping for ALL_EUROPE detection
EUROPE_DOMAIN_CURRENCY_MAP = {
    "amazon.co.uk": ("GBP", "£"),
    "amazon.de": ("EUR", "€"),
    "amazon.fr": ("EUR", "€"),
    "amazon.it": ("EUR", "€"),
    "amazon.es": ("EUR", "€"),
    "amazon.nl": ("EUR", "€"),
    "amazon.com.be": ("EUR", "€"),
    "amazon.ie": ("EUR", "€"),
    "amazon.pl": ("PLN", "zł"),
    "amazon.se": ("SEK", "kr"),
    "amazon.com.tr": ("TRY", "₺"),
}

def get_marketplace(marketplace_id: str) -> Optional[Dict[str, Any]]:
    """Get marketplace configuration by ID."""
    return MARKETPLACES.get(marketplace_id)

def get_all_marketplaces() -> Dict[str, Dict[str, Any]]:
    """Get all marketplace configurations."""
    return MARKETPLACES

def get_currency_from_url(url: str) -> tuple[str, str]:
    """Extract currency from URL for ALL_EUROPE mode."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    # Remove www. prefix if present
    if hostname.startswith("www."):
        hostname = hostname[4:]
    for domain, (code, symbol) in EUROPE_DOMAIN_CURRENCY_MAP.items():
        if domain in hostname:
            return code, symbol
    # Fallback to EUR
    return "EUR", "€"

def validate_marketplace(marketplace_id: str) -> bool:
    """Check if marketplace ID is valid."""
    return marketplace_id in MARKETPLACES