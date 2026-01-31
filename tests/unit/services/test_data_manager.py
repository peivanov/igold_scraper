"""Unit tests for data_manager service."""

import json
from datetime import datetime, timedelta

from igold_scraper.services.data_manager import csv_to_json, organize_daily_data, cleanup_old_data


class TestCsvToJson:
    """Test CSV to JSON conversion."""

    def test_csv_to_json_valid_file(self, tmp_path):
        """Test converting valid CSV file to JSON."""
        csv_file = tmp_path / "test.csv"
        csv_content = "product_name;price_eur;quantity\n" "Gold Bar;1000.50;5\n" "Silver Coin;25.99;10\n"
        csv_file.write_text(csv_content)

        result = csv_to_json(str(csv_file))

        assert result is not None
        assert len(result) == 2
        assert result[0]["product_name"] == "Gold Bar"
        assert result[0]["price_eur"] == 1000.50
        assert result[0]["quantity"] == 5
        assert result[1]["product_name"] == "Silver Coin"

    def test_csv_to_json_type_conversion(self, tmp_path):
        """Test that types are properly converted."""
        csv_file = tmp_path / "test.csv"
        csv_content = "product_name;price_eur;in_stock\n" "Item1;123.45;true\n" "Item2;67.89;false\n"
        csv_file.write_text(csv_content)

        result = csv_to_json(str(csv_file))

        assert result is not None
        # Check numeric conversion
        assert isinstance(result[0]["price_eur"], float)
        assert result[0]["price_eur"] == 123.45
        # Booleans stay as strings in CSV
        assert result[0]["in_stock"] == "true"
        assert result[1]["in_stock"] == "false"

    def test_csv_to_json_empty_file(self, tmp_path):
        """Test handling empty CSV file."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("name,price\n")

        result = csv_to_json(str(csv_file))

        assert result == []

    def test_csv_to_json_nonexistent_file(self):
        """Test handling nonexistent file."""
        result = csv_to_json("nonexistent.csv")

        assert result is None

    def test_csv_to_json_invalid_encoding(self, tmp_path):
        """Test handling file with encoding issues."""
        csv_file = tmp_path / "invalid.csv"
        # Write invalid UTF-8 bytes
        csv_file.write_bytes(b"name,price\n\xff\xfe")

        result = csv_to_json(str(csv_file))

        assert result is None


class TestOrganizeDailyData:
    """Test organizing daily data."""

    def test_organize_gold_files(self, tmp_path, monkeypatch):
        """Test organizing gold CSV files with actual file operations."""
        # Set up working directory
        monkeypatch.chdir(tmp_path)

        # Create data directories
        (tmp_path / "data" / "gold").mkdir(parents=True)
        (tmp_path / "data" / "silver").mkdir(parents=True)

        # Create a CSV file
        csv_file = tmp_path / "igold_gold_products_sorted_2025-01-13.csv"
        csv_content = "product_name;price_eur;weight\n" "Gold Bar;1000.50;31.1\n"
        csv_file.write_text(csv_content)

        organize_daily_data()

        # Verify CSV was processed and removed
        assert not csv_file.exists()

        # Verify JSON file was created
        today = datetime.now().strftime("%Y-%m-%d")
        json_file = tmp_path / "data" / "gold" / f"{today}.json"
        assert json_file.exists()

        # Verify JSON structure and content
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["date"] == today
        assert data["source"] == "igold.bg"
        assert data["product_type"] == "gold"
        assert len(data["products"]) == 1
        assert data["products"][0]["product_name"] == "Gold Bar"
        assert data["products"][0]["price_eur"] == 1000.50

    def test_organize_silver_files(self, tmp_path, monkeypatch):
        """Test organizing silver CSV files."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data" / "silver").mkdir(parents=True)

        csv_file = tmp_path / "igold_silver_products_sorted_2025-01-13.csv"
        csv_content = "product_name;price_eur\nSilver Coin;25.99\n"
        csv_file.write_text(csv_content)

        organize_daily_data()

        assert not csv_file.exists()
        today = datetime.now().strftime("%Y-%m-%d")
        json_file = tmp_path / "data" / "silver" / f"{today}.json"
        assert json_file.exists()

        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)
        assert data["product_type"] == "silver"

    def test_organize_no_files(self, tmp_path, monkeypatch):
        """Test when no CSV files exist."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data" / "gold").mkdir(parents=True)

        # Should not raise exception
        organize_daily_data()

        # No JSON files should be created
        today = datetime.now().strftime("%Y-%m-%d")
        json_file = tmp_path / "data" / "gold" / f"{today}.json"
        assert not json_file.exists()

    def test_organize_invalid_csv(self, tmp_path, monkeypatch):
        """Test handling invalid CSV data."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data" / "gold").mkdir(parents=True)

        # Create invalid CSV (will fail conversion)
        csv_file = tmp_path / "igold_gold_products_sorted_2025-01-13.csv"
        csv_file.write_bytes(b"invalid\xff\xfe")

        # Should not raise exception
        organize_daily_data()

        # CSV should still exist (not removed on failure)
        assert csv_file.exists()


class TestCleanupOldData:
    """Test cleaning up old data files."""

    def test_cleanup_removes_old_files(self, tmp_path, monkeypatch):
        """Test that old files are removed."""
        monkeypatch.chdir(tmp_path)

        # Create data directories
        gold_dir = tmp_path / "data" / "gold"
        silver_dir = tmp_path / "data" / "silver"
        gold_dir.mkdir(parents=True)
        silver_dir.mkdir(parents=True)

        # Create old (7 months ago) and recent files
        old_date = (datetime.now() - timedelta(days=210)).strftime("%Y-%m-%d")
        recent_date = datetime.now().strftime("%Y-%m-%d")

        old_gold_file = gold_dir / f"{old_date}.json"
        recent_gold_file = gold_dir / f"{recent_date}.json"
        old_silver_file = silver_dir / f"{old_date}.json"
        recent_silver_file = silver_dir / f"{recent_date}.json"

        # Write some data to files
        for file in [old_gold_file, recent_gold_file, old_silver_file, recent_silver_file]:
            file.write_text('{"test": "data"}')

        cleanup_old_data()

        # Old files should be removed
        assert not old_gold_file.exists()
        assert not old_silver_file.exists()

        # Recent files should remain
        assert recent_gold_file.exists()
        assert recent_silver_file.exists()

    def test_cleanup_no_directories(self, tmp_path, monkeypatch):
        """Test when data directories don't exist."""
        monkeypatch.chdir(tmp_path)

        # Should not raise exception
        cleanup_old_data()

    def test_cleanup_only_old_files(self, tmp_path, monkeypatch):
        """Test cleanup removes only files older than 6 months."""
        monkeypatch.chdir(tmp_path)

        gold_dir = tmp_path / "data" / "gold"
        gold_dir.mkdir(parents=True)

        # Create files at various ages
        very_old = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")  # 1 year
        old = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")  # 6.5 months
        borderline = (datetime.now() - timedelta(days=179)).strftime("%Y-%m-%d")  # Just under 6 months
        recent = datetime.now().strftime("%Y-%m-%d")

        very_old_file = gold_dir / f"{very_old}.json"
        old_file = gold_dir / f"{old}.json"
        borderline_file = gold_dir / f"{borderline}.json"
        recent_file = gold_dir / f"{recent}.json"

        for file in [very_old_file, old_file, borderline_file, recent_file]:
            file.write_text("{}")

        cleanup_old_data()

        # Files older than 6 months should be removed
        assert not very_old_file.exists()
        assert not old_file.exists()

        # Files within 6 months should remain
        assert borderline_file.exists()
        assert recent_file.exists()

    def test_cleanup_keeps_recent_files(self, tmp_path, monkeypatch):
        """Test that recent files are not removed."""
        monkeypatch.chdir(tmp_path)

        gold_dir = tmp_path / "data" / "gold"
        silver_dir = tmp_path / "data" / "silver"
        gold_dir.mkdir(parents=True)
        silver_dir.mkdir(parents=True)

        recent_date = datetime.now().strftime("%Y-%m-%d")
        gold_file = gold_dir / f"{recent_date}.json"
        silver_file = silver_dir / f"{recent_date}.json"

        gold_file.write_text("{}")
        silver_file.write_text("{}")

        cleanup_old_data()

        # Both files should still exist
        assert gold_file.exists()
        assert silver_file.exists()
