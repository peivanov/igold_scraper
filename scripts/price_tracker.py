#!/usr/bin/env python3
"""
Price change tracker and Discord notifier for igold scraper
Compares daily prices and sends notifications for significant changes
"""

import os
import json
import glob
from datetime import datetime, timedelta
import logging
import requests
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PriceTracker:
    def __init__(self, webhook_url: str, threshold: float = 5.0):
        self.webhook_url = webhook_url
        self.threshold = threshold
        
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
    
    def compare_prices(self, today_data: Dict, yesterday_data: Dict) -> List[Dict]:
        """Compare prices between two datasets and identify significant changes"""
        changes = []
        
        if not today_data or not yesterday_data:
            return changes
            
        today_products = {p.get('product_name', ''): p for p in today_data.get('products', [])}
        yesterday_products = {p.get('product_name', ''): p for p in yesterday_data.get('products', [])}
        
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
        
        # Check for new products
        new_products = set(today_products.keys()) - set(yesterday_products.keys())
        for name in new_products:
            product = today_products[name]
            changes.append({
                'product_name': name,
                'product_type': product.get('product_type', 'unknown'),
                'metal_type': today_data.get('product_type', 'unknown'),
                'change_type': 'new_product',
                'price_per_g': product.get('price_per_g_fine_bgn'),
                'total_price_bgn': product.get('price_bgn'),
                'fine_metal_g': product.get('fine_gold_g') or product.get('fine_silver_g'),
                'url': product.get('url')
            })
        
        return changes
    
    def send_discord_notification(self, changes: List[Dict], metal_type: str):
        """Send Discord notification for price changes"""
        if not changes or not self.webhook_url:
            return
            
        # Separate regular changes from new products
        price_changes = [c for c in changes if c.get('change_type') != 'new_product']
        new_products = [c for c in changes if c.get('change_type') == 'new_product']
        
        embeds = []
        
        # Price changes embed
        if price_changes:
            color = 0x00ff00 if any(c['change_direction'] == 'decrease' for c in price_changes) else 0xff0000
            
            embed = {
                "title": f"{metal_type.title()} Price Changes - {datetime.now().strftime('%Y-%m-%d')}",
                "color": color,
                "fields": [],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "igold.bg Price Tracker"}
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
        
        # New products embed
        if new_products:
            embed = {
                "title": f"New {metal_type.title()} Products - {datetime.now().strftime('%Y-%m-%d')}",
                "color": 0x0099ff,
                "fields": [],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "igold.bg Price Tracker"}
            }
            
            for product in new_products[:10]:  # Limit to 10 new products
                embed["fields"].append({
                    "name": f"New {product['product_name'][:100]}",
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
            tracker.send_discord_notification(changes, metal_type)
        else:
            logger.info(f"No significant {metal_type} price changes detected")

if __name__ == '__main__':
    main()
