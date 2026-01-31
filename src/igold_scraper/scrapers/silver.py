#!/usr/bin/env python3

"""
igold.bg comprehensive silver scraper (coins and bars)
Scrapes product metadata once, then updates prices daily from category pages.

Refactored to use ProductManager for product-based storage with price history.
"""

import logging
import argparse
import time

from igold_scraper.scrapers.igold_base import IgoldBaseScraper
from igold_scraper.services.database_manager import DatabaseManager
from igold_scraper.constants import METAL_TYPE_SILVER

logger = logging.getLogger(__name__)

# Only use the main silver page - all silver products are there
START_PAGES = ["/srebro"]


class IgoldSilverScraper(IgoldBaseScraper):
    """Silver scraper for igold.bg"""

    def __init__(self) -> None:
        """Initialize the silver scraper."""
        super().__init__(metal_type=METAL_TYPE_SILVER)


def main() -> None:
    """Main entry point for silver scraper."""
    # Setup command line arguments
    parser = argparse.ArgumentParser(description="igold.bg silver scraper")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
        force=True,  # Override any existing configuration
    )

    # Create scraper
    scraper = IgoldSilverScraper()

    # Initialize database manager
    product_manager = DatabaseManager()

    # Scrape products and update prices
    logger.info("Starting silver product scraping from igold.bg...")
    total_updated = 0
    total_new = 0

    for category_url in START_PAGES:
        full_url = f"{scraper.base_url}{category_url}"

        # Extract prices from category page
        category_prices = scraper.extract_category_prices(full_url)
        logger.info("Extracted %d prices from category page", len(category_prices))

        # Process each product
        for price_data in category_prices:
            url = price_data['url']  # Already normalized to relative path

            # Check if we already have this product's metadata
            if not product_manager.product_exists(url, 'silver'):
                # First time seeing this product - scrape full page
                logger.info("New product found: %s", url)
                # Build full URL for scraping
                full_product_url = f"{scraper.base_url}{url}"
                product = scraper.extract_product_data(full_product_url)

                if product:
                    product.metal_type = 'silver'
                    # Silver doesn't have separate bar/coin categories
                    product_manager.save_product(product)
                    total_new += 1
                    # Add delay after scraping a new product
                    time.sleep(scraper.config.get_random_delay())
                else:
                    logger.warning("Failed to extract data from %s", url)
                    continue

            # Add price entry (for both new and existing products)
            product_manager.add_price_entry(
                url=url,
                metal_type='silver',
                sell_price_eur=price_data['sell_price_eur'],
                buy_price_eur=price_data['buy_price_eur']
            )
            total_updated += 1

    logger.info("Total products updated: %d", total_updated)
    logger.info("New products added: %d", total_new)

    # Get latest prices for all products
    latest_prices = product_manager.get_latest_prices('silver')

    # Sort by price per gram (handle None values)
    sorted_products = sorted(
        latest_prices,
        key=lambda x: x.get('price_per_g_fine_eur') if x.get('price_per_g_fine_eur') is not None else float('inf')
    )

    # Print summary statistics
    logger.info("\n=== Silver Products Summary ===")
    logger.info("Total products: %d", len(sorted_products))

    # Count by product type
    bars = sum(1 for p in sorted_products if p.get('product_type') == "bar")
    coins = sum(1 for p in sorted_products if p.get('product_type') == "coin")
    unknown = sum(1 for p in sorted_products if p.get('product_type') == "unknown")

    logger.info("Bars: %d, Coins: %d, Unknown: %d", bars, coins, unknown)

    # Top 5 by price per gram
    logger.info("\nTop 5 Best Prices (per gram fine silver):")
    for i, item in enumerate(sorted_products[:5], 1):
        name = item.get('product_name', '')
        name = name[:60] + "..." if len(name) > 60 else name
        logger.info("%d. %s (%s)", i, name, item.get('product_type', ''))
        logger.info(
            "   Price per gram: %.2f EUR",
            item.get('price_per_g_fine_eur', 0)
        )
        logger.info(
            "   Sell: %.2f EUR | Buy: %.2f EUR",
            item.get('sell_price_eur', 0),
            item.get('buy_price_eur', 0)
        )

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

    scraper.cleanup()


if __name__ == "__main__":
    main()
