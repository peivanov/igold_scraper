"""Unit tests for live_price service."""

import json
import os
from unittest.mock import Mock, patch

import pytest
import requests

from igold_scraper.services.live_price import LivePriceFetcher
from igold_scraper.exceptions import ConfigurationError, NetworkError, ValidationError


class TestLivePriceFetcherInit:
    """Test LivePriceFetcher initialization."""

    def test_init_with_api_url(self):
        """Test initialization with API URL provided."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        assert fetcher.api_base_url == "https://api.example.com"

    def test_init_with_env_variable(self):
        """Test initialization with environment variable."""
        with patch.dict(os.environ, {"PRECIOUS_METALS_API_BASE": "https://env.api.com"}):
            fetcher = LivePriceFetcher()

            assert fetcher.api_base_url == "https://env.api.com"

    def test_init_without_api_url_raises_error(self):
        """Test that missing API URL raises ConfigurationError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError, match="PRECIOUS_METALS_API_BASE"):
                LivePriceFetcher()


class TestFetchLivePrice:
    """Test fetching live precious metals prices."""

    def test_fetch_gold_price_success(self):
        """Test successfully fetching gold price."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "ts": 1704067200000,  # Jan 1, 2024
                "spreadProfilePrices": [{"spreadProfile": "elite", "bid": 2000.00, "ask": 2010.00, "bidSpread": 0.5}],
            }
        ]

        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_live_price("XAU")

        assert result is not None
        assert result["metal"] == "XAU"
        assert result["metal_name"] == "gold"
        assert "prices" in result
        assert "eur_per_gram" in result["prices"]
        assert result["prices"]["eur_per_gram"]["mid"] > 0

    def test_fetch_silver_price_success(self):
        """Test successfully fetching silver price."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "ts": 1704067200000,
                "spreadProfilePrices": [{"spreadProfile": "elite", "bid": 24.00, "ask": 24.50, "bidSpread": 0.25}],
            }
        ]

        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_live_price("XAG")

        assert result is not None
        assert result["metal"] == "XAG"
        assert result["metal_name"] == "silver"

    def test_fetch_price_empty_response(self):
        """Test handling empty API response."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        mock_response = Mock()
        mock_response.json.return_value = []

        with patch("requests.get", return_value=mock_response):
            with pytest.raises(ValidationError, match="Empty response"):
                fetcher.fetch_live_price("XAU")

    def test_fetch_price_no_elite_profile(self):
        """Test fallback when elite profile not available."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "ts": 1704067200000,
                "spreadProfilePrices": [
                    {"spreadProfile": "standard", "bid": 2000.00, "ask": 2015.00, "bidSpread": 0.75}
                ],
            }
        ]

        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_live_price("XAU")

        assert result is not None
        assert result["spread_profile"] == "standard"

    def test_fetch_price_request_timeout(self):
        """Test handling request timeout."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        with patch("requests.get", side_effect=requests.Timeout):
            with pytest.raises(NetworkError, match="Failed to fetch"):
                fetcher.fetch_live_price("XAU")

    def test_fetch_price_http_error(self):
        """Test handling HTTP errors."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError

        with patch("requests.get", return_value=mock_response):
            with pytest.raises(NetworkError, match="Failed to fetch"):
                fetcher.fetch_live_price("XAU")

    def test_fetch_price_invalid_json(self):
        """Test handling invalid JSON response."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        mock_response = Mock()
        mock_response.json.side_effect = ValueError

        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_live_price("XAU")

        assert result is None

    def test_fetch_price_calculations(self):
        """Test price conversion calculations."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "ts": 1704067200000,
                "spreadProfilePrices": [
                    {"spreadProfile": "elite", "bid": 1861.00, "ask": 1863.00, "bidSpread": 0.5}  # EUR per troy ounce
                ],
            }
        ]

        with patch("requests.get", return_value=mock_response):
            result = fetcher.fetch_live_price("XAU")

        # 1 troy ounce = 31.1035 grams
        # Mid price = (1861 + 1863) / 2 = 1862 EUR/oz
        # Per gram = 1862 / 31.1035 = ~59.86 EUR/g
        assert result is not None
        assert result["prices"]["eur_per_gram"]["mid"] > 50


class TestSavePrice:
    """Test saving price data to file."""

    def test_save_price_new_file(self, tmp_path, monkeypatch):
        """Test saving price to new file."""
        monkeypatch.chdir(tmp_path)
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        price_data = {
            "date": "2025-01-13",
            "metal": "XAU",
            "metal_name": "gold",
            "prices": {"eur_per_gram": {"mid": 120.0}},
        }

        result = fetcher.save_price(price_data, "XAU")

        assert result is True

        # Check file was created in correct path: data/live_prices/gold/2025-01-13.json
        price_file = tmp_path / "data" / "live_prices" / "gold" / "2025-01-13.json"
        assert price_file.exists()

        # Verify content
        with open(price_file, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["metal"] == "XAU"

    def test_save_price_append_to_existing(self, tmp_path, monkeypatch):
        """Test appending price to existing file."""
        monkeypatch.chdir(tmp_path)
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        # Create existing file in correct path
        live_price_dir = tmp_path / "data" / "live_prices" / "gold"
        live_price_dir.mkdir(parents=True)
        price_file = live_price_dir / "2025-01-13.json"
        price_file.write_text('[{"old": "data"}]')

        price_data = {
            "date": "2025-01-13",
            "metal": "XAU",
            "metal_name": "gold",
            "prices": {"eur_per_gram": {"mid": 120.0}},
        }

        result = fetcher.save_price(price_data, "XAU")

        assert result is True

        # Verify file was appended
        with open(price_file, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0]["old"] == "data"
        assert data[1]["metal"] == "XAU"

    def test_save_price_io_error(self, tmp_path, monkeypatch):
        """Test handling IO error when saving."""
        monkeypatch.chdir(tmp_path)
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        # Create a directory where the file should be (causes write error)
        live_price_dir = tmp_path / "data" / "live_prices" / "gold"
        live_price_dir.mkdir(parents=True)
        (live_price_dir / "2025-01-13.json").mkdir()  # Directory instead of file

        price_data = {"date": "2025-01-13", "metal": "XAU", "metal_name": "gold"}

        result = fetcher.save_price(price_data, "XAU")

        assert result is False


class TestGetLatestPrice:
    """Test getting latest price without saving."""

    def test_get_latest_price(self):
        """Test getting latest price."""
        fetcher = LivePriceFetcher(api_base_url="https://api.example.com")

        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "ts": 1704067200000,
                "spreadProfilePrices": [{"spreadProfile": "elite", "bid": 2000.00, "ask": 2010.00, "bidSpread": 0.5}],
            }
        ]

        with patch("requests.get", return_value=mock_response):
            result = fetcher.get_latest_price("XAU")

        assert result is not None
        assert result["metal"] == "XAU"
