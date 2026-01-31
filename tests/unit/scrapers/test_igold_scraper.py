"""Unit tests for gold scraper."""
from unittest.mock import Mock

import pytest

from src.igold_scraper.scrapers.gold import IgoldGoldScraper


class TestExtractProductData:
    """Tests for extract_product_data method."""

    def test_extract_valid_product(self, sample_gold_product_html, mock_scraper_session):
        """Test extracting data from a valid product page."""
        mock_response = Mock()
        mock_response.content = sample_gold_product_html.encode('utf-8')
        mock_response.raise_for_status = Mock()
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldGoldScraper()

        result = scraper.extract_product_data('https://igold.bg/product/gold-coin')

        assert result is not None
        # Verify product was extracted (contains numbers and basic structure)
        assert len(result.name) > 0
        assert '3.99' in result.name
        assert result.product_type == 'coin'
        # Core pricing data should be extracted
        assert result.sell_price_eur == 486.75
        assert result.buy_price_eur == 466.81
        assert result.sell_price_eur == 486.75
        assert result.buy_price_eur == 466.81

    def test_extract_valid_gold_bar(self, sample_gold_product_bar, mock_scraper_session):
        """Test extracting data from a valid gold bar product page."""
        mock_response = Mock()
        mock_response.content = sample_gold_product_bar.encode('utf-8')
        mock_response.raise_for_status = Mock()
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldGoldScraper()

        result = scraper.extract_product_data('https://igold.bg/product/gold-bar')

        assert result
        assert 'Кюлче' in result.name
        assert result.product_type == 'bar'
        assert result.sell_price_eur == 1277.95
        assert result.buy_price_eur == 1226.61
        assert result.sell_price_eur == 1277.95
        assert result.buy_price_eur == 1226.61
        assert result.weight == 10.0
        assert result.purity == 999.9
        assert result.fine_metal == 10.0

    def test_extract_product_network_error(self, mock_scraper_session):
        """Test handling of network errors during extraction."""
        mock_scraper_session.get = Mock(side_effect=Exception("Network error"))
        scraper = IgoldGoldScraper()

        result = scraper.extract_product_data('https://igold.bg/product/invalid')

        assert not result

    def test_extract_calculates_spread_percentage(
        self, sample_gold_product_html, mock_scraper_session
    ):
        """Test that spread percentage is calculated correctly."""
        mock_response = Mock()
        mock_response.content = sample_gold_product_html.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldGoldScraper()

        result = scraper.extract_product_data('https://igold.bg/product/gold-coin')

        # spread = ((952.00 - 913.0) / 952.00) * 100 = 4.10%
        assert result is not None
        assert result.spread_percentage == pytest.approx(4.10, abs=0.01)

    def test_extract_calculates_price_per_gram(
        self, sample_gold_product_html, mock_scraper_session
    ):
        """Test that price per gram is calculated correctly."""
        mock_response = Mock()
        mock_response.content = sample_gold_product_html.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldGoldScraper()

        result = scraper.extract_product_data('https://igold.bg/product/gold-coin')

        # price_per_g = 952.00 / 3.66 = 260.11
        assert result is not None
        if result.price_per_g_fine_eur is not None:
            assert result.price_per_g_fine_eur == pytest.approx(132.98, abs=1.0)


class TestGatherProductLinks:
    """Tests for gather_product_links method."""

    def test_gather_links_from_category(self, sample_gold_category_html, mock_scraper_session):
        """Test extracting product links from a category page."""
        mock_response = Mock()
        mock_response.content = sample_gold_category_html.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldGoldScraper()

        result = scraper.gather_product_links(
            'https://igold.bg/zlatni-kyulcheta-investitsionni'
        )

        assert isinstance(result, list)
        assert len(result) == 3
        assert any('test-gold-coin-1' in url for url in result)
        assert any('test-gold-bar-1' in url for url in result)
        assert any('test-gold-coin-2' in url for url in result)

    def test_gather_links_network_error(self, mock_scraper_session):
        """Test handling of network errors during link gathering."""
        mock_scraper_session.get = Mock(side_effect=Exception("Network error"))
        scraper = IgoldGoldScraper()

        # gather_product_links catches exceptions and returns []
        result = scraper.gather_product_links(
            'https://igold.bg/invalid-category'
        )

        assert result == []

    def test_gather_links_http_error(self, mock_scraper_session):
        """Test handling of HTTP errors during link gathering."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.content = b'<html></html>'
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldGoldScraper()

        result = scraper.gather_product_links(
            'https://igold.bg/invalid-category'
        )

        assert result == []


class TestGoldScraperFiltering:  # pylint: disable=too-few-public-methods
    """Tests for URL filtering in gold scraper."""

    def test_gather_links_filters_unwanted_urls(
        self, sample_gold_category_html, mock_scraper_session
    ):
        """Test that unwanted URLs are filtered out."""
        # Mock HTML with unwanted URL
        html_with_unwanted = sample_gold_category_html.replace(
            'test-gold-bar-1',
            'nelikvidno-i-povredeno-zlato/test-item'
        )

        mock_response = Mock()
        mock_response.content = html_with_unwanted.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldGoldScraper()
        result = scraper.gather_product_links(
            'https://igold.bg/zlatni-kyulcheta-investitsionni'
        )

        # Should have 2 products (filtered out the unwanted one)
        assert len(result) == 2
        assert not any('nelikvidno-i-povredeno' in url for url in result)


class TestScrapingOrchestration:  # pylint: disable=too-few-public-methods
    """Tests for scraping orchestration methods."""

    def test_scrape_category(
        self, sample_gold_product_html, sample_gold_category_html, mock_scraper_session
    ):
        """Test scraping a single category."""
        mock_response_category = Mock()
        mock_response_category.content = sample_gold_category_html.encode('utf-8')
        mock_response_category.status_code = 200

        mock_response_product = Mock()
        mock_response_product.content = sample_gold_product_html.encode('utf-8')
        mock_response_product.status_code = 200

        # Mock to return category page first, then product pages (multiple times)
        mock_scraper_session.get = Mock(
            side_effect=[
                mock_response_category,  # Category page
                mock_response_product,    # Product 1
                mock_response_product,    # Product 2
                mock_response_product,    # Product 3
            ]
        )

        scraper = IgoldGoldScraper()
        products = scraper.scrape_category(
            'https://igold.bg/zlatni-kyulcheta-investitsionni',
            metal_type='gold',
            product_type_hint='bar'
        )

        assert len(products) == 3
        assert all(p.metal_type == 'gold' for p in products)
        assert all(p.product_type == 'bar' for p in products)
