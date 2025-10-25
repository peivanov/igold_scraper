#!/usr/bin/env python3
"""
Daily Precious Metals Market Report Generator
Generates daily reports comparing today's top 10 products vs yesterday
"""

import json
import os
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger()

class DailyReportGenerator:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.data_dir = self.base_dir / "data"
        self.stats_dir = self.data_dir / "statistics"
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        
    def get_top_products(self, products: List[Dict], top_n: int = 10, metal_type: str = None) -> List[Dict]:
        """Get top N products with best price per fine gram (available for sale only)"""
        # Filter products with valid prices AND available for sale (sell_price > 0)
        valid_products = [p for p in products 
                         if p.get('price_per_g_fine_bgn') 
                         and p.get('sell_price_bgn') 
                         and p.get('sell_price_bgn') != 0
                         and p.get('sell_price_bgn') != '']
        
        # Additional filter: ensure products match the expected metal type
        if metal_type:
            metal_field = f'fine_{metal_type}_g'
            valid_products = [p for p in valid_products if p.get(metal_field)]
        
        # Sort by price per gram (ascending - best prices first)
        sorted_products = sorted(valid_products, key=lambda x: x.get('price_per_g_fine_bgn', float('inf')))
        
        # Remove Tavex fields from products
        clean_products = []
        for product in sorted_products[:top_n]:
            clean_product = {k: v for k, v in product.items() 
                           if not k.startswith('tavex_') and k != 'is_cheaper'}
            clean_products.append(clean_product)
        
        return clean_products
    
    def load_data(self, metal_type: str, date: datetime) -> Optional[Dict]:
        """Load product data for a specific date"""
        date_str = date.strftime('%Y-%m-%d')
        file_path = self.data_dir / metal_type / f"{date_str}.json"
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None
    
    def load_live_price(self, metal_type: str, date: datetime) -> Optional[float]:
        """Load live price for a specific date"""
        date_str = date.strftime('%Y-%m-%d')
        file_path = self.data_dir / "live_prices" / metal_type / f"{date_str}.json"
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle both array and object formats
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]  # Take first entry if it's an array
                return data.get('price_bgn_per_g')
        except Exception as e:
            logger.error(f"Error loading live price from {file_path}: {e}")
            return None
    
    def calculate_daily_statistics(self, today_data: Dict, yesterday_data: Optional[Dict], 
                                   today_live_price: Optional[float], yesterday_live_price: Optional[float],
                                   metal_type: str = 'gold') -> Dict:
        """Calculate daily market statistics"""
        
        today_products = today_data.get('products', [])
        today_top_10 = self.get_top_products(today_products, top_n=10, metal_type=metal_type)
        
        # Calculate today's metrics
        today_avg = sum(p['price_per_g_fine_bgn'] for p in today_top_10) / len(today_top_10) if today_top_10 else 0
        
        # Product type breakdown
        bars_count = sum(1 for p in today_top_10 if p.get('product_type') == 'bar')
        coins_count = sum(1 for p in today_top_10 if p.get('product_type') == 'coin')
        
        # Compare with yesterday
        yesterday_avg = 0
        new_products_count = 0
        price_change_pct = 0
        trend = "stable"
        
        if yesterday_data:
            yesterday_products = yesterday_data.get('products', [])
            yesterday_top_10 = self.get_top_products(yesterday_products, top_n=10, metal_type=metal_type)
            
            if yesterday_top_10:
                yesterday_avg = sum(p['price_per_g_fine_bgn'] for p in yesterday_top_10) / len(yesterday_top_10)
                price_change_pct = ((today_avg - yesterday_avg) / yesterday_avg * 100) if yesterday_avg > 0 else 0
                
                # Determine trend
                if abs(price_change_pct) < 1.0:
                    trend = "stable"
                elif price_change_pct > 0:
                    trend = "increasing"
                else:
                    trend = "decreasing"
            
            # Count new products
            yesterday_urls = {p.get('url') for p in yesterday_products}
            new_products_count = sum(1 for p in today_products if p.get('url') not in yesterday_urls)
        
        # Live price comparison
        live_price_change_pct = 0
        if today_live_price and yesterday_live_price:
            live_price_change_pct = ((today_live_price - yesterday_live_price) / yesterday_live_price * 100)
        
        return {
            'today_date': today_data.get('date'),
            'yesterday_date': yesterday_data.get('date') if yesterday_data else None,
            'top_10_count': len(today_top_10),
            'average_price_per_gram': round(today_avg, 2),
            'yesterday_average': round(yesterday_avg, 2) if yesterday_avg > 0 else None,
            'price_change_pct': round(price_change_pct, 2),
            'trend': trend,
            'product_types': {
                'bars': bars_count,
                'coins': coins_count
            },
            'new_products_count': new_products_count,
            'total_products_today': len(today_products),
            'best_deals': today_top_10,
            'live_price_today': today_live_price,
            'live_price_yesterday': yesterday_live_price,
            'live_price_change_pct': round(live_price_change_pct, 2) if today_live_price and yesterday_live_price else None
        }
    
    def format_discord_message(self, stats: Dict, metal_type: str) -> Dict:
        """Format statistics as Discord embed message"""
        
        metal_emoji = "💰" if metal_type == "gold" else "🪙"
        metal_name = metal_type.capitalize()
        
        # Trend emoji
        trend_emoji = {
            'increasing': '📈',
            'decreasing': '📉',
            'stable': '➡️'
        }.get(stats['trend'], '➡️')
        
        # Price change emoji
        if stats['price_change_pct'] > 1:
            change_emoji = '📈'
        elif stats['price_change_pct'] < -1:
            change_emoji = '📉'
        else:
            change_emoji = '➡️'
        
        # Build best deals list (top 5 for Discord to keep message short)
        best_deals_text = ""
        for i, product in enumerate(stats['best_deals'][:5], 1):
            name = product['product_name'][:60]
            price_per_g = product['price_per_g_fine_bgn']
            sell_price = product.get('sell_price_bgn', 0)
            url = product.get('url', '')
            
            best_deals_text += f"{i}. **{name}**\n"
            best_deals_text += f"   {price_per_g:.2f} BGN/g | Total: {sell_price:.0f} BGN\n"
            if url:
                best_deals_text += f"   [View Product]({url})\n"
            best_deals_text += "\n"
        
        # Build embed fields
        fields = [
            {
                "name": "Market Trend",
                "value": f"{trend_emoji} {stats['trend'].capitalize()}",
                "inline": True
            },
            {
                "name": "Avg Price/gram (Top 10)",
                "value": f"{stats['average_price_per_gram']} BGN",
                "inline": True
            }
        ]
        
        # Add price change if available
        if stats['yesterday_average']:
            fields.append({
                "name": "Daily Change",
                "value": f"{change_emoji} {stats['price_change_pct']:+.2f}%",
                "inline": True
            })
        
        fields.extend([
            {
                "name": "Product Types",
                "value": f"Bars: {stats['product_types']['bars']} | Coins: {stats['product_types']['coins']}",
                "inline": True
            },
            {
                "name": "Total Products",
                "value": str(stats['total_products_today']),
                "inline": True
            }
        ])
        
        # Add new products if any
        if stats['new_products_count'] > 0:
            fields.append({
                "name": "New Products",
                "value": f"🆕 {stats['new_products_count']} new products today",
                "inline": True
            })
        
        # Add live price
        if stats['live_price_today']:
            live_price_text = f"{stats['live_price_today']:.2f} BGN/g"
            if stats['live_price_change_pct'] is not None:
                live_price_text += f" ({stats['live_price_change_pct']:+.2f}%)"
            
            fields.append({
                "name": f"{metal_emoji} Live {metal_name} Price",
                "value": live_price_text,
                "inline": False
            })
        
        # Add best deals
        if best_deals_text:
            fields.append({
                "name": "🏆 Top 5 Best Deals",
                "value": best_deals_text,
                "inline": False
            })
        
        # Color based on trend
        color = {
            'increasing': 0xff4444,  # Red
            'decreasing': 0x44ff44,  # Green (good for buyers)
            'stable': 0xffaa00       # Orange
        }.get(stats['trend'], 0xffaa00)
        
        embed = {
            "embeds": [{
                "title": f"📊 Daily {metal_name} Market Report",
                "description": f"Top 10 products comparison: {stats['today_date']}",
                "color": color,
                "fields": fields,
                "footer": {
                    "text": f"Tracking top 10 products by price per gram • Data from igold.bg"
                },
                "timestamp": datetime.now().isoformat()
            }]
        }
        
        return embed
    
    def send_discord_notification(self, message: Dict) -> bool:
        """Send notification to Discord webhook"""
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if not webhook_url:
            logger.warning("DISCORD_WEBHOOK_URL not set, skipping Discord notification")
            return False
        
        try:
            response = requests.post(webhook_url, json=message, timeout=10)
            response.raise_for_status()
            logger.info("Successfully sent Discord notification")
            return True
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False
    
    def generate_daily_reports(self):
        """Generate and send daily reports for all metals"""
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        for metal_type in ['gold', 'silver']:
            logger.info(f"Generating daily {metal_type} report...")
            
            # Load data
            today_data = self.load_data(metal_type, today)
            yesterday_data = self.load_data(metal_type, yesterday)
            
            if not today_data:
                logger.warning(f"No {metal_type} data found for today ({today.strftime('%Y-%m-%d')})")
                continue
            
            # Load live prices
            today_live_price = self.load_live_price(metal_type, today)
            yesterday_live_price = self.load_live_price(metal_type, yesterday)
            
            # Calculate statistics
            stats = self.calculate_daily_statistics(
                today_data, yesterday_data, 
                today_live_price, yesterday_live_price,
                metal_type
            )
            
            # Save report
            report = {
                'report_type': 'daily',
                'metal_type': metal_type,
                'report_date': today.strftime('%Y-%m-%d'),
                'statistics': stats
            }
            
            report_file = self.stats_dir / f"{metal_type}_daily_{today.strftime('%Y-%m-%d')}.json"
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved daily {metal_type} report to {report_file}")
            
            # Send Discord notification
            discord_message = self.format_discord_message(stats, metal_type)
            self.send_discord_notification(discord_message)
        
        logger.info("Daily reports generation completed")

def main():
    generator = DailyReportGenerator()
    generator.generate_daily_reports()

if __name__ == "__main__":
    main()
