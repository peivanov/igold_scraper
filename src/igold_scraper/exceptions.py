"""Custom exception classes for igold_scraper."""


class ScraperError(Exception):
    """Base exception for all scraper-related errors."""


class NetworkError(ScraperError):
    """Raised when network-related errors occur (timeout, connection failed, etc.)."""


class ParsingError(ScraperError):
    """Raised when HTML parsing fails (XPath not found, invalid structure, etc.)."""


class ValidationError(ScraperError):
    """Raised when data validation fails (invalid format, missing fields, etc.)."""


class ConfigurationError(ScraperError):
    """Raised when configuration is invalid or missing required settings."""


class DatabaseError(ScraperError):
    """Raised when database operations fail."""
