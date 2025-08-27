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
- Handles **multiple formats** of weight, purity, and price parsing.
- Exports results as `igold_gold_products_sorted.csv`, sorted by **cheapest per gram**.
- Displays summaries:
  - Top cheapest / most expensive products
  - Breakdown by bars vs coins

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
python igold_bg_coins_and_bars_scraper.py


The results will be saved in:

igold_gold_products_sorted.csv
```

## ⚠️ Notes

The scraper introduces random delays between requests to avoid overloading the server.

The site structure may change, requiring regex/pattern updates.

## The script is for educational and personal use only.
## Please check igold.bg’s Terms of Service before heavy use.

## 📜 License

This project is licensed under the MIT License – see the LICENSE file for details