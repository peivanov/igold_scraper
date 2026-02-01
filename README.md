[![Daily Precious Metals Scraper](https://github.com/peivanov/igold_scraper/actions/workflows/daily-scraper.yml/badge.svg)](https://github.com/peivanov/igold_scraper/actions/workflows/daily-scraper.yml)

# igold.bg Gold & Silver Price Tracker

Automated scraper for [igold.bg](https://igold.bg) precious metals with live market price integration and Discord notifications.

## Features

### Scraping
- **Gold & Silver products** - Investment coins and bars from all major categories
- **Product detection** - Automatically identifies type (bar/coin) via URL patterns and keywords
- **Detailed extraction** - Weight, purity, fine metal content, prices (BGN/EUR), buy/sell prices
- **Price per gram** - Normalized pricing across different weights for easy comparison
- **Spread calculation** - Dealer markup: `((sell - buy) / sell) × 100`
- **Tavex comparison** - Optional price comparison with tavex.bg (gold only)

### Automation & Tracking
- **Daily automated scraping** - GitHub Actions runs at 6:00 AM UTC (9:00 AM Bulgarian time)
- **Live spot prices** - Real-time XAU/EUR and XAG/EUR market data
- **Price tracking** - Top 10 products by price per fine gram with change detection (>5% threshold)
- **Daily market reports** - Day-over-day analysis of top 10 products with trend detection
- **Weekly/monthly statistics** - Comprehensive market trend analysis and volatility tracking
- **Discord notifications** - Automated reports for price changes, daily summaries, and periodic statistics
- **Historical data** - 6-month retention with automatic cleanup

## Setup

1. **Clone repository**
```bash
git clone https://github.com/peivanov/igold_scraper.git
cd igold_scraper
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure GitHub Secrets** (for automation)
   - `DISCORD_WEBHOOK_URL` - Discord webhook for notifications
   - `PRECIOUS_METALS_API_BASE` - Live market data API base URL
   - `PRICE_CHANGE_THRESHOLD` - Optional, defaults to 5.0%

## Usage

### Manual scraping
```bash
# Gold products
python igold_scraper.py

# Silver products  
python igold_silver_scraper.py

# With Tavex comparison (gold only)
python igold_scraper.py --compare-tavex
```

### Automated workflow
GitHub Actions runs daily at 6:00 AM UTC (9:00 AM Bulgarian time):
- Scrapes gold and silver products
- Fetches live spot prices
- Tracks price changes (top 10 products)
- Generates weekly/monthly statistics
- Sends Discord notifications

### Data management
```bash
# Track price changes
python scripts/price_tracker.py

# Generate statistics
python scripts/statistics_generator.py
```

## Data Storage

All product data and price history is stored in a SQLite database (`data/products.db`):
- **products** table: Product metadata (name, weight, purity, etc.)
- **price_history** table: Historical buy/sell prices with timestamps

### Additional Files
```
data/
├── products.db                   # Main SQLite database
└── live_prices/
    ├── gold/                     # Live XAU/EUR spot prices
    │   └── 2025-10-25.json
    └── silver/                   # Live XAG/EUR spot prices
        └── 2025-10-25.json
```

**Data Retention**: All historical price data is retained in the database

## Key Metrics

- **Price per fine gram** - Normalized pricing across different weights
- **Spread percentage** - Dealer markup between buy/sell prices
- **Market volatility** - Standard deviation of daily average prices (top 10 products)
- **Premium over spot** - Dealer premium vs live market price
- **Price changes** - Day-over-day tracking of top 10 products

### Discord Notifications Include
- **Price alerts** - Products with significant changes (>5% default)
- **New in top 10** - Products entering the top 10 by price per gram
- **Live market prices** - Current XAU/EUR and XAG/EUR spot prices with BGN conversion
- **Weekly reports** - Market trend analysis and best deals
- **Error alerts** - Notifications if scraping fails

## Command-Line Arguments

### Gold Scraper (`igold_scraper.py`)
- `--compare-tavex` - Compare prices with tavex.bg (requires `equivalent_products.json`)
- `--add-timestamp` - Add timestamp to output filename (format: ddmmyyhhmm)

### Silver Scraper (`igold_silver_scraper.py`)
- `--add-timestamp` - Add timestamp to output filename (format: ddmmyyhhmm)

**Example:**
```bash
python igold_scraper.py --compare-tavex --add-timestamp
```

## Notes

- Random delays between requests to avoid server overload
- Site structure may change, requiring pattern updates
- For educational and personal use only
- Check igold.bg and tavex.bg Terms of Service before heavy use

## License

MIT License - See LICENSE file for details.
