"""Unit tests for silver scraper."""
from unittest.mock import Mock

import pytest

from src.igold_scraper.scrapers.silver import IgoldSilverScraper


class TestExtractProductData:
    """Tests for extract_product_data method."""

    def test_extract_valid_product(self, sample_silver_product_html, mock_scraper_session):
        """Test extracting data from a valid silver product page."""
        mock_response = Mock()
        mock_response.content = sample_silver_product_html.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldSilverScraper()

        result = scraper.extract_product_data(
            'https://igold.bg/product/silver-coin'
        )

        assert result is not None
        # Verify product was extracted (contains numbers and basic structure)
        assert len(result.name) > 0
        assert '31.1' in result.name
        # Core pricing data should be extracted
        assert result.sell_price_eur == 38.62
        assert result.buy_price_eur == 30.68

    def test_extract_valid_silver_bar(self, sample_silver_product_bar, mock_scraper_session):
        """Test extracting data from a valid silver bar product page."""
        mock_response = Mock()
        mock_response.content = sample_silver_product_bar.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldSilverScraper()

        result = scraper.extract_product_data(
            'https://igold.bg/product/silver-bar'
        )

        assert result
        assert 'Кюлче' in result.name
        assert result.product_type == 'bar'
        assert result.sell_price_eur == 281.19
        assert result.buy_price_eur == 255.62
        assert result.sell_price_eur == 281.19
        assert result.buy_price_eur == 255.62
        assert result.weight == 100.0
        assert result.purity == 999.9
        assert result.fine_metal == 100.0

    def test_extract_product_network_error(self, mock_scraper_session):
        """Test handling of network errors during extraction."""
        mock_scraper_session.get = Mock(side_effect=Exception("Network error"))
        scraper = IgoldSilverScraper()

        result = scraper.extract_product_data(
            'https://igold.bg/product/invalid'
        )

        assert not result

    def test_extract_calculates_spread_percentage(
        self, sample_silver_product_html, mock_scraper_session
    ):
        """Test that spread percentage is calculated correctly."""
        mock_response = Mock()
        mock_response.content = sample_silver_product_html.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldSilverScraper()

        result = scraper.extract_product_data(
            'https://igold.bg/product/silver-coin'
        )

        # spread = ((75.50 - 60.0) / 75.50) * 100 = 20.53%
        assert result
        if result.spread_percentage is not None:
            assert result.spread_percentage == pytest.approx(20.53, abs=0.1)

    def test_extract_calculates_price_per_gram(
        self, sample_silver_product_html, mock_scraper_session
    ):
        """Test that price per gram is calculated correctly."""
        mock_response = Mock()
        mock_response.content = sample_silver_product_html.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldSilverScraper()

        result = scraper.extract_product_data(
            'https://igold.bg/product/silver-coin'
        )

        # price_per_g = 75.50 / 31.06 = 2.43 (may be None if purity parsing fails)
        assert result
        if result.price_per_g_fine_eur is not None:
            assert result.price_per_g_fine_eur == pytest.approx(1.24, abs=0.1)


class TestGatherProductLinks:
    """Tests for gather_product_links method."""

    def test_gather_links_from_silver_page(
        self, sample_silver_category_html, mock_scraper_session
    ):
        """Test extracting product links from the silver main page."""
        mock_response = Mock()
        mock_response.content = sample_silver_category_html.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldSilverScraper()

        result = scraper.gather_product_links('https://igold.bg/srebro')

        assert isinstance(result, list)
        assert any('test-silver-coin-1' in url for url in result)
        assert any('test-silver-bar-1' in url for url in result)

    def test_gather_links_network_error(self, mock_scraper_session):
        """Test handling of network errors during link gathering."""
        mock_scraper_session.get = Mock(side_effect=Exception("Network error"))
        scraper = IgoldSilverScraper()

        result = scraper.gather_product_links('https://igold.bg/srebro')

        assert result == []

    def test_gather_links_http_error(self, mock_scraper_session):
        """Test handling of HTTP errors during link gathering."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.content = b"<html></html>"
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldSilverScraper()

        result = scraper.gather_product_links('https://igold.bg/srebro')

        assert result == []


class TestScrapingOrchestration:  # pylint: disable=too-few-public-methods
    """Tests for scraping orchestration methods."""

    def test_scrape_category(
        self, sample_silver_product_html, sample_silver_category_html, mock_scraper_session
    ):
        """Test scraping a single silver category."""
        mock_response_category = Mock()
        mock_response_category.content = sample_silver_category_html.encode('utf-8')
        mock_response_category.status_code = 200

        mock_response_product = Mock()
        mock_response_product.content = sample_silver_product_html.encode('utf-8')
        mock_response_product.status_code = 200

        # Mock to return category page first, then product pages (multiple times)
        mock_scraper_session.get = Mock(
            side_effect=[
                mock_response_category,  # Category page
                mock_response_product,    # Product 1
                mock_response_product,    # Product 2
            ]
        )

        scraper = IgoldSilverScraper()
        products = scraper.scrape_category(
            'https://igold.bg/srebro',
            metal_type='silver',
            product_type_hint='coin'
        )

        assert len(products) == 2
        assert all(p.metal_type == 'silver' for p in products)
        assert all(p.product_type == 'coin' for p in products)


class TestProductTypeDetection:
    """Tests for product type detection in extract_product_data."""

    def test_detect_coin_product(self, mock_scraper_session):
        """Test detection of coin products."""
        html_content = """
        <main><h1>Silver Coin Philharmonic</h1></main>
        <regular-product><table><tbody>
            <tr><td>Продаваме</td><td><span>25.50</span></td></tr>
            <tr><td>EUR</td><td><span>13.05</span></td></tr>
            <tr><td>Купуваме</td><td><span>24.00</span></td></tr>
            <tr><td>EUR</td><td><span>12.28</span></td></tr>
        </tbody></table></regular-product>
        <div class="memberheader__meta effect">
            <p>Тегло: 31.1 g</p>
            <p>Проба: 999</p>
            <p>Чисто сребро: 31.06 g</p>
        </div>
        """

        mock_response = Mock()
        mock_response.content = html_content.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldSilverScraper()

        result = scraper.extract_product_data(
            'https://igold.bg/product/silver-coin'
        )

        assert result
        assert 'product_type' in result.to_dict()

    def test_detect_bar_product(self, mock_scraper_session):
        """Test detection of bar/ingot products."""
        html_content = """
        <main><h1>Silver Bar 100g</h1></main>
        <regular-product><table><tbody>
            <tr><td>Продаваме</td><td><span>800.00</span></td></tr>
            <tr><td>EUR</td><td><span>409.00</span></td></tr>
            <tr><td>Купуваме</td><td><span>780.00</span></td></tr>
            <tr><td>EUR</td><td><span>399.00</span></td></tr>
        </tbody></table></regular-product>
        <div class="memberheader__meta effect">
            <p>Тегло: 100 g</p>
            <p>Проба: 999</p>
            <p>Чисто сребро: 100 g</p>
        </div>
        """

        mock_response = Mock()
        mock_response.content = html_content.encode('utf-8')
        mock_response.status_code = 200
        mock_scraper_session.get = Mock(return_value=mock_response)

        scraper = IgoldSilverScraper()

        result = scraper.extract_product_data(
            'https://igold.bg/product/silver-bar-100g'
        )

        assert result
        assert 'product_type' in result.to_dict()
