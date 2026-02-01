#!/usr/bin/env python3

"""
igold.bg comprehensive gold scraper (coins and bars)
Scrapes product metadata once, then updates prices daily from category pages.

Refactored to use ProductManager for product-based storage with price history.
"""

import logging
import argparse
import time
from typing import List

from igold_scraper.scrapers.igold_base import IgoldBaseScraper
from igold_scraper.services.database_manager import DatabaseManager
from igold_scraper.constants import METAL_TYPE_GOLD

logger = logging.getLogger(__name__)

# Start with main category pages
START_PAGES = {
    "bar": [
        "/zlatni-kyulcheta-investitsionni",
        "/kyulcheta-s-numizmatichen-potenitzial",
        "/zlatni-numizmatichni-kyulcheta",
        "/zlatni-kyulcheta-za-podarak",
    ],
    "coin": [
        "/moderni-investitzionni-moneti",
        "/istoricheski-investitzionni-moneti",
        "/zlatni-moneti-s-numizmatichen-potentzial",
        "/moderni-zlatni-moneti-za-podarak",
        "/moderni-numizmatichni-moneti",
        "/istoricheski-numizmatichni-zlatni-moneti",
    ],
}

URLS_TO_SKIP = [
    "/nelikvidno-i-povredeno-zlato",
]


class IgoldGoldScraper(IgoldBaseScraper):
    """Gold scraper for igold.bg"""

    def __init__(self) -> None:
        """Initialize the gold scraper."""
        super().__init__(metal_type=METAL_TYPE_GOLD)
        self.urls_to_skip = URLS_TO_SKIP

    def gather_product_links(self, category_url: str) -> List[str]:
        """
        Collect product links from category pages, filtering out unwanted URLs.

        Args:
            category_url: URL of category page

        Returns:
            List of product URLs
        """
        # Get links using parent method
        product_urls = super().gather_product_links(category_url)

        # Filter out URLs to skip
        filtered_urls = [url for url in product_urls if not any(skip_url in url for skip_url in self.urls_to_skip)]

        if len(filtered_urls) < len(product_urls):
            logger.debug("Filtered out %d URLs from %s", len(product_urls) - len(filtered_urls), category_url)

        return filtered_urls


def main() -> None:
    """Main entry point for gold scraper."""
    # Setup command line arguments
    parser = argparse.ArgumentParser(description="igold.bg gold scraper")
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
    scraper = IgoldGoldScraper()

    # Initialize database manager
    product_manager = DatabaseManager()

    # Scrape products and update prices
    logger.info("Starting gold product scraping from igold.bg...")
    total_updated = 0
    total_new = 0

    for product_type, category_urls in START_PAGES.items():
        logger.info("Scraping %s products (%d categories)...", product_type, len(category_urls))

        for category_url in category_urls:
            full_url = f"{scraper.base_url}{category_url}"

            # Extract prices from category page
            category_prices = scraper.extract_category_prices(full_url)

            # Process each product
            for price_data in category_prices:
                url = price_data["url"]  # Already normalized to relative path

                # Skip URLs we don't want
                if any(skip_url in url for skip_url in URLS_TO_SKIP):
                    logger.debug("Skipping filtered URL: %s", url)
                    continue

                # Check if we already have this product's metadata
                if not product_manager.product_exists(url):
                    # First time seeing this product - scrape full page
                    logger.info("New product found: %s", url)
                    # Build full URL for scraping
                    full_product_url = f"{scraper.base_url}{url}"
                    product = scraper.extract_product_data(full_product_url)

                    if product:
                        product.metal_type = "gold"
                        product.product_type = product_type
                        product_manager.save_product(product)
                        total_new += 1
                        # Add delay after scraping a new product
                        time.sleep(scraper.config.get_random_delay())
                    else:
                        logger.warning("Failed to extract data from %s", url)
                        continue

                # Add price entry (for both new and existing products)
                product_manager.add_price_entry(
                    url=url, sell_price_eur=price_data["sell_price_eur"], buy_price_eur=price_data["buy_price_eur"]
                )
                total_updated += 1

    logger.info("Total products updated: %d", total_updated)
    logger.info("New products added: %d", total_new)

    # Get latest prices for all products
    latest_prices = product_manager.get_latest_prices("gold")

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
    logger.info("\n=== Gold Products Summary ===")
    logger.info("Total products: %d", len(sorted_products))

    # Top 5 by price per gram
    logger.info("\nTop 5 Best Prices (per gram fine gold):")
    for i, item in enumerate(sorted_products[:5], 1):
        name = item.get("product_name", "")
        name = name[:60] + "..." if len(name) > 60 else name
        logger.info("%d. %s (%s)", i, name, item.get("product_type", ""))
        logger.info("   Price per gram: %.2f EUR", item.get("price_per_g_fine_eur", 0))
        logger.info("   Sell: %.2f EUR | Buy: %.2f EUR", item.get("sell_price_eur", 0), item.get("buy_price_eur", 0))

    # Top 5 by spread
    spread_sorted = sorted(
        [p for p in sorted_products if p.get("spread_percentage") is not None],
        key=lambda x: x.get("spread_percentage", 0),
    )

    if spread_sorted:
        logger.info("\nTop 5 Best Spreads:")
        for i, item in enumerate(spread_sorted[:5], 1):
            name = item.get("product_name", "")
            name = name[:60] + "..." if len(name) > 60 else name
            logger.info("%d. %s (%s)", i, name, item.get("product_type", ""))
            logger.info("   Spread: %.2f%%", item.get("spread_percentage", 0))

    scraper.cleanup()


if __name__ == "__main__":
    main()
