#!/usr/bin/env python3
"""
Base scraper class for precious metals scrapers.
Provides common functionality for gold and silver scraping.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
import time
import random
import logging
from dataclasses import dataclass, field
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class ScraperConfig:
    """Configuration for scraper behavior"""

    base_url: str
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    request_timeout: int = 30
    delay_min: float = 1.0
    delay_max: float = 2.5
    retry_attempts: int = 3
    retry_backoff: float = 1.5

    def get_random_delay(self) -> float:
        """Get random delay between min and max"""
        return random.uniform(self.delay_min, self.delay_max)


@dataclass
class Product:
    """Data class representing a precious metal product"""

    name: str
    url: str
    metal_type: str  # 'gold' or 'silver'
    product_type: str  # 'bar', 'coin', or 'unknown'
    weight: Optional[float] = None
    purity: Optional[float] = None  # per mille (0-1000)
    fine_metal: Optional[float] = None
    sell_price_eur: Optional[float] = None
    buy_price_eur: Optional[float] = None
    price_per_g_fine_eur: Optional[float] = None
    scrape_time: datetime = field(default_factory=datetime.now)

    @property
    def spread_percentage(self) -> Optional[float]:
        """Calculate bid-ask spread percentage"""
        if self.sell_price_eur and self.sell_price_eur > 0 and self.buy_price_eur is not None:
            return round(
                ((self.sell_price_eur - self.buy_price_eur) / self.sell_price_eur) * 100, 2
            )
        return None

    @property
    def is_valid(self) -> bool:
        """Check if product has essential data (name and at least one price)"""
        has_sell = self.sell_price_eur is not None and self.sell_price_eur > 0
        has_buy = self.buy_price_eur is not None and self.buy_price_eur > 0
        return bool(self.name and (has_sell or has_buy))

    def to_dict(self) -> Dict:
        """Convert to dictionary for CSV/JSON export"""
        return {
            "product_name": self.name,
            "url": self.url,
            "product_type": self.product_type,
            "metal_type": self.metal_type,
            "total_weight_g": self.weight,
            "purity_per_mille": self.purity,
            "fine_metal_g": self.fine_metal,
            "sell_price_eur": self.sell_price_eur,
            "buy_price_eur": self.buy_price_eur,
            "price_per_g_fine_eur": self.price_per_g_fine_eur,
            "spread_percentage": self.spread_percentage,
        }


class BaseScraper(ABC):
    """
    Abstract base class for precious metal scrapers.

    Provides common functionality like HTTP requests, retries, and rate limiting.
    Subclasses should implement the parsing logic specific to each site.
    """

    def __init__(self, config: ScraperConfig):
        """
        Initialize scraper with configuration.

        Args:
            config: ScraperConfig instance with scraper settings
        """
        self.config = config
        self.session = self._create_session()
        self.products: List[Product] = []
        self.failed_urls: List[Tuple[str, str]] = []  # (url, error_message)

    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy"""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.retry_attempts,
            backoff_factor=self.config.retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set headers
        session.headers.update(
            {
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        return session

    def _fetch_page(self, url: str) -> Optional[requests.Response]:
        """
        Fetch a page with rate limiting, retry logic, and error handling.

        Args:
            url: URL to fetch

        Returns:
            Response object or None if failed after all retries
        """
        last_error = None

        for attempt in range(1, self.config.retry_attempts + 1):
            try:
                # Add delay before request (not on first attempt of first request)
                time.sleep(self.config.get_random_delay())

                logger.debug("Fetching: %s (attempt %d/%d)", url, attempt, self.config.retry_attempts)
                response = self.session.get(url, timeout=self.config.request_timeout)
                response.raise_for_status()

                # Success - log if this wasn't the first attempt
                if attempt > 1:
                    logger.info("Successfully fetched %s on attempt %d", url, attempt)

                return response

            except requests.Timeout:
                last_error = f"Timeout after {self.config.request_timeout}s"
                logger.warning("Attempt %d/%d failed for %s: %s",
                             attempt, self.config.retry_attempts, url, last_error)
                if attempt < self.config.retry_attempts:
                    backoff_delay = self.config.retry_backoff ** attempt
                    logger.debug("Retrying after %.1fs backoff...", backoff_delay)
                    time.sleep(backoff_delay)

            except requests.HTTPError as e:
                status_code = e.response.status_code
                last_error = f"HTTP {status_code}"

                # Don't retry on client errors (4xx except 429)
                if 400 <= status_code < 500 and status_code != 429:
                    logger.warning("Client error for %s: %s (not retrying)", url, last_error)
                    break

                logger.warning("Attempt %d/%d failed for %s: %s",
                             attempt, self.config.retry_attempts, url, last_error)
                if attempt < self.config.retry_attempts:
                    backoff_delay = self.config.retry_backoff ** attempt
                    logger.debug("Retrying after %.1fs backoff...", backoff_delay)
                    time.sleep(backoff_delay)

            except requests.ConnectionError as e:
                last_error = f"Connection error: {str(e)[:100]}"
                logger.warning("Attempt %d/%d failed for %s: %s",
                             attempt, self.config.retry_attempts, url, last_error)
                if attempt < self.config.retry_attempts:
                    backoff_delay = self.config.retry_backoff ** attempt
                    logger.debug("Retrying after %.1fs backoff...", backoff_delay)
                    time.sleep(backoff_delay)

            except Exception as e:
                last_error = f"Unexpected error: {str(e)[:100]}"
                logger.error("Attempt %d/%d failed for %s: %s",
                           attempt, self.config.retry_attempts, url, last_error)
                if attempt < self.config.retry_attempts:
                    backoff_delay = self.config.retry_backoff ** attempt
                    logger.debug("Retrying after %.1fs backoff...", backoff_delay)
                    time.sleep(backoff_delay)

        # All retries exhausted
        logger.error("Failed to fetch %s after %d attempts. Last error: %s",
                    url, self.config.retry_attempts, last_error)
        self.failed_urls.append((url, last_error or "Unknown error"))
        return None

    @abstractmethod
    def gather_product_links(self, category_url: str) -> List[str]:
        """
        Extract product URLs from a category page.

        Must be implemented by subclasses.

        Args:
            category_url: URL of category/listing page

        Returns:
            List of product URLs
        """

    @abstractmethod
    def extract_product_data(self, url: str) -> Optional[Product]:
        """
        Extract product details from a product page.

        Must be implemented by subclasses.

        Args:
            url: URL of product detail page

        Returns:
            Product object or None if extraction failed
        """

    def scrape_category(
        self, category_url: str, metal_type: str, product_type_hint: Optional[str] = None
    ) -> List[Product]:
        """
        Scrape all products from a category page.

        Args:
            category_url: URL of category page
            metal_type: Type of metal ('gold' or 'silver')
            product_type_hint: Hint for product type ('bar' or 'coin')

        Returns:
            List of Product objects
        """
        logger.info("Scraping category: %s", category_url)
        products = []

        # Get product links
        product_urls = self.gather_product_links(category_url)
        logger.info("Found %d products in category", len(product_urls))

        if not product_urls:
            logger.warning("No products found in %s", category_url)
            return products

        # Extract data from each product
        for i, product_url in enumerate(product_urls, 1):
            logger.debug("Processing product %d/%d: %s", i, len(product_urls), product_url)
            product = self.extract_product_data(product_url)

            if product:
                product.metal_type = metal_type
                if product_type_hint:
                    product.product_type = product_type_hint
                products.append(product)
            else:
                logger.debug("Failed to extract data from %s", product_url)

        logger.info("Successfully scraped %d products from category", len(products))
        return products

    def scrape_all(self, category_urls: Dict[str, List[str]], metal_type: str) -> List[Product]:
        """
        Scrape all categories and product types.

        Args:
            category_urls: Dict mapping product type to list of category URLs
                          {'bar': ['url1', 'url2'], 'coin': ['url3']}
            metal_type: Type of metal ('gold' or 'silver')

        Returns:
            List of all Product objects
        """
        all_products = []

        for product_type, urls in category_urls.items():
            logger.info("Starting to scrape %s products (%d categories)", product_type, len(urls))

            for category_url in urls:
                products = self.scrape_category(category_url, metal_type, product_type)
                all_products.extend(products)

        logger.info(
            "Scraping complete. Total products: %d, Failed URLs: %d",
            len(all_products),
            len(self.failed_urls),
        )

        if self.failed_urls:
            logger.warning("Failed to fetch %d URLs:", len(self.failed_urls))
            for url, error in self.failed_urls[:5]:  # Show first 5
                logger.warning("  - %s: %s", url, error)

        return all_products

    def sort_products(
        self, products: List[Product], primary_key: str = "price_per_g_fine_eur"
    ) -> List[Product]:
        """
        Sort products by price per gram, with items lacking prices at the end.

        Args:
            products: List of products to sort
            primary_key: Field to sort by

        Returns:
            Sorted list of products
        """

        def sort_key(product):
            key_value = getattr(product, primary_key, None)
            if key_value is not None:
                return (0, key_value)  # Has price: sort numerically
            return (1, 0)  # No price: sort to end

        return sorted(products, key=sort_key)

    def cleanup(self):
        """Clean up resources (close session, etc.)"""
        self.session.close()
        logger.debug("Scraper session closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("This is a base class. Use IgoldScraper or IgoldSilverScraper instead.")
