#!/usr/bin/env python3

"""
igold.bg comprehensive silver scraper (coins and bars)
Creates a CSV with all silver products found on igold.bg.

Captures both silver coins and silver bars with enhanced detection.

Outputs columns:
- product_name
- url
- total_weight_g
- purity_per_mille
- fine_silver_g
- price_bgn
- price_eur (if listed)
- price_per_g_fine_bgn
- price_per_g_fine_eur
- buy_price_bgn (if available)
- sell_price_bgn (if available)
- spread_percentage (calculated as ((sell_price_bgn - buy_price_bgn) / sell_price_bgn) * 100)

Results are sorted by price per gram (ascending - lowest to highest) (BGN). Items without price per gram are placed at the end.
"""

import re
import csv
import time
import random
import logging
import argparse
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger()

BASE = "https://igold.bg"

# Only use the main silver page - all silver products are there
START_PAGES = [
    "/srebro"
]

# Silver-specific product patterns
PRODUCT_PATTERNS = [
    # Silver bar patterns
    'srebarno', 'сребърно', 'silver', 'srebro', 'сребро',
    'srebarni-kyulcheta', 'сребърни кюлчeta', 'silver bar', 'silver ingot',
    
    # Silver coin patterns
    'srebarni-moneti', 'сребърни монети', 'silver coin', 'silver coins',
    'maple leaf', 'eagle', 'philharmonic', 'britannia', 'kangaroo', 'panda',
    'american eagle', 'canadian maple', 'vienna philharmonic',
    
    # General product indicators
    '/product/', 'монета', 'монети', 'кюлче', 'кюлчета'
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# Randomize wait time to appear more human-like
def random_delay():
    return random.uniform(1.0, 2.5)

def parse_float_bg(s: str):
    """Parse Bulgarian-formatted numbers like '6,45 гр.' or "5 838,00 лв." etc."""
    if not s:
        return None
    # remove non numeric but keep , and . and -
    s = s.strip()
    # replace non-breaking spaces and regular spaces
    s = s.replace('\xa0', '').replace(' ', '').replace('\u00A0', '')
    # Replace comma decimal with dot
    s = s.replace(',', '.')
    # Remove currency symbols and letters
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s) if s != '' else None
    except:
        return None

def safe_get(soup, selectors):
    """Safely get text from the first matching selector"""
    for sel in selectors:
        elements = soup.select(sel)
        for el in elements:
            if el and el.get_text(strip=True):
                return el.get_text(separator=' ', strip=True)
    return None

def detect_product_type(title, url, page_text):
    """Determine if the product is a silver bar or a silver coin"""
    # Default to unknown
    product_type = "unknown"
    
    # Check URL patterns
    if any(term in url.lower() for term in ["kyulche", "кюлче", "kulche", "bar", "ingot", "слитък"]):
        product_type = "bar"
    elif any(term in url.lower() for term in ["moneta", "монета", "coin"]):
        product_type = "coin"
    
    # Check title patterns
    if title:
        title_lower = title.lower()
        if any(term in title_lower for term in ["кюлче", "kulche", "bar", "слитък", "слитки", "ingot"]):
            product_type = "bar"
        elif any(term in title_lower for term in ["монета", "coin"]):
            product_type = "coin"
        # Check for specific silver coin names
        elif any(term in title_lower for term in ["maple", "eagle", "philharmonic", "britannia", "kangaroo", "panda"]):
            product_type = "coin"
    
    # Check page text if still unknown
    if product_type == "unknown" and page_text:
        page_lower = page_text.lower()
        bar_mentions = len(re.findall(r'кюлче|слитък|ingot|bar', page_lower))
        coin_mentions = len(re.findall(r'монета|coin', page_lower))
        
        if bar_mentions > coin_mentions:
            product_type = "bar"
        elif coin_mentions > bar_mentions:
            product_type = "coin"
    
    return product_type

def extract_product_data(url):
    """Extract product information from a product page"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None
    
    time.sleep(random_delay())
    soup = BeautifulSoup(r.content, 'lxml')

    # Product title/name - expanded selectors
    title = safe_get(soup, [
        'h1.entry-title', 
        'h1.product_title', 
        'div.product-title h1',
        'h1.product-name',
        'h1',
        'div.product-info h1',
        'div.title h1'
    ]) or (soup.title.string if soup.title else '')

    # Get all text content for parsing
    page_text = soup.get_text(separator='\n')
    
    # Detect if this is a bar or coin
    product_type = detect_product_type(title, url, page_text)
    
    # Initialize price variables
    price_bgn = None
    price_eur = None
    sell_price = None
    buy_price = None

    # APPROACH 1: Look for structured price elements with classes
    price_elements = soup.find_all(['div', 'span', 'p'], class_=re.compile(r'price|цена|cost|sum|amount', re.I))
    for elem in price_elements:
        text = elem.get_text(strip=True)
        if text:
            # Extract BGN prices
            bgn_match = re.search(r'([0-9\s\.,]+)\s*(лв\.?|BGN|лева)', text, re.IGNORECASE)
            if bgn_match and not price_bgn:
                price_bgn = parse_float_bg(bgn_match.group(1))
            
            # Extract EUR prices
            eur_match = re.search(r'([0-9\s\.,]+)\s*(€|EUR|евро)', text, re.IGNORECASE)
            if eur_match and not price_eur:
                price_eur = parse_float_bg(eur_match.group(1))

    # APPROACH 2: Look for any elements containing price indicators
    if not price_bgn:
        price_containers = soup.find_all(string=re.compile(r'цена|лева|лв', re.IGNORECASE))
        for container in price_containers:
            if container.parent:
                text = container.parent.get_text(strip=True)
                bgn_match = re.search(r'([0-9\s\.,]+)\s*(лв\.?|BGN|лева)', text, re.IGNORECASE)
                if bgn_match:
                    price_bgn = parse_float_bg(bgn_match.group(1))
                    break

    # APPROACH 3: Look for "Продаваме" and "Купуваме" in the text
    lines = page_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Look for sell prices (Продаваме)
        if 'Продаваме' in line or 'продаваме' in line or 'Цена' in line:
            bgn_match = re.search(r'([0-9\s\.,]+)\s*(лв\.?|BGN|лева)', line, re.IGNORECASE)
            if bgn_match:
                sell_price = parse_float_bg(bgn_match.group(1))
                if not price_bgn:  # Use as main price if no other price found
                    price_bgn = sell_price
        
        # Look for buy prices (Купуваме)
        if 'Купуваме' in line or 'купуваме' in line:
            bgn_match = re.search(r'([0-9\s\.,]+)\s*(лв\.?|BGN|лева)', line, re.IGNORECASE)
            if bgn_match:
                buy_price = parse_float_bg(bgn_match.group(1))

    # APPROACH 4: Look for price tables or structured data
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            row_text = row.get_text(separator=' ', strip=True)
            if 'Продаваме' in row_text or 'Цена' in row_text:
                bgn_match = re.search(r'([0-9\s\.,]+)\s*(лв\.?|BGN|лева)', row_text, re.IGNORECASE)
                if bgn_match and not sell_price:
                    sell_price = parse_float_bg(bgn_match.group(1))
                    if not price_bgn:
                        price_bgn = sell_price
            if 'Купуваме' in row_text:
                bgn_match = re.search(r'([0-9\s\.,]+)\s*(лв\.?|BGN|лева)', row_text, re.IGNORECASE)
                if bgn_match and not buy_price:
                    buy_price = parse_float_bg(bgn_match.group(1))

    # APPROACH 5: Fallback - look for any price-like patterns
    if not price_bgn and not sell_price:
        price_matches = re.findall(r'([0-9\s\.,]+)\s*(лв\.?|BGN|лева)', page_text, re.IGNORECASE)
        if price_matches:
            for match in price_matches:
                potential_price = parse_float_bg(match[0])
                if potential_price and potential_price > 5:  # Reasonable minimum price for silver
                    price_bgn = potential_price
                    break

    # Weight extraction with expanded patterns
    total_weight = None
    weight_patterns = [
        r'Тегло[:\s]*([0-9\s\.,]+)\s*(гр\.?|g|грама)',
        r'([0-9\.,]+)\s*(гр\.?|g|грама)\s*(?:тегло|общо|сребро)',
        r'Общо\s*тегло[:\s]*([0-9\s\.,]+)\s*(гр\.?|g|грама)',
        r'тежи\s*([0-9\s\.,]+)\s*(гр\.?|g|грама)',
        r'Тегло[:\s]*([0-9\s\.,]+)',
        r'Грамаж[:\s]*([0-9\s\.,]+)',
        r'тегло\s*([0-9\s\.,]+)\s*(?:гр\.?|g|грама)',
        r'weight[:\s]*([0-9\s\.,]+)\s*(?:g|gr|gram)'
    ]
    
    for pattern in weight_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            total_weight = parse_float_bg(match.group(1))
            break
    
    # Special handling for weight extraction from title
    if total_weight is None and title:
        # Try to extract from title
        title_weight_matches = [
            re.search(r'(\d[\d\s,\.]+)\s*(?:гр\.?|g|грама)', title, re.IGNORECASE),
            re.search(r'(\d[\d\s,\.]+)\s*(?:унц|унци|oz|ozt|унция)', title, re.IGNORECASE),
        ]
        
        for match in title_weight_matches:
            if match:
                weight_value = parse_float_bg(match.group(1))
                if weight_value:
                    # Check if it's in ounces
                    if any(term in match.group(0).lower() for term in ['унц', 'oz', 'ozt', 'унция']):
                        # Convert troy ounces to grams (1 troy oz = 31.1035g)
                        weight_value = weight_value * 31.1035
                    total_weight = weight_value
                    break
        
        # Standard weights for silver if weight is in the name/title
        if total_weight is None:
            title_lower = title.lower()
            if '1 унция' in title_lower or '1 oz' in title_lower or '31.1' in title_lower:
                total_weight = 31.1035  # 1 troy ounce
            elif '1 грам' in title_lower or '1g' in title_lower:
                total_weight = 1.0
            elif '5 грам' in title_lower or '5g' in title_lower:
                total_weight = 5.0
            elif '10 грам' in title_lower or '10g' in title_lower:
                total_weight = 10.0
            elif '15 грам' in title_lower or '15g' in title_lower:
                total_weight = 15.0
            elif '20 грам' in title_lower or '20g' in title_lower:
                total_weight = 20.0
            elif '50 грам' in title_lower or '50g' in title_lower:
                total_weight = 50.0
            elif '100 грам' in title_lower or '100g' in title_lower:
                total_weight = 100.0
            elif '250 грам' in title_lower or '250g' in title_lower:
                total_weight = 250.0
            elif '500 грам' in title_lower or '500g' in title_lower:
                total_weight = 500.0
            elif '1000 грам' in title_lower or '1 кг' in title_lower:
                total_weight = 1000.0
        
        # For coins with known weights
        if total_weight is None and product_type == "coin" and title:
            title_lower = title.lower()
            if 'maple' in title_lower or 'кленов лист' in title_lower:
                total_weight = 31.1035  # 1 oz
            elif 'eagle' in title_lower and ('american' in title_lower or 'американски' in title_lower):
                total_weight = 31.1035  # 1 oz
            elif 'philharmonic' in title_lower or 'филхармоник' in title_lower:
                total_weight = 31.1035  # 1 oz
            elif 'britannia' in title_lower or 'британия' in title_lower:
                total_weight = 31.1035  # 1 oz
            elif 'kangaroo' in title_lower or 'кенгуру' in title_lower:
                total_weight = 31.1035  # 1 oz
            elif 'panda' in title_lower or 'панда' in title_lower:
                total_weight = 30.0  # Chinese Silver Panda is 30g

    # Purity extraction with expanded patterns for silver
    purity = None
    purity_patterns = [
        r'Проба[:\s]*([0-9\.,]+)\s*/\s*1000',
        r'Проба[:\s]*([0-9]{3,4})[/\\]1000',
        r'([0-9]{3,4})\s*/\s*1000',
        r'Проба[:\s]*([0-9\.,]{3,6})(?!\s*/)',
        r'Чистота[:\s]*([0-9\.,]+)',
        r'финес[:\s]*([0-9\.,]+)',
        r'fineness[:\s]*([0-9\.,]+)',
        r'purity[:\s]*([0-9\.,]+)',
        r'999[.,]9',
        r'999[.,]0',
        r'925[.,]0',  # Sterling silver
        r'900[.,]0',
    ]
    
    for pattern in purity_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            # Special case for fixed purity values
            if pattern in ['999[.,]9', '999[.,]0', '925[.,]0', '900[.,]0']:
                purity_text = match.group(0).replace(',', '.')
                purity = float(purity_text)
            else:
                purity_val = parse_float_bg(match.group(1))
                if purity_val:
                    if purity_val >= 100:
                        purity = purity_val
                    elif purity_val < 1:
                        purity = purity_val * 1000
                    else:
                        purity = purity_val
            break
    
    # Default purity for silver products
    if purity is None:
        if product_type == "bar":
            purity = 999.9  # Most investment silver bars are .9999
        elif product_type == "coin":
            # Most modern investment silver coins are .999
            if title and any(coin in title.lower() for coin in ['maple', 'eagle', 'philharmonic', 'britannia', 'kangaroo']):
                purity = 999.0
            elif title and 'sterling' in title.lower():
                purity = 925.0  # Sterling silver
            else:
                purity = 999.0  # Default for investment silver coins

    # Fine silver calculation
    fine_silver = None
    fine_silver_match = re.search(r'Чисто\s*сребро[:\s]*([0-9\s\.,]+)\s*(гр\.?|g|грама)', page_text, re.IGNORECASE)
    if fine_silver_match:
        fine_silver = parse_float_bg(fine_silver_match.group(1))

    # Calculate fine silver if not explicitly stated
    if fine_silver is None and total_weight is not None and purity is not None:
        fine_silver = total_weight * (purity / 1000.0)

    data = {
        'product_name': title.strip() if title else None,
        'url': url,
        'product_type': product_type,
        'total_weight_g': total_weight,
        'purity_per_mille': purity,
        'fine_silver_g': fine_silver,
        'price_bgn': price_bgn,
        'price_eur': price_eur,
        'price_per_g_fine_bgn': None,
        'price_per_g_fine_eur': None,
        'buy_price_bgn': buy_price,
        'sell_price_bgn': sell_price,
        'spread_percentage': None,
    }

    # Compute price per gram
    if fine_silver and fine_silver > 0:
        if price_bgn:
            try:
                data['price_per_g_fine_bgn'] = round(price_bgn / fine_silver, 2)
            except:
                pass
        if price_eur:
            try:
                data['price_per_g_fine_eur'] = round(price_eur / fine_silver, 2)
            except:
                pass

    # Calculate spread percentage
    if buy_price and sell_price and sell_price > 0:
        try:
            spread = ((sell_price - buy_price) / sell_price) * 100
            data['spread_percentage'] = round(spread, 2)
        except:
            pass

    return data

def gather_product_links():
    """Extract all product links from the main silver page."""
    out = set()
    
    # Only scan the main silver page
    url = urljoin(BASE, "/srebro")
    logger.info("Scanning main silver page: %s", url)
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        logger.error("Failed to open main silver page %s: %s", url, e)
        return []
        
    time.sleep(random_delay())
    soup = BeautifulSoup(r.content, 'lxml')
    
    # Look for all links on the page
    all_links = soup.find_all('a', href=True)
    found_product_links = 0
    
    for a in all_links:
        href = a.get('href', '')
        if not href or href == '#' or 'javascript:' in href or 'mailto:' in href:
            continue
            
        # Make sure we have an absolute URL
        full_url = urljoin(BASE, href)
        
        # Skip external links
        if not full_url.startswith(BASE):
            continue
            
        # Skip obvious non-product URLs
        if any(pattern in href.lower() for pattern in ['/category/', '/tag/', '/author/', '/blog/', '/cart', '/checkout']):
            continue
            
        # Skip the main silver category page itself
        if href.endswith('/srebro') or href == '/srebro':
            continue
            
        # Check if this looks like a product URL
        # Look for product indicators in the URL or link text
        link_text = a.get_text(strip=True).lower()
        href_lower = href.lower()
        
        # Check for silver-related terms in URL or link text
        is_silver_product = (
            any(term in href_lower for term in ['srebro', 'сребро', 'silver', 'srebarni', 'сребърни']) or
            any(term in link_text for term in ['сребро', 'srebro', 'silver', 'сребърни', 'srebarni']) or
            '/product/' in href_lower or
            # Look for specific product patterns
            any(term in href_lower for term in ['moneta', 'монета', 'coin', 'kyulche', 'кюлче', 'bar', 'ingot'])
        )
        
        if is_silver_product:
            out.add(full_url)
            found_product_links += 1
    
    logger.info("Found %d potential silver product links", found_product_links)
    
    # Also look for product containers or grids specifically
    product_containers = soup.select('.products, .product-grid, .product-list, .items-grid, .woocommerce-products-grid, .shop-products, .product-container')
    for container in product_containers:
        links = container.select('a[href]')
        for a in links:
            href = a.get('href', '')
            if href:
                full_url = urljoin(BASE, href)
                if full_url.startswith(BASE) and not href.endswith('/srebro'):
                    out.add(full_url)
    
    # Look for specific product link patterns
    for selector in [
        'a[href*="srebarno"]',
        'a[href*="сребърно"]', 
        'a[href*="silver"]',
        'a[href*="srebro"]',
        'a[href*="сребро"]',
        'a[href*="srebarni"]',
        'a[href*="сребърни"]',
        'a[href*="/product"]',
        'a.woocommerce-LoopProduct-link',
        '.product a',
        '.product-item a',
        '.item a',
        'a[href*="moneta"]',
        'a[href*="монета"]'
    ]:
        for a in soup.select(selector):
            href = a.get('href', '')
            if href:
                full_url = urljoin(BASE, href)
                if full_url.startswith(BASE) and not href.endswith('/srebro'):
                    out.add(full_url)

    # Remove duplicates and filter
    filtered_urls = []
    for product_url in out:
        parsed = urlparse(product_url)
        path = parsed.path.lower()
        
        # Skip URLs that are definitely not products
        if any(segment in path for segment in ['/category/', '/tag/', '/author/', '/blog/']):
            continue
            
        # Skip the main silver page itself
        if path.endswith('/srebro') or path == '/srebro':
            continue
            
        filtered_urls.append(product_url)
    
    logger.info("Found %d unique silver product links from main page", len(filtered_urls))
    return sorted(filtered_urls)

def sort_key_function(item):
    """
    Sort function that prioritizes items with price_per_g_fine_bgn.
    Items without price per gram go to the end.
    """
    price_per_g = item.get('price_per_g_fine_bgn')
    if price_per_g is not None:
        return (0, price_per_g)  # (priority, price) - 0 = high priority
    else:
        return (1, 0)  # (priority, fallback) - 1 = low priority

def main():
    # Setup command line arguments
    parser = argparse.ArgumentParser(description='igold.bg silver scraper')
    parser.add_argument('--add-timestamp', action='store_true', help='Add timestamp to output filename (format: ddmmyyhhmm)')
    args = parser.parse_args()

    print("Starting igold.bg silver scraper")
    print("Scraping silver coins and silver bars from https://igold.bg/srebro...")
    
    links = gather_product_links()
    logger.info("Found %d candidate silver product links.", len(links))
    
    if not links:
        logger.error("No silver product links found. The site structure might have changed.")
        return
    
    results = []
    failed_count = 0
    
    for link in tqdm(links, desc="Scraping silver products"):
        data = extract_product_data(link)
        if data and data.get('product_name'):
            results.append(data)
            
            # Log product name and key stats
            if data.get('fine_silver_g') and data.get('price_bgn'):
                logger.debug("Extracted: %s - %s - %sg @ %s BGN",
                             data['product_type'],
                             data['product_name'],
                             data['fine_silver_g'],
                             data['price_bgn'])
        else:
            failed_count += 1
            if failed_count <= 5:  # Show first few failures for debugging
                logger.warning("Failed to extract data from: %s", link)

    # Sort results by price per gram (ascending - lowest to highest)
    results.sort(key=sort_key_function)
    
    logger.info("\nSorting %d silver products by price per gram (BGN)...", len(results))

    # Define CSV fields
    keys = ['product_name','url','product_type','total_weight_g','purity_per_mille','fine_silver_g',
            'price_bgn','price_eur','price_per_g_fine_bgn','price_per_g_fine_eur',
            'buy_price_bgn','sell_price_bgn','spread_percentage']
    base_fname = 'igold_silver_products_sorted'
        
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
    
    logger.info("Wrote %d silver products to %s", len(results), fname)
    logger.info("Failed to extract data from %d links", failed_count)
    
    # Count products by type
    bars = [r for r in results if r.get('product_type') == 'bar']
    coins = [r for r in results if r.get('product_type') == 'coin']
    unknown = [r for r in results if r.get('product_type') == 'unknown']
    
    logger.info("Silver product breakdown: %d bars, %d coins, %d unknown", len(bars), len(coins), len(unknown))
    
    # Show summary of prices found
    with_prices = [r for r in results if r.get('price_bgn') or r.get('sell_price_bgn')]
    with_price_per_gram = [r for r in results if r.get('price_per_g_fine_bgn')]
    
    logger.info("Products with prices: %d/%d", len(with_prices), len(results))
    logger.info("Products with price per gram: %d/%d", len(with_price_per_gram), len(results))

    # Show analysis if we have results
    if with_price_per_gram:
        logger.info("\n=== TOP 10 CHEAPEST SILVER PER GRAM (BGN) ===")
        for i, item in enumerate(with_price_per_gram[:10]):
            name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
            logger.info("%d. %s (%s)", i+1, name, item['product_type'])
            logger.info("   Price per gram: %s BGN", item['price_per_g_fine_bgn'])
            logger.info("   Total price: %s BGN", item['price_bgn'])
            logger.info("   Fine silver: %s g", item['fine_silver_g'])
            logger.info("")
        
        if len(with_price_per_gram) >= 3:
            logger.info("=== TOP 3 MOST EXPENSIVE SILVER PER GRAM (BGN) ===")
            for i, item in enumerate(with_price_per_gram[-3:][::-1]):
                name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
                logger.info("%d. %s (%s)", i+1, name, item['product_type'])
                logger.info("   Price per gram: %s BGN", item['price_per_g_fine_bgn'])
                logger.info("   Total price: %s BGN", item['price_bgn'])
                logger.info("   Fine silver: %s g", item['fine_silver_g'])
                logger.info("")

    # Show spread analysis if available
    with_spread = [r for r in results if r.get('spread_percentage') is not None]
    if with_spread:
        spread_sorted = sorted(with_spread, key=lambda x: x['spread_percentage'])
        
        logger.info("\n=== TOP 5 SILVER PRODUCTS WITH LOWEST SPREAD ===")
        for i, item in enumerate(spread_sorted[:5]):
            name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
            logger.info("%d. %s (%s)", i+1, name, item['product_type'])
            logger.info("   Spread: %s%%", item['spread_percentage'])
            logger.info("   Buy: %s BGN, Sell: %s BGN", item['buy_price_bgn'], item['sell_price_bgn'])
            logger.info("")

if __name__ == '__main__':
    main()
