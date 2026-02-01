"""
Shared utilities for gold and silver scraper.
Common functions to reduce code duplication.
"""

import re
import logging
from typing import Dict, Optional, List
from urllib.parse import urljoin

logger = logging.getLogger()

# ============================================================================
# CONSTANTS (Shared by both scrapers)
# ============================================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}


# ============================================================================
# SORTING AND FILTERING (Shared by both scrapers)
# ============================================================================

def sort_key_function(item: Dict) -> tuple:
    """
    Sort function that prioritizes items with price_per_g_fine_eur.
    Items without price per gram go to the end.

    Args:
        item: Product dictionary

    Returns:
        Tuple for sorting: (priority, price) where 0 = has price, 1 = no price
    """
    price_per_g = item.get('price_per_g_fine_eur')
    if price_per_g is not None:
        return (0, price_per_g)  # (priority, price) - 0 = high priority
    return (1, 0)  # (priority, fallback) - 1 = low priority


# ============================================================================
# PRICE AND CALCULATION UTILITIES
# ============================================================================

def calculate_spread(buy_price: Optional[float], sell_price: Optional[float]) -> Optional[float]:
    """
    Calculate bid-ask spread percentage.

    Formula: ((sell - buy) / sell) * 100

    Args:
        buy_price: Purchase price
        sell_price: Sale price

    Returns:
        Spread percentage rounded to 2 decimals, or None if invalid
    """
    # Validate inputs
    if buy_price is None or sell_price is None:
        return None
    if not isinstance(buy_price, (int, float)) or not isinstance(sell_price, (int, float)):
        return None
    if buy_price < 0 or sell_price <= 0:
        return None

    spread = ((sell_price - buy_price) / sell_price) * 100
    return round(spread, 2)


def calculate_price_per_gram(price: Optional[float], fine_metal: Optional[float]) -> Optional[float]:
    """
    Calculate price per gram of fine metal.

    Args:
        price: Total price in currency
        fine_metal: Amount of fine metal in grams

    Returns:
        Price per gram rounded to 2 decimals, or None if invalid
    """
    if fine_metal and fine_metal > 0 and price and price > 0:
        return round(price / fine_metal, 2)
    return None


def calculate_fine_metal(weight: Optional[float], purity: Optional[int]) -> Optional[float]:
    """
    Calculate amount of fine metal from weight and purity.

    Args:
        weight: Total weight in grams
        purity: Purity in per mille (0-1000)

    Returns:
        Fine metal amount in grams, or None if invalid
    """
    if weight and weight > 0 and purity and purity > 0:
        return weight * (purity / 1000.0)
    return None


# ============================================================================
# PARSING UTILITIES
# ============================================================================

def safe_float(value: Optional[str], default: Optional[float] = None) -> Optional[float]:
    """
    Safely convert string to float, handling Bulgarian number format.

    Handles:
    - Bulgarian decimal separator: "5,99" → 5.99
    - Whitespace and non-breaking spaces
    - Invalid input returns default

    Args:
        value: String to convert
        default: Default value if conversion fails

    Returns:
        Float value or default (None by default)
    """
    if not value:
        return default
    try:
        # Clean up the value
        value = value.strip()
        # Remove non-breaking spaces and regular spaces
        value = value.replace('\xa0', '').replace('\u00A0', '')
        # Replace Bulgarian decimal separator
        value = value.replace(',', '.')
        return float(value)
    except (ValueError, AttributeError):
        return default


def parse_float_bg(s: str) -> Optional[float]:
    """
    Parse Bulgarian-formatted number string.

    Examples:
    - "6,45 гр." → 6.45
    - "5 838,00 лв." → 5838.0
    - "1,23" → 1.23

    Args:
        s: Bulgarian formatted number string

    Returns:
        Parsed float or None if parsing fails
    """
    if not s:
        return None
    try:
        s = s.strip()
        # Remove non-breaking spaces and Unicode spaces
        s = s.replace('\xa0', ' ').replace('\u00A0', ' ')
        # Remove currency symbols and letters first (keep spaces for thousands separator)
        s = re.sub(r"[a-zA-Zа-яА-ЯёЁ.]+", "", s)
        # Now remove spaces (they were thousands separators)
        s = s.replace(' ', '')
        # Replace comma decimal with dot
        s = s.replace(',', '.')
        # Clean up any remaining non-numeric characters except decimal point and minus
        s = re.sub(r"[^0-9.\-]", "", s)
        return float(s) if s != '' else None
    except (ValueError, AttributeError):
        return None


# ============================================================================
# TAVEX UTILITIES (Gold-specific)
# ============================================================================

def find_tavex_equivalent(
    igold_product: Dict,
    tavex_products: List[Dict],
    equivalent_products: Dict[str, str]
) -> Optional[Dict]:
    """
    Find the equivalent Tavex product for an igold product.

    Args:
        igold_product: Dictionary containing igold product data
        tavex_products: List of dictionaries containing Tavex product data
        equivalent_products: Dictionary mapping igold names to Tavex names

    Returns:
        Dictionary with tavex_buy_price_eur, tavex_sell_price_eur,
        tavex_spread_percentage, is_cheaper, or None if no match
    """
    igold_name = igold_product.get('product_name')
    if not igold_name:
        return None

    # Check if we have an equivalent in our mapping
    tavex_name = equivalent_products.get(igold_name)
    if not tavex_name:
        return None

    # Find the Tavex product with that name
    for tavex_product in tavex_products:
        if tavex_product.get('name') == tavex_name:
            # Get the Tavex data
            tavex_buy_price = tavex_product.get('buy_price')
            tavex_sell_price = tavex_product.get('sell_price')
            tavex_spread = tavex_product.get('spread_percentage')

            # Determine if igold is cheaper
            is_cheaper = "NO"
            igold_sell_price = igold_product.get('sell_price_eur')
            if igold_sell_price and tavex_sell_price and igold_sell_price < tavex_sell_price:
                is_cheaper = "YES"

            return {
                'tavex_buy_price_eur': tavex_buy_price,
                'tavex_sell_price_eur': tavex_sell_price,
                'tavex_spread_percentage': tavex_spread,
                'is_cheaper': is_cheaper,
                'tavex_product_name': tavex_name
            }

    return None


def add_tavex_data_to_results(
    results: List[Dict],
    tavex_products: List[Dict],
    equivalent_products: Dict[str, str]
) -> List[Dict]:
    """
    Add Tavex comparison data to the igold results.

    Args:
        results: List of dictionaries containing igold product data
        tavex_products: List of dictionaries containing Tavex product data
        equivalent_products: Dictionary mapping igold names to Tavex names

    Returns:
        Updated results list with Tavex data
    """
    logger.info("Adding Tavex comparison data to %d igold products...", len(results))

    # Track statistics
    matched_count = 0
    cheaper_count = 0

    for result in results:
        # Find Tavex equivalent
        tavex_data = find_tavex_equivalent(result, tavex_products, equivalent_products)

        if tavex_data:
            # Add Tavex data to the result
            result.update(tavex_data)
            matched_count += 1
            if tavex_data['is_cheaper'] == "YES":
                cheaper_count += 1
        else:
            # If no match, add None values
            result['tavex_buy_price_eur'] = None
            result['tavex_sell_price_eur'] = None
            result['tavex_spread_percentage'] = None
            result['is_cheaper'] = None
            result['tavex_product_name'] = None

    logger.info("Found Tavex equivalents for %d products", matched_count)
    logger.info("igold is cheaper for %d products", cheaper_count)

    return results


# ============================================================================
# URL UTILITIES
# ============================================================================

def convert_relative_url_to_absolute(url: str, base: str) -> str:
    """
    Convert a relative URL to an absolute URL.

    Args:
        url: Relative or absolute URL
        base: Base URL for joining

    Returns:
        Absolute URL
    """
    return urljoin(base, url)


if __name__ == '__main__':
    print("This module contains shared scraper utilities.")
    print("Import functions from your scraper scripts.")
