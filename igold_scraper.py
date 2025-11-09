#!/usr/bin/env python3

"""
igold.bg comprehensive gold scraper (coins and bars)
Creates a CSV with all gold products found on igold.bg.

Captures both gold coins and gold bars with enhanced detection.

Outputs columns:
- product_name
- url
- total_weight_g
- purity_per_mille
- fine_gold_g
- price_bgn
- price_eur (if listed)
- price_per_g_fine_bgn
- price_per_g_fine_eur
- buy_price_bgn (if available)
- sell_price_bgn (if available)
- spread_percentage (calculated as ((sell_price_bgn - buy_price_bgn) / sell_price_bgn) * 100)

Results are sorted by price per gram (ascending - lowest to highest) (BGN). Items without price per gram are placed at the end.

If the --compare-tavex flag is used, additional columns are added:
- tavex_buy_price_bgn
- tavex_sell_price_bgn
- tavex_spread_percentage
- is_cheaper (YES if igold sell price is cheaper than tavex sell price, NO otherwise)
"""

import re
import csv
import time
import random
import logging
import json
import argparse
from urllib.parse import urljoin
import requests
from lxml import html
from tqdm import tqdm

# Import tavex scraper functionality
from tavex_scraper import scrape_tavex_gold_products

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger()

BASE = "https://igold.bg"

# Start with main category pages
START_PAGES = {
    "bar": [
        "/zlatni-kyulcheta-investitsionni",
        "/kyulcheta-s-numizmatichen-potenitzial",
        "/zlatni-numizmatichni-kyulcheta",
        "/zlatni-kyulcheta-za-podarak",
    ],
    "coin": [
        "/moderni-investitzionni-moneti",
        "/istoricheski-investitzionni-moneti",
        "/zlatni-moneti-s-numizmatichen-potentzial",
        "/moderni-zlatni-moneti-za-podarak",
        "/moderni-numizmatichni-moneti",
        "/istoricheski-numizmatichni-zlatni-moneti",
    ]
}

URLS_TO_SKIP = [
    '/nelikvidno-i-povredeno-zlato',
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

SCRAPE_DELAY_MIN = 1.0 # seconds
SCRAPE_DELAY_MAX = 2.5 # seconds

# Randomize wait time to appear more human-like
def random_delay():
    return random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX)

def extract_product_data(url: str, product_type: str) -> dict:
    """Extract product information from a product page using XPath"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return {}

    time.sleep(random_delay())
    tree = html.fromstring(r.content)

    title = tree.xpath('string(//main//h1)').strip()
    title = re.sub(r'\s+', ' ', title)

    # Sell prices (Продаваме)
    sell_price_bgn = float(tree.xpath('string(//regular-product//table/tbody/tr[1]/td[2]/span)').split()[0])
    sell_price_eur = float(tree.xpath('string(//regular-product//table/tbody/tr[2]/td[2]/span)').split()[0])

    # Buy prices (Купуваме)
    buy_price_bgn = float(tree.xpath('string(//regular-product//table/tbody/tr[4]/td[2]/span)').split()[0])
    buy_price_eur = float(tree.xpath('string(//regular-product//table/tbody/tr[5]/td[2]/span)').split()[0])

    # "Out of stock" notification breaks the xpath, using class selector instead
    details_container = tree.xpath('//div[contains(@class, "memberheader__meta") and contains(@class, "effect")]')

    # Extract all product details into a dictionary
    product_details_dict = {}
    if details_container:
        paragraphs = details_container[0].xpath('.//p')
        for p in paragraphs:
            text = p.text_content().strip()
            if text and ':' in text:
                # Split on first colon only
                key, value = text.split(':', 1)
                product_details_dict[key.strip()] = value.strip()

    weight = product_details_dict.get("Тегло", None)
    if weight is not None:
        weight = float(weight.split()[0])

    purity = product_details_dict.get("Проба", None)
    if purity is not None:
        purity = purity.split()[0]

    fine_gold = product_details_dict.get("Чисто злато", None)
    if fine_gold is not None:
        fine_gold = float(fine_gold.split()[0])

    if fine_gold is None and weight is not None and purity is not None:
        fine_gold = weight * (purity / 1000.0)

    # Calculate price per gram of fine gold
    price_per_g_bgn = None
    price_per_g_eur = None
    if fine_gold and fine_gold > 0:
        if sell_price_bgn and sell_price_bgn > 0:
            price_per_g_bgn = round(sell_price_bgn / fine_gold, 2)
        if sell_price_eur and sell_price_eur > 0:
            price_per_g_eur = round(sell_price_eur / fine_gold, 2)

    # Calculate spread percentage
    spread_percentage = None
    if buy_price_bgn and sell_price_bgn and sell_price_bgn > 0:
        spread = ((sell_price_bgn - buy_price_bgn) / sell_price_bgn) * 100
        spread_percentage = round(spread, 2)

    data = {
        'product_name': title.strip() if title else None,
        'url': url,
        'product_type': product_type,
        'total_weight_g': weight,
        'purity_per_mille': purity,
        'fine_gold_g': fine_gold,
        'sell_price_bgn': sell_price_bgn,
        'buy_price_bgn': buy_price_bgn,
        'sell_price_eur': sell_price_eur,
        'buy_price_eur': buy_price_eur,
        'price_per_g_fine_bgn': price_per_g_bgn,
        'price_per_g_fine_eur': price_per_g_eur,
        'spread_percentage': spread_percentage,
    }

    return data

def gather_product_links(url: str) -> list[str]:
    """Collect product links from category pages using XPath."""
    product_urls = set()
    logger.info(f"Scanning page: {url}")

    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        logger.warning(f"Failed to open page {url}: {r.status_code}")
        return []

    time.sleep(random_delay())

    tree = html.fromstring(r.content)

    product_hrefs = tree.xpath('//dd[@class="kv__member-name"]/a[1][@href and @href!="#"]/@href')

    new_products = {urljoin(BASE, href) for href in product_hrefs if href not in URLS_TO_SKIP}
    product_urls.update(new_products)

    logger.info(f"Found {len(new_products)} product links on {url}")

    # Log titles in debug mode
    if logger.level <= logging.DEBUG and new_products:
        product_links = tree.xpath('//dd[@class="kv__member-name"]/a[1][@href and @href!="#"]')
        for link in product_links:
            h2_text = link.xpath('string(.//h2)')
            if h2_text:
                logger.debug(f"  Found: {h2_text.strip()} -> {urljoin(BASE, link.get('href'))}")

    return sorted(product_urls)

def sort_key_function(item):
    """
    Sort function that prioritizes items with price_per_g_fine_bgn.
    Items without price per gram go to the end.
    """
    price_per_g = item.get('price_per_g_fine_bgn')
    if price_per_g is not None:
        return (0, price_per_g)  # (priority, price) - 0 = high priority
    else:
        return (1, 0)  # (priority, fallback) - 1 = low priority, items without price go to end

def convert_relative_url_to_absolute(url: str) -> str:
    """Convert a relative URL to an absolute URL."""
    return urljoin(BASE, url)

def find_tavex_equivalent(igold_product, tavex_products, equivalent_products):
    """
    Find the equivalent Tavex product for an igold product.

    Args:
        igold_product: Dictionary containing igold product data
        tavex_products: List of dictionaries containing Tavex product data
        equivalent_products: Dictionary mapping igold product names to Tavex product names

    Returns:
        Dictionary with tavex_buy_price_bgn, tavex_sell_price_bgn, tavex_spread_percentage, is_cheaper
        or None if no equivalent is found
    """
    igold_name = igold_product.get('product_name')
    if not igold_name:
        return None

    # Check if we have an equivalent in our mapping
    tavex_name = equivalent_products.get(igold_name)
    if not tavex_name:
        return None

    # Find the Tavex product with that name
    for tavex_product in tavex_products:
        if tavex_product.get('name') == tavex_name:
            # Get the Tavex data
            tavex_buy_price = tavex_product.get('buy_price')
            tavex_sell_price = tavex_product.get('sell_price')
            tavex_spread = tavex_product.get('spread_percentage')

            # Determine if igold is cheaper
            is_cheaper = "NO"
            igold_sell_price = igold_product.get('sell_price_bgn')
            if igold_sell_price and tavex_sell_price and igold_sell_price < tavex_sell_price:
                is_cheaper = "YES"

            return {
                'tavex_buy_price_bgn': tavex_buy_price,
                'tavex_sell_price_bgn': tavex_sell_price,
                'tavex_spread_percentage': tavex_spread,
                'is_cheaper': is_cheaper,
                'tavex_product_name': tavex_name
            }

    return None

def add_tavex_data_to_results(results, tavex_products, equivalent_products):
    """
    Add Tavex comparison data to the igold results.

    Args:
        results: List of dictionaries containing igold product data
        tavex_products: List of dictionaries containing Tavex product data
        equivalent_products: Dictionary mapping igold product names to Tavex product names

    Returns:
        Updated results list with Tavex data
    """
    logger.info(f"Adding Tavex comparison data to {len(results)} igold products...")

    # Track statistics
    matched_count = 0
    cheaper_count = 0

    for result in results:
        # Find Tavex equivalent
        tavex_data = find_tavex_equivalent(result, tavex_products, equivalent_products)

        if tavex_data:
            # Add Tavex data to the result
            result.update(tavex_data)
            matched_count += 1
            if tavex_data['is_cheaper'] == "YES":
                cheaper_count += 1
        else:
            # If no match, add None values
            result['tavex_buy_price_bgn'] = None
            result['tavex_sell_price_bgn'] = None
            result['tavex_spread_percentage'] = None
            result['is_cheaper'] = None
            result['tavex_product_name'] = None

    logger.info(f"Found Tavex equivalents for {matched_count} products")
    logger.info(f"igold is cheaper for {cheaper_count} products")

    return results

def main():
    # Setup command line arguments
    parser = argparse.ArgumentParser(description='igold.bg gold scraper')
    parser.add_argument('--compare-tavex', action='store_true', help='Compare with Tavex prices')
    parser.add_argument('--add-timestamp', action='store_true', help='Add timestamp to output filename (format: ddmmyyhhmm)')
    args = parser.parse_args()

    logger.info(f"Starting igold.bg gold scraper")
    logger.info(f"Scraping both gold coins and gold bars...")
    
    # If comparing with Tavex, load necessary data
    tavex_products = None
    equivalent_products = None

    if args.compare_tavex:
        logger.info("Comparing with Tavex prices is enabled")

        # Load equivalent products mapping
        try:
            with open('equivalent_products.json', 'r', encoding='utf-8') as f:
                equivalent_products = json.load(f)
            logger.info(f"Loaded {len(equivalent_products)} product mappings from equivalent_products.json")
        except Exception as e:
            logger.error(f"Failed to load equivalent_products.json: {e}")
            logger.info("Cannot continue with Tavex comparison without equivalent_products.json")
            return

        # Scrape Tavex products
        logger.info("Scraping Tavex products...")
        tavex_products = scrape_tavex_gold_products()
        logger.info(f"Scraped {len(tavex_products)} products from Tavex")

    # {"coin": {links: [...]}, "bar": {links: [...]}, ...}
    url_data = {}
    for product_type, rel_urls in START_PAGES.items():
        product_urls = []
        for rel_url in rel_urls:
            abs_url = convert_relative_url_to_absolute(rel_url)
            product_urls.extend(gather_product_links(abs_url))

        url_data[product_type] = {"links": product_urls}

    num_product_links = len([link for data in url_data.values() for link in data['links']])
    logger.info(f"Found {num_product_links} candidate product links.")

    if not url_data.values() or all(len(data['links']) == 0 for data in url_data.values()):
        logger.error("No product links found. The site structure might have changed.")
        return

    results = []
    failed_count = 0

    for product_type, data in url_data.items():
        logger.info(f"Starting to scan {len(data['links'])} links for {product_type} products...")

        for link in tqdm(data['links'], desc=f"Processing {product_type} products"):
            product_data = extract_product_data(link, product_type)
            if product_data and product_data.get('product_name'):
                results.append(product_data)

                # Log product name and key stats
                if product_data.get('fine_gold_g') and product_data.get('price_bgn'):
                    logger.debug(f"Extracted: {product_data['product_type']} - {product_data['product_name']} - "
                                 f"{product_data['fine_gold_g']}g @ {product_data['price_bgn']} BGN")
            else:
                failed_count += 1
                if failed_count <= 5:  # Show first few failures for debugging
                    logger.warning(f"Failed to extract data from: {link}")

    # If comparing with Tavex, add Tavex data to results
    if args.compare_tavex and tavex_products and equivalent_products:
        results = add_tavex_data_to_results(results, tavex_products, equivalent_products)

    # Sort results by price per gram (ascending - lowest to highest)
    # Items without price per gram will be placed at the end
    results.sort(key=sort_key_function)
    
    logger.info(f"\nSorting {len(results)} products by price per gram (BGN)...")

    # Define CSV fields based on whether we're comparing with Tavex
    if args.compare_tavex:
        keys = ['product_name','url','product_type','total_weight_g','purity_per_mille','fine_gold_g',
                'sell_price_bgn','buy_price_bgn', 'sell_price_eur','buy_price_eur','price_per_g_fine_bgn',
                'price_per_g_fine_eur', 'spread_percentage',
                'tavex_buy_price_bgn','tavex_sell_price_bgn','tavex_spread_percentage','is_cheaper','tavex_product_name']
        base_fname = 'igold_tavex_gold_products_sorted'
    else:
        keys = ['product_name','url','product_type','total_weight_g','purity_per_mille','fine_gold_g',
                'sell_price_bgn','buy_price_bgn', 'sell_price_eur','buy_price_eur','price_per_g_fine_bgn',
                'price_per_g_fine_eur', 'spread_percentage']
        base_fname = 'igold_gold_products_sorted'
        
    if args.add_timestamp:
        from datetime import datetime
        timestamp = datetime.now().strftime('%d%m%y%H%M')
        fname = f"{base_fname}_{timestamp}.csv"
    else:
        fname = f"{base_fname}.csv"

    # Write CSV
    with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=keys, delimiter=';')
        writer.writeheader()
        for r in results:
            writer.writerow(r)
    
    logger.info(f"Wrote {len(results)} rows to {fname}")
    logger.info(f"Failed to extract data from {failed_count} links")
 
    # Count products by type
    bars = [r for r in results if r.get('product_type') == 'bar']
    coins = [r for r in results if r.get('product_type') == 'coin']
    unknown = [r for r in results if r.get('product_type') == 'unknown']

    logger.info(f"Product breakdown: {len(bars)} bars, {len(coins)} coins, {len(unknown)} unknown")

    # Show summary of prices found
    with_prices = [r for r in results if r.get('price_bgn') or r.get('sell_price_bgn')]
    with_price_per_gram = [r for r in results if r.get('price_per_g_fine_bgn')]
 
    logger.info(f"Products with prices: {len(with_prices)}/{len(results)}")
    logger.info(f"Products with price per gram: {len(with_price_per_gram)}/{len(results)}")

    # If comparing with Tavex, show comparison statistics
    if args.compare_tavex:
        with_tavex_match = [r for r in results if r.get('tavex_sell_price_bgn') is not None]
        cheaper_than_tavex = [r for r in with_tavex_match if r.get('is_cheaper') == "YES"]

        logger.info(f"\n=== TAVEX COMPARISON SUMMARY ===")
        logger.info(f"Products with Tavex match: {len(with_tavex_match)}/{len(results)}")
        logger.info(f"Products cheaper at igold: {len(cheaper_than_tavex)}/{len(with_tavex_match)}")

        if cheaper_than_tavex:
            logger.info(f"\n=== TOP 10 BETTER DEALS AT IGOLD ===")
            # Sort by price difference percentage (biggest savings first)
            better_deals = []
            for item in cheaper_than_tavex:
                if item.get('sell_price_bgn') and item.get('tavex_sell_price_bgn'):
                    saving = (item['tavex_sell_price_bgn'] - item['sell_price_bgn']) / item['tavex_sell_price_bgn'] * 100
                    better_deals.append((item, saving))

            better_deals.sort(key=lambda x: x[1], reverse=True)

            for i, (item, saving) in enumerate(better_deals[:10]):
                name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
                logger.info(f"{i+1}. {name} ({item['product_type']})")
                logger.info(f"   igold price: {item['sell_price_bgn']} BGN")
                logger.info(f"   Tavex price: {item['tavex_sell_price_bgn']} BGN")
                logger.info(f"   Savings: {saving:.2f}%")
                logger.info("")

    # Show top 5 cheapest per gram and most expensive per gram
    if with_price_per_gram:
        logger.info(f"\n=== TOP 10 CHEAPEST PER GRAM (BGN) ===")
        for i, item in enumerate(with_price_per_gram[:10]):
            name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
            logger.info(f"{i+1}. {name} ({item['product_type']})")
            logger.info(f"   Price per gram: {item['price_per_g_fine_bgn']} BGN")
            logger.info(f"   Total price: {item['buy_price_bgn']} BGN")
            logger.info(f"   Fine gold: {item['fine_gold_g']} g")
            logger.info("")
        
        logger.info(f"=== TOP 3 MOST EXPENSIVE PER GRAM (BGN) ===")
        for i, item in enumerate(with_price_per_gram[-3:][::-1]):  # Last 5, reversed
            name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
            logger.info(f"{i+1}. {name} ({item['product_type']})")
            logger.info(f"   Price per gram: {item['price_per_g_fine_bgn']} BGN")
            logger.info(f"   Total price: {item['buy_price_bgn']} BGN")
            logger.info(f"   Fine gold: {item['fine_gold_g']} g")
            logger.info("")
        
        # Show separately for bars and coins
        if bars and len([b for b in bars if b.get('price_per_g_fine_bgn')]) >= 3:
            logger.info(f"\n=== TOP 10 CHEAPEST GOLD BARS PER GRAM (BGN) ===")
            bars_with_price = [b for b in bars if b.get('price_per_g_fine_bgn')]
            bars_with_price.sort(key=lambda x: x['price_per_g_fine_bgn'])
            for i, item in enumerate(bars_with_price[:10]):
                name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
                logger.info(f"{i+1}. {name}")
                logger.info(f"   Price per gram: {item['price_per_g_fine_bgn']} BGN")
                logger.info(f"   Total price: {item['buy_price_bgn']} BGN")
                logger.info(f"   Weight: {item['total_weight_g']} g")
                logger.info("")
                
        if coins and len([c for c in coins if c.get('price_per_g_fine_bgn')]) >= 3:
            logger.info(f"\n=== TOP 10 CHEAPEST GOLD COINS PER GRAM (BGN) ===")
            coins_with_price = [c for c in coins if c.get('price_per_g_fine_bgn')]
            coins_with_price.sort(key=lambda x: x['price_per_g_fine_bgn'])
            for i, item in enumerate(coins_with_price[:10]):
                name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
                logger.info(f"{i+1}. {name}")
                logger.info(f"   Price per gram: {item['price_per_g_fine_bgn']} BGN")
                logger.info(f"   Total price: {item['buy_price_bgn']} BGN")
                logger.info(f"   Weight: {item['total_weight_g']} g")
                logger.info("")

    # Show spread analysis
    with_spread = [r for r in results if r.get('spread_percentage') is not None]
    if with_spread:
        # Sort by spread for analysis
        spread_sorted = sorted(with_spread, key=lambda x: x['spread_percentage'])

        logger.info(f"\n=== TOP 5 PRODUCTS WITH LOWEST SPREAD ===")
        for i, item in enumerate(spread_sorted[:5]):
            name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
            logger.info(f"{i+1}. {name} ({item['product_type']})")
            logger.info(f"   Spread: {item['spread_percentage']}%")
            logger.info(f"   Buy price: {item['buy_price_bgn']} BGN")
            logger.info(f"   Sell price: {item['sell_price_bgn']} BGN")
            logger.info("")

        logger.info(f"\n=== TOP 5 PRODUCTS WITH HIGHEST SPREAD ===")
        for i, item in enumerate(spread_sorted[-5:][::-1]):  # Last 5, reversed
            name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
            logger.info(f"{i+1}. {name} ({item['product_type']})")
            logger.info(f"   Spread: {item['spread_percentage']}%")
            logger.info(f"   Buy price: {item['buy_price_bgn']} BGN")
            logger.info(f"   Sell price: {item['sell_price_bgn']} BGN")
            logger.info("")

        # If comparing with Tavex, show spread comparison
        if args.compare_tavex:
            with_both_spreads = [r for r in results if r.get('spread_percentage') is not None and r.get('tavex_spread_percentage') is not None]
            better_spread_than_tavex = [r for r in with_both_spreads if r['spread_percentage'] < r['tavex_spread_percentage']]

            logger.info(f"\n=== SPREAD COMPARISON WITH TAVEX ===")
            logger.info(f"Products with both spreads: {len(with_both_spreads)}")
            logger.info(f"Products with better spread at igold: {len(better_spread_than_tavex)}/{len(with_both_spreads)}")

            if better_spread_than_tavex:
                logger.info(f"\n=== TOP 5 BETTER SPREADS AT IGOLD ===")
                # Sort by spread difference (biggest difference first)
                better_spreads = []
                for item in better_spread_than_tavex:
                    spread_diff = item['tavex_spread_percentage'] - item['spread_percentage']
                    better_spreads.append((item, spread_diff))

                better_spreads.sort(key=lambda x: x[1], reverse=True)

                for i, (item, spread_diff) in enumerate(better_spreads[:5]):
                    name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
                    logger.info(f"{i+1}. {name} ({item['product_type']})")
                    logger.info(f"   igold spread: {item['spread_percentage']}%")
                    logger.info(f"   Tavex spread: {item['tavex_spread_percentage']}%")
                    logger.info(f"   Difference: {spread_diff:.2f}%")
                    logger.info("")

if __name__ == '__main__':
    main()