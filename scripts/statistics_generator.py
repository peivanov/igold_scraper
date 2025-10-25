#!/usr/bin/env python3
"""
Statistics generator for igold scraper historical data
Generates weekly and monthly market analysis reports
"""

import os
import json
import glob
from datetime import datetime, timedelta
import statistics
import logging
import requests
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StatisticsGenerator:
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
    
    def get_top_products(self, products: List[Dict], top_n: int = 10, metal_type: str = None) -> List[Dict]:
        """Get top N products with best price per fine gram (excludes Tavex fields)"""
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
        
    def load_historical_data(self, metal_type: str, days: int) -> List[Dict]:
        """Load historical data for specified number of days"""
        data = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            file_path = f"data/{metal_type}/{date}.json"
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        daily_data = json.load(f)
                        data.append(daily_data)
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")
        
        return data
    
    def load_live_prices(self, metal_type: str, days: int) -> List[Dict]:
        """Load historical live prices for specified metal type and number of days"""
        prices = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            file_path = f"data/live_prices/{metal_type}/{date}.json"
            
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Get the latest price entry for each day
                        if isinstance(data, list) and len(data) > 0:
                            prices.append(data[-1])
                        elif isinstance(data, dict):
                            prices.append(data)
                except Exception as e:
                    logger.error(f"Error loading live price {file_path}: {e}")
        
        return prices
    
    def calculate_market_statistics(self, historical_data: List[Dict], live_prices: List[Dict] = None, metal_type: str = 'gold') -> Dict:
        """Calculate market statistics from historical data - focusing on top 10 products"""
        if not historical_data:
            return {}
            
        stats = {
            'period_days': len(historical_data),
            'unique_products_in_top_10': set(),
            'average_price_per_gram': 0,
            'price_volatility': 0,
            'price_trend': 'stable',
            'cheapest_products': [],
            'product_type_breakdown': {'bars': 0, 'coins': 0},
            'daily_top_10_averages': []
        }
        
        daily_top_10_averages = []
        all_top_10_names = set()
        product_type_counts = {'bars': 0, 'coins': 0}
        
        # Analyze each day's top 10 products
        for day_data in historical_data:
            products = day_data.get('products', [])
            
            # Get top 10 for this day - filter by metal type
            top_10 = self.get_top_products(products, top_n=10, metal_type=metal_type)
            
            if not top_10:
                continue
            
            # Track unique product names that appeared in top 10
            for product in top_10:
                all_top_10_names.add(product.get('product_name', ''))
                
                # Count product types (count each occurrence)
                product_type = product.get('product_type', 'unknown')
                if product_type == 'bar':
                    product_type_counts['bars'] += 1
                elif product_type == 'coin':
                    product_type_counts['coins'] += 1
            
            # Calculate daily average for top 10
            daily_prices = [p.get('price_per_g_fine_bgn') for p in top_10 if p.get('price_per_g_fine_bgn')]
            
            if daily_prices:
                daily_avg = statistics.mean(daily_prices)
                daily_top_10_averages.append({
                    'date': day_data.get('date'),
                    'average_price': daily_avg,
                    'top_10_count': len(top_10)
                })
        
        # Calculate overall statistics
        if daily_top_10_averages:
            # Average of daily top-10 averages
            overall_avg = statistics.mean([d['average_price'] for d in daily_top_10_averages])
            stats['average_price_per_gram'] = overall_avg
            
            # Volatility based on daily averages (not individual products)
            if len(daily_top_10_averages) > 1:
                stats['price_volatility'] = statistics.stdev([d['average_price'] for d in daily_top_10_averages])
            
            # Calculate trend from daily averages
            if len(daily_top_10_averages) >= 2:
                first_avg = daily_top_10_averages[-1]['average_price']  # Oldest
                last_avg = daily_top_10_averages[0]['average_price']    # Newest
                
                trend_pct = ((last_avg - first_avg) / first_avg) * 100
                
                if trend_pct > 2:
                    stats['price_trend'] = 'increasing'
                elif trend_pct < -2:
                    stats['price_trend'] = 'decreasing'
                else:
                    stats['price_trend'] = 'stable'
                
                stats['trend_percentage'] = trend_pct
        
        stats['unique_products_in_top_10'] = len(all_top_10_names)
        stats['product_type_breakdown'] = product_type_counts
        stats['daily_top_10_averages'] = daily_top_10_averages[:7]  # Last 7 days
        
        # Add live price statistics if available
        if live_prices:
            live_price_data = []
            for price_entry in live_prices:
                bgn_mid = price_entry.get('prices', {}).get('bgn_per_gram', {}).get('mid')
                date = price_entry.get('date')
                if bgn_mid and date:
                    live_price_data.append({'date': date, 'price': bgn_mid})
            
            if live_price_data:
                stats['live_prices'] = live_price_data[:7]  # Last 7 days
                
                # Calculate live price trend
                if len(live_price_data) >= 2:
                    oldest_live = live_price_data[-1]['price']
                    newest_live = live_price_data[0]['price']
                    live_trend_pct = ((newest_live - oldest_live) / oldest_live) * 100
                    stats['live_price_trend_percentage'] = live_trend_pct
                    
                    if live_trend_pct > 2:
                        stats['live_price_trend'] = 'increasing'
                    elif live_trend_pct < -2:
                        stats['live_price_trend'] = 'decreasing'
                    else:
                        stats['live_price_trend'] = 'stable'
                
                # Current live price
                stats['current_live_price_bgn_g'] = live_price_data[0]['price']
                
                # Add metal type for reference
                stats['live_price_metal'] = live_prices[0].get('metal_name', 'unknown')
        
        # Get cheapest products from latest data (top 10 only, filtered by metal type)
        if historical_data:
            latest_products = historical_data[0].get('products', [])
            top_10_latest = self.get_top_products(latest_products, top_n=10, metal_type=metal_type)
            
            # Already sorted by price, so first 5 are cheapest
            stats['cheapest_products'] = top_10_latest[:5]
        
        return stats
    
    def generate_report(self, period: str = 'weekly'):
        """Generate statistics report for specified period"""
        days = 7 if period == 'weekly' else 30
        report_date = datetime.now().strftime('%Y-%m-%d')
        
        reports = {}
        
        for metal_type in ['gold', 'silver']:
            logger.info(f"Generating {period} {metal_type} statistics...")
            
            historical_data = self.load_historical_data(metal_type, days)
            
            if not historical_data:
                logger.warning(f"No historical data found for {metal_type}")
                continue
            
            # Load live prices for this metal type
            live_prices = self.load_live_prices(metal_type, days)
            if live_prices:
                logger.info(f"Loaded {len(live_prices)} days of live {metal_type} prices")
            
            stats = self.calculate_market_statistics(historical_data, live_prices, metal_type)
            
            report = {
                'report_type': period,
                'metal_type': metal_type,
                'report_date': report_date,
                'period_start': (datetime.now() - timedelta(days=days-1)).strftime('%Y-%m-%d'),
                'period_end': datetime.now().strftime('%Y-%m-%d'),
                'statistics': stats,
                'data_points': len(historical_data)
            }
            
            reports[metal_type] = report
            
            # Save report
            output_file = f"data/statistics/{metal_type}_{period}_{report_date}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved {metal_type} {period} report to {output_file}")
        
        # Send Discord summary if webhook is available
        if self.webhook_url and reports:
            self.send_statistics_notification(reports, period)
        
        return reports
    
    def send_statistics_notification(self, reports: Dict, period: str):
        """Send Discord notification with statistics summary (Top 10 products focus)"""
        embeds = []
        
        for metal_type, report in reports.items():
            stats = report.get('statistics', {})
            
            # Determine color based on trend
            trend = stats.get('price_trend', 'stable')
            if trend == 'increasing':
                color = 0xff0000  # Red for price increases
            elif trend == 'decreasing':
                color = 0x00ff00  # Green for price decreases
            else:
                color = 0xffff00  # Yellow for stable
            
            trend_emoji = {'increasing': '📈', 'decreasing': '📉', 'stable': '➡️'}
            
            embed = {
                "title": f"📊 {period.title()} {metal_type.title()} Market Report (Top 10 Products)",
                "color": color,
                "fields": [
                    {
                        "name": "Market Trend",
                        "value": f"{trend_emoji.get(trend, '➡️')} {trend.title()}",
                        "inline": True
                    },
                    {
                        "name": "Avg Price/gram (Top 10)",
                        "value": f"{stats.get('average_price_per_gram', 0):.2f} BGN",
                        "inline": True
                    },
                    {
                        "name": "Unique Products Tracked",
                        "value": str(stats.get('unique_products_in_top_10', 0)),
                        "inline": True
                    }
                ],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": f"Period: {report.get('period_start')} to {report.get('period_end')} | Tracking top 10 by price per gram"}
            }
            
            # Add trend percentage if available
            if 'trend_percentage' in stats:
                trend_sign = "+" if stats['trend_percentage'] > 0 else ""
                embed["fields"].append({
                    "name": "Price Change",
                    "value": f"{trend_sign}{stats['trend_percentage']:.2f}%",
                    "inline": True
                })
            
            # Add volatility
            if stats.get('price_volatility', 0) > 0:
                embed["fields"].append({
                    "name": "Price Volatility",
                    "value": f"{stats['price_volatility']:.2f} BGN/g",
                    "inline": True
                })
            
            # Add product breakdown
            breakdown = stats.get('product_type_breakdown', {})
            if any(breakdown.values()):
                breakdown_text = f"Bars: {breakdown.get('bars', 0)} | Coins: {breakdown.get('coins', 0)}"
                embed["fields"].append({
                    "name": "Product Types in Top 10",
                    "value": breakdown_text,
                    "inline": True
                })
            
            # Add live price info (for both gold and silver)
            if 'current_live_price_bgn_g' in stats:
                live_price = stats['current_live_price_bgn_g']
                live_trend = stats.get('live_price_trend', 'stable')
                live_trend_pct = stats.get('live_price_trend_percentage', 0)
                live_trend_sign = "+" if live_trend_pct > 0 else ""
                
                # Choose emoji based on metal type
                price_emoji = "💰" if metal_type == 'gold' else "🪙"
                
                embed["fields"].append({
                    "name": f"{price_emoji} Current Live {metal_type.title()} Price",
                    "value": f"**{live_price:.2f} BGN/g** ({trend_emoji.get(live_trend, '➡️')} {live_trend_sign}{live_trend_pct:.2f}%)",
                    "inline": False
                })
            
            # Add best deal (cheapest product)
            cheapest = stats.get('cheapest_products', [])
            if cheapest:
                product = cheapest[0]
                product_name = product.get('product_name', 'Unknown')[:80]
                embed["fields"].append({
                    "name": "🏆 Best Deal",
                    "value": f"{product_name}\n**{product.get('price_per_g_fine_bgn', 0):.2f} BGN/g**\n[View]({product.get('url', '#')})",
                    "inline": False
                })
            
            embeds.append(embed)
        
        if embeds:
            payload = {"embeds": embeds}
            
            try:
                response = requests.post(self.webhook_url, json=payload)
                response.raise_for_status()
                logger.info(f"Sent {period} statistics notification to Discord")
            except Exception as e:
                logger.error(f"Failed to send statistics notification: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate statistics reports')
    parser.add_argument('--period', choices=['weekly', 'monthly'], default='weekly', 
                       help='Report period (weekly or monthly)')
    args = parser.parse_args()
    
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    generator = StatisticsGenerator(webhook_url)
    
    reports = generator.generate_report(args.period)
    
    if reports:
        logger.info(f"Generated {args.period} reports for {len(reports)} metal types")
    else:
        logger.warning("No reports generated - check data availability")

if __name__ == '__main__':
    main()
