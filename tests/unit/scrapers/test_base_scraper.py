"""Unit tests for BaseScraper class."""
from unittest.mock import Mock

import requests

from src.igold_scraper.scrapers.base import BaseScraper, Product, ScraperConfig


class ConcreteScraper(BaseScraper):
    """Concrete implementation of BaseScraper for testing."""

    def __init__(self):
        config = ScraperConfig(base_url="https://example.com")
        super().__init__(config)

    def gather_product_links(self, category_url: str):
        """Concrete implementation for testing."""
        response = self._fetch_page(category_url)
        if response:
            return ["https://example.com/product1", "https://example.com/product2"]
        return []

    def extract_product_data(self, url: str):
        """Concrete implementation for testing."""
        response = self._fetch_page(url)
        if response:
            return Product(
                name="Test Product",
                url=url,
                metal_type="gold",
                product_type="coin",
                weight=31.1,
                purity=999,
                sell_price_eur=100.0,
                buy_price_eur=90.0,
            )
        return None


class TestBaseScraper:
    """Tests for BaseScraper base functionality."""

    def test_init_creates_session(self, mock_scraper_session):  # pylint: disable=unused-argument
        """Test that initialization creates a session."""
        scraper = ConcreteScraper()
        assert scraper.session is not None
        assert not scraper.failed_urls

    def test_fetch_page_success(self, mock_scraper_session):
        """Test successful page fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"<html>Test</html>"
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = ConcreteScraper()
        response = scraper._fetch_page("https://example.com/test")  # pylint: disable=protected-access

        assert response is not None
        assert response.status_code == 200

    def test_fetch_page_timeout(self, mock_scraper_session):
        """Test handling of timeout errors."""
        mock_scraper_session.get = Mock(side_effect=requests.Timeout())

        scraper = ConcreteScraper()
        response = scraper._fetch_page("https://example.com/test")  # pylint: disable=protected-access

        assert response is None
        assert len(scraper.failed_urls) == 1
        assert scraper.failed_urls[0][0] == "https://example.com/test"
        assert "Timeout" in scraper.failed_urls[0][1]

    def test_fetch_page_http_error(self, mock_scraper_session):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status = Mock(
            side_effect=requests.HTTPError(response=mock_response)
        )
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = ConcreteScraper()
        response = scraper._fetch_page("https://example.com/test")  # pylint: disable=protected-access

        assert response is None
        assert len(scraper.failed_urls) == 1
        assert "HTTP 404" in scraper.failed_urls[0][1]

    def test_fetch_page_general_exception(self, mock_scraper_session):
        """Test handling of general exceptions."""
        mock_scraper_session.get = Mock(side_effect=Exception("Network error"))

        scraper = ConcreteScraper()
        response = scraper._fetch_page("https://example.com/test")  # pylint: disable=protected-access

        assert response is None
        assert len(scraper.failed_urls) == 1
        assert "Network error" in scraper.failed_urls[0][1]

    def test_scrape_category(self, mock_scraper_session):
        """Test scraping a category page."""
        # Mock successful responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"<html>Test</html>"
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = ConcreteScraper()
        products = scraper.scrape_category(
            "https://example.com/category",
            metal_type="gold",
            product_type_hint="coin"
        )

        assert len(products) == 2
        assert all(p.metal_type == "gold" for p in products)
        assert all(p.product_type == "coin" for p in products)

    def test_scrape_category_no_products(self, mock_scraper_session):
        """Test scraping category with no products."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = ConcreteScraper()
        # Override gather_product_links to return empty list
        scraper.gather_product_links = Mock(return_value=[])

        products = scraper.scrape_category(
            "https://example.com/category",
            metal_type="gold"
        )

        assert len(products) == 0

    def test_scrape_all(self, mock_scraper_session):
        """Test scraping all categories."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"<html>Test</html>"
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = ConcreteScraper()
        category_urls = {
            "coin": ["https://example.com/coins"],
            "bar": ["https://example.com/bars"]
        }

        products = scraper.scrape_all(category_urls, metal_type="gold")

        # Should have 2 products from each category (4 total)
        assert len(products) == 4
        assert all(p.metal_type == "gold" for p in products)

    def test_sort_products(self, mock_scraper_session):  # pylint: disable=unused-argument
        """Test sorting products by price per gram."""
        scraper = ConcreteScraper()

        products = [
            Product(
                name="Expensive",
                url="https://example.com/expensive",
                metal_type="gold",
                product_type="coin",
                weight=31.1,
                purity=999,
                sell_price_eur=100.0,
                buy_price_eur=90.0,
                price_per_g_fine_eur=3.2
            ),
            Product(
                name="No Price",
                url="https://example.com/noprice",
                metal_type="gold",
                product_type="coin",
                weight=31.1,
                purity=999,
                sell_price_eur=100.0,
                buy_price_eur=90.0,
                price_per_g_fine_eur=None
            ),
            Product(
                name="Cheap",
                url="https://example.com/cheap",
                metal_type="gold",
                product_type="coin",
                weight=31.1,
                purity=999,
                sell_price_eur=80.0,
                buy_price_eur=70.0,
                price_per_g_fine_eur=2.5
            ),
        ]

        sorted_products = scraper.sort_products(products)

        # Check order: cheap first, expensive second, no price last
        assert sorted_products[0].name == "Cheap"
        assert sorted_products[1].name == "Expensive"
        assert sorted_products[2].name == "No Price"

    def test_cleanup_closes_session(self, mock_scraper_session):
        """Test cleanup closes the session."""
        scraper = ConcreteScraper()
        scraper.cleanup()

        mock_scraper_session.close.assert_called_once()

    def test_context_manager(self, mock_scraper_session):
        """Test using scraper as context manager."""
        with ConcreteScraper() as scraper:
            assert scraper is not None

        # Session should be closed after exiting context
        mock_scraper_session.close.assert_called_once()


class TestScraperConfig:
    """Tests for ScraperConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ScraperConfig(base_url="https://example.com")

        assert config.base_url == "https://example.com"
        assert config.request_timeout == 30
        assert config.delay_min == 1.0
        assert config.delay_max == 2.5
        assert config.retry_attempts == 3
        assert config.retry_backoff == 1.5

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ScraperConfig(
            base_url="https://example.com",
            request_timeout=60,
            delay_min=0.5,
            delay_max=1.0,
            retry_attempts=5,
            retry_backoff=2.0
        )

        assert config.request_timeout == 60
        assert config.delay_min == 0.5
        assert config.delay_max == 1.0
        assert config.retry_attempts == 5
        assert config.retry_backoff == 2.0

    def test_get_random_delay(self):
        """Test random delay is within bounds."""
        config = ScraperConfig(base_url="https://example.com", delay_min=1.0, delay_max=2.0)

        for _ in range(10):
            delay = config.get_random_delay()
            assert 1.0 <= delay <= 2.0


class TestProduct:
    """Tests for Product dataclass."""

    def test_product_creation(self):
        """Test creating a Product instance."""
        product = Product(
            name="Test Coin",
            url="https://example.com/coin",
            metal_type="gold",
            product_type="coin",
            weight=31.1,
            purity=999,
            sell_price_eur=100.0,
            buy_price_eur=90.0
        )

        assert product.name == "Test Coin"
        assert product.url == "https://example.com/coin"
        assert product.metal_type == "gold"
        assert product.product_type == "coin"
        assert product.weight == 31.1
        assert product.purity == 999
        assert product.sell_price_eur == 100.0
        assert product.buy_price_eur == 90.0

    def test_product_to_dict(self):
        """Test converting Product to dictionary."""
        product = Product(
            name="Test Coin",
            url="https://example.com/coin",
            metal_type="gold",
            product_type="coin",
            weight=31.1,
            purity=999,
            sell_price_eur=100.0,
            buy_price_eur=90.0
        )

        product_dict = product.to_dict()

        assert product_dict["product_name"] == "Test Coin"
        assert product_dict["url"] == "https://example.com/coin"
        assert product_dict["metal_type"] == "gold"
        assert product_dict["product_type"] == "coin"
        assert product_dict["total_weight_g"] == 31.1
