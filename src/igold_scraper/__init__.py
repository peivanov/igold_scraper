"""igold_scraper - Gold and silver price scraper."""

__version__ = "1.0.0"

from igold_scraper.config import Config
from igold_scraper.exceptions import (
    ScraperError,
    NetworkError,
    ParsingError,
    ValidationError,
    ConfigurationError,
    DatabaseError,
)

__all__ = [
    "Config",
    "ScraperError",
    "NetworkError",
    "ParsingError",
    "ValidationError",
    "ConfigurationError",
    "DatabaseError",
]
