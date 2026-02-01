#!/usr/bin/env python3
"""
Shared runner logic for gold and silver scrapers.
Eliminates code duplication between scrapers.
"""

import logging
import time
from typing import List, Dict, Optional, Union, Tuple

from igold_scraper.scrapers.base import BaseScraper
from igold_scraper.services.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


def run_scraper(
    scraper: BaseScraper,
    product_manager: DatabaseManager,
    start_pages: Union[List[str], Dict[str, List[str]]],
    metal_type: str,
    urls_to_skip: Optional[List[str]] = None
) -> Tuple[int, int]:
    """
    Run scraping workflow for a metal type.

    Args:
        scraper: Scraper instance (IgoldGoldScraper or IgoldSilverScraper)
        product_manager: DatabaseManager instance
        start_pages: List of category URLs or dict of {product_type: [urls]}
        metal_type: 'gold' or 'silver'
        urls_to_skip: Optional list of URLs to skip

    Returns:
        Tuple of (total_updated, total_new)
    """
    total_updated = 0
    total_new = 0
    urls_to_skip = urls_to_skip or []

    # Handle both list and dict start_pages
    if isinstance(start_pages, dict):
        # Gold: {product_type: [urls]}
        categories = start_pages.items()
    else:
        # Silver: [urls] - treat as unknown product type
        categories = [('unknown', start_pages)]

    for product_type, category_urls in categories:
        if product_type != 'unknown':
            logger.info("Scraping %s products (%d categories)...", product_type, len(category_urls))

        for category_url in category_urls:
            full_url = f"{scraper.base_url}{category_url}"

            # Extract prices from category page
            try:
                category_prices = scraper.extract_category_prices(full_url)
                logger.info("Extracted %d prices from category page", len(category_prices))
            except Exception as e:
                logger.exception("Failed to extract prices from %s: %s", full_url, e)
                continue

            # Process each product
            for price_data in category_prices:
                url = price_data['url']  # Already normalized to relative path

                # Skip URLs we don't want
                if any(skip_url in url for skip_url in urls_to_skip):
                    logger.debug("Skipping filtered URL: %s", url)
                    continue

                # Check if we already have this product's metadata
                if not product_manager.product_exists(url, metal_type):
                    # First time seeing this product - scrape full page
                    logger.info("New product found: %s", url)

                    try:
                        # Build full URL for scraping
                        full_product_url = f"{scraper.base_url}{url}"
                        product = scraper.extract_product_data(full_product_url)

                        if product:
                            product.metal_type = metal_type
                            if product_type != 'unknown':
                                product.product_type = product_type
                            product_manager.save_product(product)
                            total_new += 1
                            # Add delay after scraping a new product
                            time.sleep(scraper.config.get_random_delay())
                        else:
                            logger.warning("Failed to extract data from %s", url)
                            continue
                    except Exception as e:
                        logger.exception("Error scraping new product %s: %s", url, e)
                        continue

                # Add price entry (for both new and existing products)
                try:
                    product_manager.add_price_entry(
                        url=url,
                        sell_price_eur=price_data['sell_price_eur'],
                        buy_price_eur=price_data['buy_price_eur']
                    )
                    total_updated += 1
                except Exception as e:
                    logger.exception("Failed to add price entry for %s: %s", url, e)
                    continue

    return total_updated, total_new


def print_summary_stats(product_manager: DatabaseManager, metal_type: str) -> None:
    """
    Print summary statistics for scraped products.

    Args:
        product_manager: DatabaseManager instance
        metal_type: 'gold' or 'silver'
    """
    try:
        latest_prices = product_manager.get_latest_prices(metal_type)
    except Exception as e:
        logger.error("Failed to get latest prices: %s", e)
        return

    # Sort by price per gram (handle None values)
    sorted_products = sorted(
        latest_prices,
        key=lambda x: (
            x.get('price_per_g_fine_eur')
            if x.get('price_per_g_fine_eur') is not None
            else float('inf')
        )
    )

    # Print summary statistics
    logger.info("\n=== %s Products Summary ===", metal_type.title())
    logger.info("Total products: %d", len(sorted_products))

    # Count by product type (silver specific)
    if metal_type == 'silver':
        bars = sum(1 for p in sorted_products if p.get('product_type') == "bar")
        coins = sum(1 for p in sorted_products if p.get('product_type') == "coin")
        unknown = sum(1 for p in sorted_products if p.get('product_type') == "unknown")
        logger.info("Bars: %d, Coins: %d, Unknown: %d", bars, coins, unknown)

    # Top 5 by price per gram
    logger.info("\nTop 5 Best Prices (per gram fine %s):", metal_type)
    for i, item in enumerate(sorted_products[:5], 1):
        name = item.get('product_name', '')
        name = name[:60] + "..." if len(name) > 60 else name
        logger.info("%d. %s (%s)", i, name, item.get('product_type', ''))
        price_per_g = item.get('price_per_g_fine_eur', 0)
        if price_per_g:
            logger.info("   Price per gram: %.2f EUR", price_per_g)
        logger.info("   Sell: %.2f EUR | Buy: %.2f EUR",
                   item.get('sell_price_eur', 0), item.get('buy_price_eur', 0))

    # Top 5 by spread
    spread_sorted = sorted(
        [p for p in sorted_products if p.get('spread_percentage') is not None],
        key=lambda x: x.get('spread_percentage', 0)
    )

    if spread_sorted:
        logger.info("\nTop 5 Best Spreads:")
        for i, item in enumerate(spread_sorted[:5], 1):
            name = item.get('product_name', '')
            name = name[:60] + "..." if len(name) > 60 else name
            logger.info("%d. %s (%s)", i, name, item.get('product_type', ''))
            logger.info("   Spread: %.2f%%", item.get('spread_percentage', 0))
