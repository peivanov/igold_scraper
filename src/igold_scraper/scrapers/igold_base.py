#!/usr/bin/env python3
"""
Base scraper for igold.bg website.
Contains shared logic for both gold and silver scrapers.
"""

import re
import logging
from typing import Optional, List, Dict
from urllib.parse import urljoin, urlparse

from lxml import html

from igold_scraper.scrapers.base import BaseScraper, ScraperConfig, Product
from igold_scraper.config import get_config
from igold_scraper.utils.parsing import parse_weight, parse_purity
from igold_scraper.constants import xpaths

logger = logging.getLogger(__name__)


class IgoldBaseScraper(BaseScraper):
    """
    Base scraper for igold.bg website.
    Contains shared parsing logic for both gold and silver products.
    """

    def __init__(self, metal_type: str):
        """
        Initialize igold scraper.

        Args:
            metal_type: Either 'gold' or 'silver'
        """
        config_obj = get_config()

        # Create ScraperConfig from app config
        scraper_config = ScraperConfig(
            base_url=config_obj.IGOLD_BASE_URL,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            request_timeout=config_obj.REQUEST_TIMEOUT,
            delay_min=config_obj.SCRAPE_DELAY_MIN,
            delay_max=config_obj.SCRAPE_DELAY_MAX,
        )

        super().__init__(scraper_config)
        self.metal_type = metal_type
        self.base_url = config_obj.IGOLD_BASE_URL

    def gather_product_links(self, category_url: str) -> List[str]:
        """
        Collect product links from category pages using XPath.

        Args:
            category_url: URL of category page

        Returns:
            List of product URLs
        """
        logger.info("Scanning page: %s", category_url)

        response = self._fetch_page(category_url)
        if not response:
            return []

        tree = html.fromstring(response.content)

        # Extract product links
        product_hrefs = tree.xpath(xpaths.CATEGORY_PRODUCT_LINKS)

        # Convert to absolute URLs
        product_urls = [urljoin(self.base_url, href) for href in product_hrefs]

        logger.info("Found %d product links on %s", len(product_urls), category_url)

        # Log titles in debug mode
        if logger.level <= logging.DEBUG and product_urls:
            product_links = tree.xpath(xpaths.CATEGORY_PRODUCT_ELEMENTS)
            for link in product_links:
                h2_text = link.xpath(xpaths.CATEGORY_PRODUCT_TITLE)
                if h2_text:
                    url = urljoin(self.base_url, link.get("href"))
                    logger.debug("  Found: %s -> %s", h2_text.strip(), url)

        return sorted(product_urls)

    def extract_category_prices(self, category_url: str) -> List[Dict]:
        """
        Extract prices directly from category page without visiting individual pages.

        Args:
            category_url: URL of category page

        Returns:
            List of dicts with url, sell_price_eur, buy_price_eur
        """
        logger.info("Extracting prices from category: %s", category_url)

        response = self._fetch_page(category_url)
        if not response:
            return []

        tree = html.fromstring(response.content)

        # Extract product items
        product_items = tree.xpath(xpaths.CATEGORY_PRODUCT_ITEMS)

        prices = []
        for item in product_items:
            try:
                # Extract URL
                url = item.xpath(xpaths.CATEGORY_ITEM_URL)
                if not url:
                    continue

                # Normalize to relative URL (remove base URL if present)
                if url.startswith('http'):
                    parsed = urlparse(url)
                    url = parsed.path

                # Extract prices
                buy_price_str = item.xpath(xpaths.CATEGORY_ITEM_BUY_PRICE_EUR)
                sell_price_str = item.xpath(xpaths.CATEGORY_ITEM_SELL_PRICE_EUR)

                # Parse prices (remove "€" and whitespace, handle various formats)
                buy_price_eur = None
                sell_price_eur = None

                if buy_price_str:
                    try:
                        # Remove currency symbols, non-breaking spaces, and normalize
                        cleaned = buy_price_str.replace('€', '').replace('\xa0', '').replace(',', '.').strip()
                        buy_price_eur = float(cleaned)
                    except (ValueError, AttributeError) as e:
                        logger.debug("Failed to parse buy price '%s': %s", buy_price_str, e)

                if sell_price_str:
                    try:
                        cleaned = sell_price_str.replace('€', '').replace('\xa0', '').replace(',', '.').strip()
                        sell_price_eur = float(cleaned)
                    except (ValueError, AttributeError) as e:
                        logger.debug("Failed to parse sell price '%s': %s", sell_price_str, e)

                # Validate and add if we have at least one valid price
                # Only track products igold.bg sells (not buy-only products)
                has_sell = sell_price_eur and sell_price_eur > 0

                if has_sell:  # Only store if they actually sell this product
                    prices.append({
                        'url': url,
                        'sell_price_eur': sell_price_eur or 0.0,  # Use 0 if not available
                        'buy_price_eur': buy_price_eur or 0.0      # Use 0 if not available
                    })
                else:
                    logger.debug(
                        "Skipping item %s: no valid prices found (sell=%.2f, buy=%.2f)",
                        url, sell_price_eur or 0, buy_price_eur or 0
                    )

            except (ValueError, IndexError) as e:
                logger.debug("Failed to extract price from item: %s", e)
                continue

        logger.info("Extracted %d prices from category", len(prices))
        return prices

    def extract_product_data(self, url: str) -> Optional[Product]:
        """
        Extract product information from a product page.

        Args:
            url: URL of product detail page

        Returns:
            Product object or None if extraction failed
        """
        response = self._fetch_page(url)
        if not response:
            return None

        tree = html.fromstring(response.content)

        # Extract title
        title = tree.xpath(xpaths.PRODUCT_TITLE).strip()
        title = re.sub(r"\s+", " ", title)

        if not title:
            logger.warning("No title found for %s", url)
            return None

        # Detect product type from title
        product_type = self._detect_product_type(title)

        # Extract prices
        prices = self._extract_prices(tree)

        # Extract product details
        details = self._extract_product_details(tree)

        # Parse weight and purity
        weight = parse_weight(details.get("Тегло"))
        purity = parse_purity(details.get("Проба"))

        # Apply default purity if needed
        if purity is None:
            purity = self._get_default_purity(product_type)

        # Extract or calculate fine metal content
        fine_metal_label = "Чисто злато" if self.metal_type == "gold" else "Чисто сребро"
        fine_metal = parse_weight(details.get(fine_metal_label))

        if fine_metal is None and weight is not None and purity is not None:
            fine_metal = weight * (purity / 1000.0)

        # Calculate price per gram
        price_per_g_eur = None
        if fine_metal and fine_metal > 0:
            if prices["sell_eur"] and prices["sell_eur"] > 0:
                price_per_g_eur = round(prices["sell_eur"] / fine_metal, 2)

        # Extract relative URL path (remove base URL if present)
        relative_url = url
        if url.startswith('http'):
            parsed = urlparse(url)
            relative_url = parsed.path

        # Create Product object
        product = Product(
            name=title,
            url=relative_url,
            metal_type=self.metal_type,
            product_type=product_type,
            weight=weight,
            purity=purity,
            fine_metal=fine_metal,
            sell_price_eur=prices["sell_eur"],
            buy_price_eur=prices["buy_eur"],
            price_per_g_fine_eur=price_per_g_eur,
        )

        return product

    def _extract_prices(self, tree: html.HtmlElement) -> Dict[str, Optional[float]]:
        """
        Extract buy and sell prices from product page.

        Args:
            tree: lxml tree of product page

        Returns:
            Dictionary with EUR price keys
        """
        prices: Dict[str, Optional[float]] = {
            "sell_eur": None,
            "buy_eur": None,
        }

        # Sell prices
        try:
            sell_eur_str = tree.xpath(xpaths.PRICE_SELL_EUR).strip()
            if sell_eur_str:
                # Remove EUR symbol and whitespace, handle various formats
                cleaned = (
                    sell_eur_str.replace('€', '')
                    .replace('\xa0', '')
                    .replace(',', '.')
                    .strip()
                )
                prices["sell_eur"] = float(cleaned.split()[0])
        except (ValueError, IndexError):
            pass

        # Buy prices
        try:
            buy_eur_str = tree.xpath(xpaths.PRICE_BUY_EUR).strip()
            if buy_eur_str:
                # Remove EUR symbol and any whitespace, handle various formats
                cleaned = buy_eur_str.replace('€', '').replace('\xa0', '').replace(',', '.').strip()
                prices["buy_eur"] = float(cleaned.split()[0])
        except (ValueError, IndexError):
            pass

        return prices

    def _extract_product_details(self, tree: html.HtmlElement) -> Dict[str, str]:
        """
        Extract product details from the details container.

        Args:
            tree: lxml tree of product page

        Returns:
            Dictionary of detail key-value pairs
        """
        details_dict = {}

        details_container = tree.xpath(xpaths.PRODUCT_DETAILS_CONTAINER)

        if details_container:
            paragraphs = details_container[0].xpath(xpaths.PRODUCT_DETAILS_PARAGRAPHS)
            for p in paragraphs:
                text = p.text_content().strip()
                if text and ":" in text:
                    # Split on first colon only
                    key, value = text.split(":", 1)
                    details_dict[key.strip()] = value.strip()

        return details_dict

    def _detect_product_type(self, title: str) -> str:
        """
        Determine if the product is a bar or a coin based on title keywords.

        Args:
            title: Product title

        Returns:
            'bar', 'coin', or 'unknown'
        """
        if not title:
            return "unknown"

        title_lower = title.lower()

        # Check for coin indicators (монета, монети)
        if "монета" in title_lower or "монети" in title_lower:
            return "coin"

        # Check for bar indicators (кюлче)
        if "кюлче" in title_lower:
            return "bar"

        return "unknown"

    def _get_default_purity(self, product_type: str) -> Optional[float]:
        """
        Get default purity based on metal type and product type.

        Args:
            product_type: 'bar', 'coin', or 'unknown'

        Returns:
            Default purity or None
        """
        if self.metal_type == "silver":
            # Silver defaults
            if product_type == "bar":
                return 999.9  # Most investment silver bars are .9999
            if product_type == "coin":
                return 999.0  # Most modern investment silver coins are .999
            return 999.0  # Default for unknown silver products

        # No defaults for gold - purity should be explicit
        return None
