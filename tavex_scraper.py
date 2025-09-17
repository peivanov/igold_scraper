#!/usr/bin/env python3

"""
Tavex.bg gold scraper
Scrapes gold product information (buy/sell prices) from tavex.bg.

Can be used as a standalone script or imported as a module.

When run as a standalone script, it saves the data to tavex_gold_products.json.
When imported as a module, the scrape_tavex_gold_products() function can be used
to get the gold product data.
"""

import requests
import json
import logging
import argparse
from bs4 import BeautifulSoup

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def scrape_tavex_gold_products():
    """
    Scrape gold product information from tavex.bg.
    
    Returns:
        List of dictionaries containing gold product information:
        - name: Product name
        - buy_price: Buy price in BGN
        - sell_price: Sell price in BGN
        - spread_percentage: Spread percentage
    """
    # URL of the page to scrape
    url = 'https://tavex.bg/zlato/'
    
    logger.info(f"Fetching data from {url}")
    
    # Send HTTP request to the URL
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch data: {e}")
        return []
    
    # Parse the HTML content
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find the modal div with gold products
    modal_div = soup.find('div', {'id': 'modaal-add-price-alert'})
    
    if not modal_div:
        logger.error("Modal div not found - website structure may have changed")
        return []
    
    # Find all option elements inside the modal div
    options = modal_div.find_all('option')
    
    gold_products = []
    error_count = 0
    
    logger.info(f"Found {len(options)} potential products")
    
    for option in options:
        # Skip empty options or those without data-pricelist
        if not option.get('data-pricelist'):
            continue
        
        # Get product name
        name = option.text.strip()
        
        # Get price data
        try:
            price_data = json.loads(option['data-pricelist'])
            
            # Extract buy price (first item in the buy array)
            buy_price = None
            if price_data.get('buy') and len(price_data['buy']) > 0:
                buy_price = float(price_data['buy'][0]['price'])
            
            # Extract sell price (first item in the sell array)
            sell_price = None
            if price_data.get('sell') and len(price_data['sell']) > 0:
                sell_price = float(price_data['sell'][0]['price'])
            
            # Calculate spread percentage
            spread_percentage = None
            if name and buy_price is not None and sell_price is not None and sell_price > 0:
                spread_percentage = ((sell_price - buy_price) / sell_price) * 100
                spread_percentage = round(spread_percentage, 2)  # Round to 2 decimal places
                
            # Add to our list
            if name and buy_price is not None and sell_price is not None:
                gold_products.append({
                    'name': name,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'spread_percentage': spread_percentage
                })
                
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Error parsing data for {name}: {e}")
            error_count += 1
            continue
    
    logger.info(f"Successfully scraped {len(gold_products)} products, {error_count} errors")
    return gold_products

def save_to_json(gold_products, output_file="tavex_gold_products.json"):
    """
    Save gold product information to a JSON file.
    
    Args:
        gold_products: List of dictionaries containing gold product information
        output_file: Path to the output JSON file
    """
    try:
        # Create formatted JSON
        formatted_json = json.dumps(gold_products, ensure_ascii=False, indent=2)
        
        # Save to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(formatted_json)
        
        logger.info(f"Data saved to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error saving data to {output_file}: {e}")
        return False

def main():
    """
    Main function when script is run standalone.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scrape gold product information from tavex.bg')
    parser.add_argument('--output', '-o', default='tavex_gold_products.json',
                      help='Output JSON file (default: tavex_gold_products.json)')
    args = parser.parse_args()
    
    # Scrape gold product information
    gold_products = scrape_tavex_gold_products()
    
    # Check if products were found
    if not gold_products:
        logger.error("No gold products were found.")
        return
    
    # Save to JSON
    save_to_json(gold_products, args.output)
    
    # Print summary
    print(f"Total products found: {len(gold_products)}")
    
    # Show some statistics
    total_buy = sum(product['buy_price'] for product in gold_products)
    total_sell = sum(product['sell_price'] for product in gold_products)
    avg_spread = sum(product['spread_percentage'] for product in gold_products) / len(gold_products)
    
    print(f"Average spread: {avg_spread:.2f}%")
    
    # Print a few example products
    print("\nExample products:")
    for i, product in enumerate(gold_products[:5]):
        print(f"{i+1}. {product['name']}")
        print(f"   Buy price: {product['buy_price']} BGN")
        print(f"   Sell price: {product['sell_price']} BGN")
        print(f"   Spread: {product['spread_percentage']}%")
        print()

if __name__ == "__main__":
    main()
