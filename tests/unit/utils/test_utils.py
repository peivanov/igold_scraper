"""
Simple tests for scraper_utils module.
Run with: pytest tests/test_utils.py -v
"""

import pytest
from src.igold_scraper.utils.parsing import (
    safe_float,
    parse_float_bg,
    calculate_spread,
    calculate_price_per_gram,
    calculate_fine_metal,
    sort_key_function,
)


class TestSafeFloat:
    """Tests for safe_float function."""

    def test_valid_float(self):
        """Test converting valid float strings."""
        assert safe_float("5.99") == 5.99
        assert safe_float("1234.56") == 1234.56
        assert safe_float("0.1") == 0.1

    def test_bulgarian_format(self):
        """Test converting Bulgarian decimal separator (comma)."""
        assert safe_float("5,99") == 5.99
        assert safe_float("1234,56") == 1234.56

    def test_with_whitespace(self):
        """Test handling whitespace."""
        assert safe_float("  5.99  ") == 5.99
        assert safe_float("5,99 ") == 5.99

    def test_invalid_input(self):
        """Test handling invalid input."""
        assert safe_float("") is None
        assert safe_float("abc") is None
        assert safe_float(None) is None

    def test_with_default(self):
        """Test default value."""
        assert safe_float("invalid", default=0.0) == 0.0
        assert safe_float(None, default=10.0) == 10.0


class TestParseBulgarianFloat:
    """Tests for parse_float_bg function."""

    def test_with_units(self):
        """Test parsing with units."""
        assert parse_float_bg("6,45 гр.") == 6.45
        assert parse_float_bg("5,99 лв.") == 5.99

    def test_with_thousands_separator(self):
        """Test parsing with space as thousands separator."""
        assert parse_float_bg("5 838,00 лв.") == 5838.0
        assert parse_float_bg("1 234,56") == 1234.56

    def test_simple_numbers(self):
        """Test simple number parsing."""
        assert parse_float_bg("1,23") == 1.23
        assert parse_float_bg("100") == 100.0

    def test_invalid(self):
        """Test invalid input."""
        assert parse_float_bg("") is None
        assert parse_float_bg("abc") is None


class TestCalculateSpread:
    """Tests for calculate_spread function."""

    def test_normal_spread(self):
        """Test normal spread calculation."""
        # spread = ((110 - 100) / 110) * 100 = 9.09%
        result = calculate_spread(100, 110)
        assert result == pytest.approx(9.09, abs=0.01)

    def test_zero_spread(self):
        """Test zero spread."""
        assert calculate_spread(100, 100) == 0.0

    def test_invalid_inputs(self):
        """Test invalid inputs."""
        assert calculate_spread(0, 0) is None
        assert calculate_spread(None, 100) is None
        assert calculate_spread(100, None) is None
        assert calculate_spread(-10, 100) is None


class TestCalculatePricePerGram:
    """Tests for calculate_price_per_gram function."""

    def test_valid_calculation(self):
        """Test valid price per gram calculation."""
        assert calculate_price_per_gram(100, 5) == 20.0
        assert calculate_price_per_gram(50, 10) == 5.0
        assert calculate_price_per_gram(952, 31.1035) == pytest.approx(30.61, abs=0.01)

    def test_invalid_inputs(self):
        """Test invalid inputs."""
        assert calculate_price_per_gram(100, 0) is None
        assert calculate_price_per_gram(None, 5) is None
        assert calculate_price_per_gram(100, None) is None
        assert calculate_price_per_gram(0, 5) is None


class TestCalculateFineMetal:
    """Tests for calculate_fine_metal function."""

    def test_valid_calculation(self):
        """Test valid fine metal calculation."""
        # 10g at 900 per mille = 9g fine
        assert calculate_fine_metal(10, 900) == 9.0
        # 100g at 1000 per mille = 100g fine
        assert calculate_fine_metal(100, 1000) == 100.0

    def test_invalid_inputs(self):
        """Test invalid inputs."""
        assert calculate_fine_metal(10, 0) is None
        assert calculate_fine_metal(0, 900) is None
        assert calculate_fine_metal(None, 900) is None
        assert calculate_fine_metal(10, None) is None


class TestSortKeyFunction:
    """Tests for sort_key_function."""

    def test_with_price(self):
        """Test sorting items with price per gram."""
        item = {'price_per_g_fine_eur': 48.35}
        result = sort_key_function(item)
        assert result == (0, 48.35)

    def test_without_price(self):
        """Test sorting items without price per gram."""
        item = {'price_per_g_fine_eur': None}
        result = sort_key_function(item)
        assert result == (1, 0)

    def test_sort_order(self):
        """Test that items with price come before items without."""
        item_with_price = {'price_per_g_fine_eur': 48.35}
        item_without_price = {'price_per_g_fine_eur': None}
        item_with_higher_price = {'price_per_g_fine_eur': 50.0}

        items = [item_without_price, item_with_higher_price, item_with_price]
        sorted_items = sorted(items, key=sort_key_function)

        # Items with price come first, sorted by price ascending
        assert sorted_items[0] == item_with_price
        assert sorted_items[1] == item_with_higher_price
        assert sorted_items[2] == item_without_price


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
