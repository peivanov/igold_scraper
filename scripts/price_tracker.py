#!/usr/bin/env python3
"""
Price change tracker and Discord notifier for igold scraper
Compares daily prices and sends notifications for significant changes
"""

import os
import json
from datetime import datetime, timedelta
import logging
import requests
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PriceTracker:
    def __init__(self, webhook_url: str, threshold: float = 5.0):
        self.webhook_url = webhook_url
        self.threshold = threshold
    
    def load_live_price(self, metal_type: str, date: str = None) -> Optional[Dict]:
        """Load live price for a specific metal and date (gold or silver)"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        file_path = f"data/live_prices/{metal_type}/{date}.json"
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Return the latest price if multiple entries exist
                    if isinstance(data, list) and len(data) > 0:
                        return data[-1]
                    return data
            except Exception as e:
                logger.error(f"Error loading live price {file_path}: {e}")
        return None
        
    def load_data(self, date: str, metal_type: str) -> Optional[Dict]:
        """Load data for a specific date and metal type"""
        file_path = f"data/{metal_type}/{date}.json"
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
        return None
    
    def get_top_products(self, products: List[Dict], top_n: int = 10) -> List[Dict]:
        """Get top N products with best price per fine gram"""
        # Filter products with valid prices
        valid_products = [p for p in products if p.get('price_per_g_fine_bgn')]
        
        # Sort by price per gram (ascending - best prices first)
        sorted_products = sorted(valid_products, key=lambda x: x.get('price_per_g_fine_bgn', float('inf')))
        
        return sorted_products[:top_n]
    
    def compare_prices(self, today_data: Dict, yesterday_data: Dict) -> List[Dict]:
        """Compare prices between two datasets - only for top 10 products with best price per fine gram"""
        changes = []
        
        if not today_data or not yesterday_data:
            return changes
        
        # Get top 10 products from today with best prices
        today_top_products = self.get_top_products(today_data.get('products', []), top_n=10)
        
        # Create lookup dictionaries
        today_products = {p.get('product_name', ''): p for p in today_top_products}
        yesterday_products = {p.get('product_name', ''): p for p in yesterday_data.get('products', [])}
        
        # Track changes only for top 10 products
        for name, today_product in today_products.items():
            if name in yesterday_products:
                yesterday_product = yesterday_products[name]
                
                # Compare price per gram (primary metric)
                today_price = today_product.get('price_per_g_fine_bgn')
                yesterday_price = yesterday_product.get('price_per_g_fine_bgn')
                
                if today_price and yesterday_price:
                    change_pct = ((today_price - yesterday_price) / yesterday_price) * 100
                    
                    if abs(change_pct) >= self.threshold:
                        changes.append({
                            'product_name': name,
                            'product_type': today_product.get('product_type', 'unknown'),
                            'metal_type': today_data.get('product_type', 'unknown'),
                            'yesterday_price': yesterday_price,
                            'today_price': today_price,
                            'change_percentage': change_pct,
                            'change_direction': 'increase' if change_pct > 0 else 'decrease',
                            'total_price_bgn': today_product.get('price_bgn'),
                            'fine_metal_g': today_product.get('fine_gold_g') or today_product.get('fine_silver_g'),
                            'url': today_product.get('url')
                        })
            else:
                # This is a new product in the top 10
                changes.append({
                    'product_name': name,
                    'product_type': today_product.get('product_type', 'unknown'),
                    'metal_type': today_data.get('product_type', 'unknown'),
                    'change_type': 'new_in_top_10',
                    'price_per_g': today_product.get('price_per_g_fine_bgn'),
                    'total_price_bgn': today_product.get('price_bgn'),
                    'fine_metal_g': today_product.get('fine_gold_g') or today_product.get('fine_silver_g'),
                    'url': today_product.get('url')
                })
        
        return changes
    
    def send_discord_notification(self, changes: List[Dict], metal_type: str, live_price: Optional[Dict] = None):
        """Send Discord notification for price changes (includes live market price for both gold and silver)"""
        if not self.webhook_url:
            return
        
        embeds = []
        
        # Add live price embed at the top (for both gold and silver)
        if live_price:
            prices = live_price.get('prices', {}).get('bgn_per_gram', {})
            mid_price = prices.get('mid', 0)
            bid_price = prices.get('bid', 0)
            ask_price = prices.get('ask', 0)
            timestamp = live_price.get('timestamp', '')
            metal_name = live_price.get('metal_name', metal_type)
            
            # Choose color and emoji based on metal type
            if metal_type == 'gold':
                color = 0xFFD700  # Gold color
                emoji = "💰"
            else:  # silver
                color = 0xC0C0C0  # Silver color
                emoji = "🪙"
            
            live_embed = {
                "title": f"{emoji} Live {metal_name.title()} Market Price",
                "color": color,
                "fields": [
                    {
                        "name": "Current Price",
                        "value": f"**{mid_price:.2f} BGN/g**",
                        "inline": True
                    },
                    {
                        "name": "Bid / Ask",
                        "value": f"{bid_price:.2f} / {ask_price:.2f} BGN/g",
                        "inline": True
                    },
                    {
                        "name": "Source",
                        "value": f"{live_price.get('source', 'Unknown')}",
                        "inline": True
                    }
                ],
                "timestamp": timestamp,
                "footer": {"text": f"Platform: {live_price.get('platform', 'Unknown')} | Spread: {live_price.get('prices', {}).get('eur_per_oz', {}).get('spread', 0)} EUR/oz"}
            }
            embeds.append(live_embed)
        
        # Skip rest if no changes
        if not changes:
            # Send live price only if available
            if embeds:
                payload = {"embeds": embeds}
                try:
                    response = requests.post(self.webhook_url, json=payload)
                    response.raise_for_status()
                    logger.info(f"Sent live {metal_type} price notification to Discord")
                except Exception as e:
                    logger.error(f"Failed to send Discord notification: {e}")
            return
            
        # Separate regular changes from new products in top 10
        price_changes = [c for c in changes if c.get('change_type') != 'new_in_top_10']
        new_in_top_10 = [c for c in changes if c.get('change_type') == 'new_in_top_10']
        
        embeds = []
        
        # Price changes embed
        if price_changes:
            color = 0x00ff00 if any(c['change_direction'] == 'decrease' for c in price_changes) else 0xff0000
            
            embed = {
                "title": f"{metal_type.title()} Price Changes (Top 10 Products) - {datetime.now().strftime('%Y-%m-%d')}",
                "color": color,
                "fields": [],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "igold.bg Price Tracker - Tracking top 10 products by best price per gram"}
            }
            
            # Sort by absolute change percentage
            sorted_changes = sorted(price_changes, key=lambda x: abs(x['change_percentage']), reverse=True)
            
            for change in sorted_changes[:10]:  # Limit to top 10 changes
                direction_emoji = "📈" if change['change_direction'] == 'increase' else "📉"
                change_sign = "+" if change['change_percentage'] > 0 else ""
                
                embed["fields"].append({
                    "name": f"{direction_emoji} {change['product_name'][:100]}",
                    "value": (
                        f"**{change_sign}{change['change_percentage']:.1f}%**\n"
                        f"Price/g: {change['yesterday_price']:.2f} → {change['today_price']:.2f} BGN\n"
                        f"Type: {change['product_type'].title()}\n"
                        f"[View Product]({change['url']})"
                    ),
                    "inline": True
                })
            
            embeds.append(embed)
        
        # New products in top 10 embed
        if new_in_top_10:
            embed = {
                "title": f"New in Top 10 {metal_type.title()} Products - {datetime.now().strftime('%Y-%m-%d')}",
                "color": 0x0099ff,
                "fields": [],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "igold.bg Price Tracker - Products newly entered top 10"}
            }
            
            for product in new_in_top_10[:10]:
                embed["fields"].append({
                    "name": f"⭐ {product['product_name'][:100]}",
                    "value": (
                        f"Price/g: {product.get('price_per_g', 'N/A'):.2f} BGN\n"
                        f"Total: {product.get('total_price_bgn', 'N/A')} BGN\n"
                        f"Type: {product['product_type'].title()}\n"
                        f"[View Product]({product['url']})"
                    ),
                    "inline": True
                })
            
            embeds.append(embed)
        
        # Send notification
        if embeds:
            payload = {"embeds": embeds}
            
            try:
                response = requests.post(self.webhook_url, json=payload)
                response.raise_for_status()
                logger.info(f"Sent Discord notification for {metal_type} with {len(changes)} changes")
            except Exception as e:
                logger.error(f"Failed to send Discord notification: {e}")
    
    def send_error_notification(self, error_message: str):
        """Send Discord notification for scraping errors"""
        if not self.webhook_url:
            return
            
        embed = {
            "title": "Scraping Error",
            "description": f"Error occurred during daily scraping:\n\n```{error_message}```",
            "color": 0xff0000,
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "igold.bg Price Tracker"}
        }
        
        payload = {"embeds": [embed]}
        
        try:
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
            logger.info("Sent error notification to Discord")
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

def main():
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    threshold = float(os.getenv('PRICE_CHANGE_THRESHOLD', '5.0'))
    
    if not webhook_url:
        logger.warning("No Discord webhook URL provided, notifications disabled")
        return
    
    tracker = PriceTracker(webhook_url, threshold)
    
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Process both gold and silver
    for metal_type in ['gold', 'silver']:
        logger.info(f"Processing {metal_type} price changes...")
        
        # Load live price for this metal
        live_price = tracker.load_live_price(metal_type, today)
        if live_price:
            logger.info(f"Loaded live {metal_type} price: {live_price['prices']['bgn_per_gram']['mid']:.2f} BGN/g")
        
        today_data = tracker.load_data(today, metal_type)
        yesterday_data = tracker.load_data(yesterday, metal_type)
        
        if not today_data:
            logger.warning(f"No {metal_type} data found for today ({today})")
            continue
            
        if not yesterday_data:
            logger.info(f"No {metal_type} data found for yesterday ({yesterday}), skipping comparison")
            continue
        
        changes = tracker.compare_prices(today_data, yesterday_data)
        
        if changes:
            logger.info(f"Found {len(changes)} significant {metal_type} changes")
            tracker.send_discord_notification(changes, metal_type, live_price)
        else:
            logger.info(f"No significant {metal_type} price changes detected")
            # Still send live price notification even if no changes
            if live_price:
                tracker.send_discord_notification([], metal_type, live_price)

if __name__ == '__main__':
    main()
