[![Daily Precious Metals Scraper](https://github.com/peivanov/igold_scraper/actions/workflows/daily-scraper.yml/badge.svg)](https://github.com/peivanov/igold_scraper/actions/workflows/daily-scraper.yml)

# igold.bg Gold & Silver Scraper (Coins & Bars)

A comprehensive Python scraper for [igold.bg](https://igold.bg), extracting product details for **investment gold coins**, **gold bars**, **silver coins**, and **silver bars**.  
The script gathers product information, detects product type, and generates a **CSV report sorted by the lowest price per gram of fine gold/silver**.

**🤖 NEW: GitHub Actions Automation** - Automated daily scraping with price change tracking and Discord notifications!

---

## ✨ Features
- Scrapes **all major categories** of gold and silver bars and coins.
- Detects **product type** (bar / coin) via:
  - URL patterns
  - Title keywords
  - Page text analysis
- Extracts detailed product data:
  - Product name & URL  
  - Weight (g)  
  - Purity (per mille)  
  - Fine gold/silver weight (g)  
  - Prices in **BGN** and **EUR** (if available)  
  - Buy/Sell prices (if listed)  
  - Computed **price per gram of fine gold/silver**
  - **Spread percentage** - dealer markup calculated as `((sell_price - buy_price) / sell_price) × 100`
- Handles **multiple formats** of weight, purity, and price parsing.
- Exports results as `igold_gold_products_sorted.csv` or `igold_silver_products_sorted.csv`, sorted by **cheapest per gram**.
- Displays summaries:
  - Top cheapest / most expensive products
  - Breakdown by bars vs coins
- **NEW!** Compares prices with [tavex.bg](https://tavex.bg) to find the best deals
  - Use `--compare-tavex` flag to enable comparison (gold only)
  - Shows which products are cheaper at igold.bg
  - Adds columns for tavex prices and spread to the CSV
  - Uses a mapping in `equivalent_products.json` to match products

---

## 🤖 GitHub Actions Automation

### **Automated Daily Scraping & Price Tracking**
- **📅 Daily Schedule**: Automatically runs at 6:00 AM UTC (9:00 AM Bulgarian time)
- **📊 Price Change Detection**: Compares daily prices and identifies significant changes (>5% by default)
- **🔔 Discord Notifications**: Rich notifications for price changes, new products, and market trends
- **📈 Market Analysis**: Weekly and monthly statistical reports
- **🗂️ Data Management**: 6-month historical data retention with automatic cleanup

### **Discord Notifications Include:**
- **Price Alerts**: Products with significant price changes (configurable threshold)
- **New Products**: Newly detected items on igold.bg
- **Market Reports**: Weekly trend analysis and best deals
- **Error Notifications**: Alerts if scraping fails

### **Setup Automation:**
1. **Configure Discord Webhook**: 
   - Go to repository Settings → Secrets → Add `DISCORD_WEBHOOK_URL`
   - Optionally add `PRICE_CHANGE_THRESHOLD` (defaults to 5.0)

2. **GitHub Actions will automatically**:
   - Run scrapers daily
   - Store data in `data/` directory
   - Generate historical JSON files
   - Send Discord notifications for changes
   - Create weekly/monthly statistics

3. **Manual Trigger**: Go to Actions tab → "Daily Precious Metals Scraper" → "Run workflow"

---

## 📊 Spread Analysis

The scraper now calculates the **spread percentage** for each product, which represents the dealer's markup between buy and sell prices. This helps identify:

- **Investment efficiency**: Lower spreads mean better value for investors
- **Product categories**: Gold and silver bars typically have lower spreads than coins
- **Size premium**: Larger bars generally offer better spreads
- **Collectible premium**: Numismatic items have higher spreads due to collector value

### Spread Formula
```
Spread % = ((Sell Price - Buy Price) / Sell Price) × 100
```

### Typical Spread Ranges (to end of 2025)
- **Large investment bars** (50g+): 0.5% - 1.5%
- **1oz investment bars/coins**: 0.5% - 2%
- **Smaller bars/coins**: 1% - 5%
- **Collectible/numismatic items**: 5% - 30%

### Dealer Comparison
With the `--compare-tavex` flag, the scraper compares spreads between igold.bg and tavex.bg:
- Shows which dealer offers the lower spread for each product
- Calculates the spread difference
- Identifies overall which dealer has better pricing
- Helps find the best value for both buying and selling gold

---

## 🚀 Getting Started

### Manual Usage

```bash
# 1. Clone the repo
git clone https://github.com/peivanov/igold_scraper.git
cd igold_scraper

# 2. Set up a virtual environment (Recommended)
# On Ubuntu / Linux
sudo apt update
sudo apt install python3-venv -y

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

🔹 On Windows (PowerShell or CMD)
# Create virtual environment
python -m venv venv

# Activate (PowerShell)
venv\Scripts\Activate.ps1
# or: venv\Scripts\activate.bat

# If blocked by execution policy, use instead:
venv\Scripts\activate.bat

👉 If you see an error about execution policies in PowerShell, either run venv\Scripts\activate.bat (CMD-style) or temporarily allow scripts with:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

3. Install dependencies

Once your venv is active, run:

pip install -r requirements.txt

4. Run the scrapers

# Gold scraper
python igold_scraper.py

# Silver scraper
python igold_silver_scraper.py

# To enable Tavex price comparison (gold only):
python igold_scraper.py --compare-tavex

# To add timestamp to the output file:
python igold_scraper.py --add-timestamp
python igold_silver_scraper.py --add-timestamp

# To use both options (gold only):
python igold_scraper.py --compare-tavex --add-timestamp
```

The results will be saved in:

# Gold results
igold_gold_products_sorted.csv
# or when comparing with Tavex:
igold_tavex_gold_products_sorted.csv
# or with timestamp (format: ddmmyyhhmm):
igold_gold_products_sorted_170920252140.csv

# Silver results
igold_silver_products_sorted.csv
# or with timestamp:
igold_silver_products_sorted_170920252140.csv
```

### Automated Usage (GitHub Actions)

1. **Fork/Clone** this repository
2. **Add Discord webhook** to repository secrets (`DISCORD_WEBHOOK_URL`)
3. **GitHub Actions will automatically**:
   - Run daily at 6:00 AM UTC
   - Store data in `data/` directory
   - Send Discord notifications
   - Generate weekly/monthly reports

---
## 📋 Command-Line Arguments

The script supports the following command-line arguments:

| Argument | Description | Example |
|----------|-------------|---------|
| `--compare-tavex` | Enables comparison with Tavex prices. Adds columns for Tavex prices, spread, and indicates if the product is cheaper at igold.bg | `python igold_scraper.py --compare-tavex` |
| `--add-timestamp` | Adds a timestamp to the output file name in the format ddmmyyhhmm (day, month, year, hour, minute) | `python igold_scraper.py --add-timestamp` |

### Silver Scraper (`igold_silver_scraper.py`)

| Argument | Description | Example |
|----------|-------------|---------|
| `--add-timestamp` | Adds a timestamp to the output file name in the format ddmmyyhhmm (day, month, year, hour, minute) | `python igold_silver_scraper.py --add-timestamp` |

You can combine multiple arguments as needed:
```bash
python igold_scraper.py --compare-tavex --add-timestamp
```

# Silver with timestamp
python igold_silver_scraper.py --add-timestamp
```

---

## 📁 Data Structure (GitHub Actions)

When using GitHub Actions automation, data is organized as:

```
data/
├── gold/                    # Daily gold scraping results
│   ├── 2025-01-15.json     # Gold products for specific date
│   └── 2025-01-16.json
├── silver/                  # Daily silver scraping results
│   ├── 2025-01-15.json     # Silver products for specific date
│   └── 2025-01-16.json
└── statistics/              # Generated reports and analysis
    ├── gold_weekly_2025-01-15.json
    ├── silver_weekly_2025-01-15.json
    └── gold_monthly_2025-01-15.json
```

**Data Retention**: 6 months of historical data with automatic cleanup.

---

## 📈 Market Analysis Features

### **Daily Price Tracking**
- Compares current prices with previous day
- Identifies products with significant changes (>5% default)
- Tracks new products and discontinued items

### **Weekly/Monthly Reports**
- Market trend analysis (increasing/decreasing/stable)
- Price volatility calculations
- Best deals identification
- Product type breakdowns (bars vs coins)
- Average price per gram tracking

### **Discord Integration**
- Rich embed notifications with product links
- Real-time price change alerts
- Weekly market summaries
- Error notifications for failed runs

---

## ⚠️ Notes

The scraper introduces random delays between requests to avoid overloading the server.

The site structure may change, requiring regex/pattern updates.

## The scripts are for educational and personal use only.
## Please check igold.bg's and tavex.bg's Terms of Service before heavy use.

## 📜 License

This project is licensed under the MIT License – see the LICENSE file for details
