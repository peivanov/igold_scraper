# igold.bg Gold Scraper (Coins & Bars)

A comprehensive Python scraper for [igold.bg](https://igold.bg), extracting product details for **investment gold coins** and **gold bars**.  
The script gathers product information, detects product type, and generates a **CSV report sorted by the lowest price per gram of fine gold**.

---

## ✨ Features
- Scrapes **all major categories** of gold bars and coins.
- Detects **product type** (bar / coin) via:
  - URL patterns
  - Title keywords
  - Page text analysis
- Extracts detailed product data:
  - Product name & URL  
  - Weight (g)  
  - Purity (per mille)  
  - Fine gold weight (g)  
  - Prices in **BGN** and **EUR** (if available)  
  - Buy/Sell prices (if listed)  
  - Computed **price per gram of fine gold**
  - **Spread percentage** - dealer markup calculated as `((sell_price - buy_price) / sell_price) × 100`
- Handles **multiple formats** of weight, purity, and price parsing.
- Exports results as `igold_gold_products_sorted.csv`, sorted by **cheapest per gram**.
- Displays summaries:
  - Top cheapest / most expensive products
  - Breakdown by bars vs coins
- **NEW!** Compares prices with [tavex.bg](https://tavex.bg) to find the best deals
  - Use `--compare-tavex` flag to enable comparison
  - Shows which products are cheaper at igold.bg
  - Adds columns for tavex prices and spread to the CSV
  - Uses a mapping in `equivalent_products.json` to match products

---

## 📊 Spread Analysis

The scraper now calculates the **spread percentage** for each product, which represents the dealer's markup between buy and sell prices. This helps identify:

- **Investment efficiency**: Lower spreads mean better value for investors
- **Product categories**: Gold bars typically have lower spreads than coins
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

```bash
### 1. Clone the repo
git clone https://github.com:peivanov/igold_scraper.git
cd igold_scraper

2. Set up a virtual environment (Recommended)
🔹 On Ubuntu / Linux
# Install venv if missing
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

# If blocked by execution policy, use instead:
venv\Scripts\activate.bat

👉 If you see an error about execution policies in PowerShell, either run venv\Scripts\activate.bat (CMD-style) or temporarily allow scripts with:

Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

3. Install dependencies

Once your venv is active, run:

pip install -r requirements.txt

4. Run the scraper
python igold_scraper.py

# To enable Tavex price comparison:
python igold_scraper.py --compare-tavex

# To add timestamp to the output file:
python igold_scraper.py --add-timestamp

# To use both options:
python igold_scraper.py --compare-tavex --add-timestamp


The results will be saved in:

igold_gold_products_sorted.csv
# or when comparing with Tavex:
igold_tavex_gold_products_sorted.csv
# or with timestamp (format: ddmmyyhhmm):
igold_gold_products_sorted_170920252140.csv
```

## 📋 Command-Line Arguments

The script supports the following command-line arguments:

| Argument | Description | Example |
|----------|-------------|---------|
| `--compare-tavex` | Enables comparison with Tavex prices. Adds columns for Tavex prices, spread, and indicates if the product is cheaper at igold.bg | `python igold_scraper.py --compare-tavex` |
| `--add-timestamp` | Adds a timestamp to the output file name in the format ddmmyyhhmm (day, month, year, hour, minute) | `python igold_scraper.py --add-timestamp` |

You can combine multiple arguments as needed:
```bash
python igold_scraper.py --compare-tavex --add-timestamp
```

## ⚠️ Notes

The scraper introduces random delays between requests to avoid overloading the server.

The site structure may change, requiring regex/pattern updates.

## The script is for educational and personal use only.
## Please check igold.bg’s and tavex.bg's Terms of Service before heavy use.

## 📜 License

This project is licensed under the MIT License – see the LICENSE file for details
