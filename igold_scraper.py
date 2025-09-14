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
"""

import re
import csv
import time
import random
import logging
import sys
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

# Start with main category pages
START_PAGES = [
    # Main categories for gold bars
    "/zlatni-kyulcheta-investitsionni",
    "/kyulcheta-s-numizmatichen-potenitzial",
    "/zlatni-numizmatichni-kyulcheta",
    "/zlatni-kyulcheta-za-podarak",
    
    # Main categories for gold coins
    "/moderni-investitzionni-moneti",
    "/istoricheski-investitzionni-moneti",
    "/zlatni-moneti-s-numizmatichen-potentzial",
    "/moderni-zlatni-moneti-za-podarak",
    "/moderni-numizmatichni-moneti",
    "/istoricheski-numizmatichni-zlatni-moneti",
]

# Extended patterns to match more product types
PRODUCT_PATTERNS = [
    # Bar patterns
    'kyulche', 'кюлче', 'kulche', 'bar', 'ingot', 'слитък', 'слитки', 'златно кюлче',
    'heraeus', 'metalor', 'umicore', 'perth mint', 'argor', 'pamp', 'perth', 'valcambi', 
    
    # Coin patterns
    'zlatna-moneta', 'zlatni-', '/product/', 'монета', 'монети', 'coin', 'coins',
    'kurusha', 'napoleon', 'sovereign', 'dukat', 'дукат', 'maple', 'krugerrand', 'philharmonic', 
    'britannia', 'eagle', 'panda', 'kangaroo', 'австрийски', 'американски', 'британски',
    'libertad', 'либертад', 'lunar', 'buffalo', 'буфало'
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
    """Determine if the product is a gold bar or a gold coin"""
    # Default to unknown
    product_type = "unknown"
    
    # Check URL patterns
    if any(term in url.lower() for term in ["kyulche", "кюлче", "kulche", "bar", "ingot", "слитък"]):
        product_type = "bar"
    elif any(term in url.lower() for term in ["moneta", "монета", "coin", "dukat", "дукат"]):
        product_type = "coin"
    
    # Check title patterns
    if title:
        if any(term in title.lower() for term in ["кюлче", "kulche", "bar", "слитък", "слитки", "ingot"]):
            product_type = "bar"
        elif any(term in title.lower() for term in ["монета", "coin", "дукат", "dukat"]):
            product_type = "coin"
    
    # Check page text
    if product_type == "unknown" and page_text:
        bar_mentions = len(re.findall(r'кюлче|слитък|ingot|bar', page_text, re.IGNORECASE))
        coin_mentions = len(re.findall(r'монета|coin|дукат|dukat', page_text, re.IGNORECASE))
        
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
        logger.warning(f"Failed to fetch {url}: {e}")
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
            # Try to extract price from the same line or nearby lines
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
                    if not price_bgn:  # Use as main price if no other price found
                        price_bgn = sell_price
            if 'Купуваме' in row_text:
                bgn_match = re.search(r'([0-9\s\.,]+)\s*(лв\.?|BGN|лева)', row_text, re.IGNORECASE)
                if bgn_match and not buy_price:
                    buy_price = parse_float_bg(bgn_match.group(1))

    # APPROACH 5: Fallback - look for any price-like patterns
    if not price_bgn and not sell_price:
        # Look for standalone prices in the format "5 838,00 лв."
        price_matches = re.findall(r'([0-9\s\.,]+)\s*(лв\.?|BGN|лева)', page_text, re.IGNORECASE)
        if price_matches:
            # Take the first reasonable price (not too small, likely not weight)
            for match in price_matches:
                potential_price = parse_float_bg(match[0])
                if potential_price and potential_price > 10:  # Reasonable minimum price
                    price_bgn = potential_price
                    break

    # Weight extraction with expanded patterns
    total_weight = None
    weight_patterns = [
        r'Тегло[:\s]*([0-9\s\.,]+)\s*(гр\.?|g|грама)',
        r'([0-9\.,]+)\s*(гр\.?|g|грама)\s*(?:тегло|общо|злато)',
        r'Общо\s*тегло[:\s]*([0-9\s\.,]+)\s*(гр\.?|g|грама)',
        r'тежи\s*([0-9\s\.,]+)\s*(гр\.?|g|грама)',
        r'Тегло[:\s]*([0-9\s\.,]+)',
        r'Грамаж[:\s]*([0-9\s\.,]+)',
        r'Грамаж:\s*([0-9\s\.,]+)',
        r'тегло\s*([0-9\s\.,]+)\s*(?:гр\.?|g|грама)',
        r'weight[:\s]*([0-9\s\.,]+)\s*(?:g|gr|gram)'
    ]
    
    for pattern in weight_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            total_weight = parse_float_bg(match.group(1))
            break
    
    # Special handling for weight extraction
    if total_weight is None:
        # Try to extract from title
        title_weight_matches = [
            re.search(r'(\d[\d\s,\.]+)\s*(?:гр\.?|g|грама)', title, re.IGNORECASE),
            re.search(r'(\d[\d\s,\.]+)\s*(?:унц|унци|oz|ozt|унция)', title, re.IGNORECASE),
            re.search(r'(\d[\d\s,\.]+)\s*(?:g|gr|gram)', title, re.IGNORECASE)
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
        
        # Standard weights for gold bars if weight is in the name/title
        if total_weight is None and title:
            # Look for standard bar weights in the title
            if '1 грам' in title.lower() or '1g' in title.lower() or '1 g' in title.lower():
                total_weight = 1.0
            elif '2.5 грам' in title.lower() or '2.5g' in title.lower() or '2.5 g' in title.lower():
                total_weight = 2.5
            elif '5 грам' in title.lower() or '5g' in title.lower() or '5 g' in title.lower():
                total_weight = 5.0
            elif '10 грам' in title.lower() or '10g' in title.lower() or '10 g' in title.lower():
                total_weight = 10.0
            elif '20 грам' in title.lower() or '20g' in title.lower() or '20 g' in title.lower():
                total_weight = 20.0
            elif '31.1 грам' in title.lower() or '31.1g' in title.lower() or '1 oz' in title.lower():
                total_weight = 31.1035  # 1 troy ounce
            elif '50 грам' in title.lower() or '50g' in title.lower() or '50 g' in title.lower():
                total_weight = 50.0
            elif '100 грам' in title.lower() or '100g' in title.lower() or '100 g' in title.lower():
                total_weight = 100.0
            elif '250 грам' in title.lower() or '250g' in title.lower() or '250 g' in title.lower():
                total_weight = 250.0
            elif '500 грам' in title.lower() or '500g' in title.lower() or '500 g' in title.lower():
                total_weight = 500.0
            elif '1000 грам' in title.lower() or '1 кг' in title.lower() or '1kg' in title.lower():
                total_weight = 1000.0
        
        # For coins with known weights
        if total_weight is None and product_type == "coin":
            if 'дукат' in title.lower() or 'dukat' in title.lower():
                # Austrian Dukat is 3.49g
                if '1 дукат' in title.lower() or '1 dukat' in title.lower() or 'един дукат' in title.lower():
                    total_weight = 3.49
                elif '4 дукат' in title.lower() or '4 dukat' in title.lower() or 'четири дукат' in title.lower():
                    total_weight = 13.96  # 4 * 3.49
                
            if 'sovereign' in title.lower() or 'соверен' in title.lower():
                # Sovereign is 7.99g or 7.988g
                if 'half' not in title.lower() and 'половин' not in title.lower():
                    total_weight = 7.99
                else:
                    total_weight = 3.99  # Half sovereign
            
            if 'napoleon' in title.lower() or 'наполеон' in title.lower():
                # Napoleon is 5.81g
                total_weight = 5.81

    # Purity extraction with expanded patterns
    purity = None
    purity_patterns = [
        r'Проба[:\s]*([0-9\.,]+)\s*/\s*1000',
        r'Проба[:\s]*([0-9]{3,4})[/\\]1000',
        r'([0-9]{3,4})\s*/\s*1000',
        r'Проба[:\s]*([0-9\.,]{3,6})(?!\s*/)',
        r'Чистота[:\s]*([0-9\.,]+)',
        r'(\d+)\s*карата',
        r'(\d+)K\s*злато',
        r'финес[:\s]*([0-9\.,]+)',
        r'fineness[:\s]*([0-9\.,]+)',
        r'purity[:\s]*([0-9\.,]+)',
        r'999[.,]9', # Match common "999.9" references
        r'999[.,]0',
        r'995[.,]0',
        r'916[.,]7',
        r'900[.,]0',
    ]
    
    for pattern in purity_patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            # Special case for fixed purity values
            if pattern in ['999[.,]9', '999[.,]0', '995[.,]0', '916[.,]7', '900[.,]0']:
                purity_text = match.group(0).replace(',', '.')
                purity = float(purity_text)
            else:
                purity_val = parse_float_bg(match.group(1))
                if purity_val:
                    # Convert carats to per mille if needed
                    if 'карата' in pattern or 'K' in pattern:
                        purity = (purity_val / 24) * 1000
                    # If it's a 3-4 digit number, it's likely per mille
                    elif purity_val >= 100:
                        purity = purity_val
                    # If it's a decimal less than 1, convert to per mille
                    elif purity_val < 1:
                        purity = purity_val * 1000
                    else:
                        purity = purity_val
            break
    
    # For bars, default to 999.9 if not specified (most investment bars are 999.9)
    if purity is None and product_type == "bar":
        # Check if it's explicitly mentioned as investment gold
        if 'инвестиционно' in title.lower() or 'investment' in title.lower():
            purity = 999.9
    
    # For specific coins, set known purity if not found
    if purity is None and product_type == "coin":
        # Check for known coin types with standard purities
        if 'дукат' in title.lower() or 'dukat' in title.lower():
            # Austrian Dukat is 986 fine gold
            purity = 986
        elif 'sovereign' in title.lower() or 'соверен' in title.lower():
            # Sovereign is 916.7 fine gold (22 carat)
            purity = 916.7
        elif 'napoleon' in title.lower() or 'наполеон' in title.lower():
            # Napoleon is 900 fine gold
            purity = 900
        elif 'maple' in title.lower() or 'кленов лист' in title.lower():
            # Canadian Maple Leaf is 999.9 fine gold
            purity = 999.9
        elif 'krugerrand' in title.lower() or 'крюгерранд' in title.lower():
            # Krugerrand is 916.7 fine gold (22 carat)
            purity = 916.7
        elif 'philharmonic' in title.lower() or 'филхармоник' in title.lower():
            # Vienna Philharmonic is 999.9 fine gold
            purity = 999.9
        elif 'eagle' in title.lower() or 'игъл' in title.lower():
            # American Eagle is 916.7 fine gold (22 carat)
            purity = 916.7
        elif 'britannia' in title.lower() or 'британия' in title.lower():
            # Britannia (modern) is 999.9 fine gold
            purity = 999.9
        elif 'panda' in title.lower() or 'панда' in title.lower():
            # Chinese Panda is 999 fine gold
            purity = 999
        elif 'kangaroo' in title.lower() or 'кенгуру' in title.lower():
            # Australian Kangaroo is 999.9 fine gold
            purity = 999.9
        # Default for investment gold if nothing else matches
        elif 'инвестиционно' in title.lower() or 'investment' in title.lower():
            purity = 999.9

    # Fine gold extraction
    fine_gold = None
    fine_gold_match = re.search(r'Чисто\s*злато[:\s]*([0-9\s\.,]+)\s*(гр\.?|g|грама)', page_text, re.IGNORECASE)
    if fine_gold_match:
        fine_gold = parse_float_bg(fine_gold_match.group(1))

    # Calculate fine gold if not explicitly stated
    if fine_gold is None and total_weight is not None and purity is not None:
        fine_gold = total_weight * (purity / 1000.0)

    data = {
        'product_name': title.strip() if title else None,
        'url': url,
        'product_type': product_type,
        'total_weight_g': total_weight,
        'purity_per_mille': purity,
        'fine_gold_g': fine_gold,
        'price_bgn': price_bgn,
        'price_eur': price_eur,
        'price_per_g_fine_bgn': None,
        'price_per_g_fine_eur': None,
        'buy_price_bgn': buy_price,
        'sell_price_bgn': sell_price,
        'spread_percentage': None,
    }

    # Compute price per gram
    if fine_gold and fine_gold > 0:
        if price_bgn:
            try:
                data['price_per_g_fine_bgn'] = round(price_bgn / fine_gold, 2)
            except:
                pass
        if price_eur:
            try:
                data['price_per_g_fine_eur'] = round(price_eur / fine_gold, 2)
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

def is_product_url(url, href):
    """Check if a URL appears to be a product URL based on patterns"""
    # Skip URLs that are definitely not products
    if any(pattern in href.lower() for pattern in ['/category/', '/tag/', '/author/', '/blog/']):
        return False
        
    # Skip external links
    if not href.startswith(BASE) and not href.startswith('/'):
        if not any(BASE in href for href in [href, urljoin(BASE, href)]):
            return False
            
    # Skip category links
    if any(path in href for path in START_PAGES):
        return False
        
    # Check if URL contains any product patterns
    return any(pattern in href.lower() for pattern in PRODUCT_PATTERNS)

def gather_product_links():
    """Walk category pages and collect product links."""
    out = set()
    visited_pages = set()
    pages_to_visit = [urljoin(BASE, path) for path in START_PAGES]
    
    logger.info(f"Starting to scan {len(pages_to_visit)} category pages...")
    
    while pages_to_visit:
        url = pages_to_visit.pop(0)
        
        # Skip if already visited
        if url in visited_pages:
            continue
            
        visited_pages.add(url)
        
        logger.info(f"Scanning page: {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to open page {url}: {e}")
            continue
            
        time.sleep(random_delay())
        soup = BeautifulSoup(r.content, 'lxml')
        
        # Look for all links
        found_product_links = 0
        all_links = soup.find_all('a', href=True)
        
        for a in all_links:
            href = a.get('href', '')
            if not href or href == '#' or 'javascript:' in href or 'mailto:' in href:
                continue
                
            # Make sure we have an absolute URL
            full_url = urljoin(BASE, href)
            
            # Check if this looks like a product page
            if is_product_url(url, full_url):
                out.add(full_url)
                found_product_links += 1
                
            # Check if this is a pagination link we should follow
            is_pagination = ('page/' in href or 'paged=' in href) and BASE in full_url
            
            if is_pagination and full_url not in visited_pages and full_url not in pages_to_visit:
                pages_to_visit.append(full_url)
        
        logger.info(f"Found {found_product_links} product links on {url}")
        
        # Look specifically for product containers or grids
        product_containers = soup.select('.products, .product-grid, .product-list, .items-grid, .woocommerce-products-grid')
        for container in product_containers:
            links = container.select('a[href]')
            for a in links:
                href = a.get('href', '')
                if href and '/cdn-cgi/' not in href:
                    full_url = urljoin(BASE, href)
                    out.add(full_url)
        
        # Get specific product links using selectors that might work on this site
        for selector in [
            # Gold bar selectors
            'a[href*="kyulche"]',
            'a[href*="кюлче"]',
            'a[href*="kulche"]',
            'a[href*="bar"]',
            'a[href*="ingot"]',
            'a[href*="слитък"]',
            # Gold coin selectors
            'a[href*="zlatna-moneta"]',
            'a[href*="zlatni-"]',
            'a[href*="/product"]',
            'a.woocommerce-LoopProduct-link',
            'a[href*="dukat"]',
            'a[href*="дукат"]',
            'a[href*="kurusha"]',
            'a[href*="sovereign"]',
            'a[href*="napoleon"]',
            '.product a',
            '.product-item a',
            '.item a'
        ]:
            for a in soup.select(selector):
                href = a.get('href', '')
                if href:
                    full_url = urljoin(BASE, href)
                    out.add(full_url)

    # Remove non-product URLs (categories, tags, etc.)
    filtered_urls = []
    for url in out:
        # Parse the URL
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Skip URLs that are definitely not products
        if any(segment in path for segment in ['/category/', '/tag/', '/author/', '/blog/']):
            continue
            
        # Skip category links
        if any(path.endswith(p) for p in START_PAGES):
            continue
            
        filtered_urls.append(url)
    
    logger.info(f"Found {len(filtered_urls)} unique product links across {len(visited_pages)} pages")
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
        return (1, 0)  # (priority, fallback) - 1 = low priority, items without price go to end

def main():
    print(f"Starting igold.bg gold scraper by {sys.argv[0]}")
    print(f"Scraping both gold coins and gold bars...")
    
    links = gather_product_links()
    logger.info(f"Found {len(links)} candidate product links.")
    
    if not links:
        logger.error("No product links found. The site structure might have changed.")
        return
    
    # Show first few links for debugging
    logger.info("First 5 links found:")
    for i, link in enumerate(links[:5]):
        logger.info(f"{i+1}. {link}")
    
    results = []
    failed_count = 0
    
    for link in tqdm(links, desc="Scraping products"):
        data = extract_product_data(link)
        if data and data.get('product_name'):
            results.append(data)
            
            # Log product name and key stats
            if data.get('fine_gold_g') and data.get('price_bgn'):
                logger.debug(f"Extracted: {data['product_type']} - {data['product_name']} - {data['fine_gold_g']}g @ {data['price_bgn']} BGN")
        else:
            failed_count += 1
            if failed_count <= 5:  # Show first few failures for debugging
                logger.warning(f"Failed to extract data from: {link}")

    # Sort results by price per gram (ascending - lowest to highest)
    # Items without price per gram will be placed at the end
    results.sort(key=sort_key_function)
    
    logger.info(f"\nSorting {len(results)} products by price per gram (BGN)...")

    # Write CSV
    fname = 'igold_gold_products_sorted.csv'
    keys = ['product_name','url','product_type','total_weight_g','purity_per_mille','fine_gold_g',
            'price_bgn','price_eur','price_per_g_fine_bgn','price_per_g_fine_eur',
            'buy_price_bgn','sell_price_bgn','spread_percentage']
    
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
    
    # Show top 5 cheapest per gram and most expensive per gram
    if with_price_per_gram:
        logger.info(f"\n=== TOP 10 CHEAPEST PER GRAM (BGN) ===")
        for i, item in enumerate(with_price_per_gram[:10]):
            name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
            logger.info(f"{i+1}. {name} ({item['product_type']})")
            logger.info(f"   Price per gram: {item['price_per_g_fine_bgn']} BGN")
            logger.info(f"   Total price: {item['price_bgn']} BGN")
            logger.info(f"   Fine gold: {item['fine_gold_g']} g")
            logger.info("")
        
        logger.info(f"=== TOP 3 MOST EXPENSIVE PER GRAM (BGN) ===")
        for i, item in enumerate(with_price_per_gram[-3:][::-1]):  # Last 5, reversed
            name = item['product_name'][:60] + "..." if len(item['product_name'] or '') > 60 else item['product_name']
            logger.info(f"{i+1}. {name} ({item['product_type']})")
            logger.info(f"   Price per gram: {item['price_per_g_fine_bgn']} BGN")
            logger.info(f"   Total price: {item['price_bgn']} BGN")
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
                logger.info(f"   Total price: {item['price_bgn']} BGN")
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
                logger.info(f"   Total price: {item['price_bgn']} BGN")
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

if __name__ == '__main__':
    main()
