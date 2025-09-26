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
    
    def calculate_market_statistics(self, historical_data: List[Dict]) -> Dict:
        """Calculate market statistics from historical data"""
        if not historical_data:
            return {}
            
        stats = {
            'period_days': len(historical_data),
            'total_products': 0,
            'average_price_per_gram': 0,
            'price_volatility': 0,
            'price_trend': 'stable',
            'cheapest_products': [],
            'most_expensive_products': [],
            'product_type_breakdown': {'bars': 0, 'coins': 0, 'unknown': 0},
            'daily_averages': []
        }
        
        all_prices = []
        daily_averages = []
        product_counts = {'bars': 0, 'coins': 0, 'unknown': 0}
        
        for day_data in historical_data:
            products = day_data.get('products', [])
            daily_prices = []
            
            for product in products:
                price_per_g = product.get('price_per_g_fine_bgn')
                if price_per_g:
                    all_prices.append(price_per_g)
                    daily_prices.append(price_per_g)
                
                product_type = product.get('product_type', 'unknown')
                if product_type in product_counts:
                    product_counts[product_type] += 1
            
            if daily_prices:
                daily_avg = statistics.mean(daily_prices)
                daily_averages.append({
                    'date': day_data.get('date'),
                    'average_price': daily_avg,
                    'product_count': len(products)
                })
        
        if all_prices:
            stats['total_products'] = len(all_prices)
            stats['average_price_per_gram'] = statistics.mean(all_prices)
            
            if len(all_prices) > 1:
                stats['price_volatility'] = statistics.stdev(all_prices)
            
            # Calculate trend from daily averages
            if len(daily_averages) >= 2:
                first_avg = daily_averages[-1]['average_price']  # Oldest
                last_avg = daily_averages[0]['average_price']    # Newest
                
                trend_pct = ((last_avg - first_avg) / first_avg) * 100
                
                if trend_pct > 2:
                    stats['price_trend'] = 'increasing'
                elif trend_pct < -2:
                    stats['price_trend'] = 'decreasing'
                else:
                    stats['price_trend'] = 'stable'
                
                stats['trend_percentage'] = trend_pct
        
        stats['product_type_breakdown'] = product_counts
        stats['daily_averages'] = daily_averages[:7]  # Last 7 days
        
        # Find cheapest and most expensive products from latest data
        if historical_data:
            latest_products = historical_data[0].get('products', [])
            products_with_prices = [p for p in latest_products if p.get('price_per_g_fine_bgn')]
            
            if products_with_prices:
                # Sort by price per gram
                sorted_products = sorted(products_with_prices, key=lambda x: x['price_per_g_fine_bgn'])
                
                stats['cheapest_products'] = sorted_products[:5]
                stats['most_expensive_products'] = sorted_products[-5:]
        
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
            
            stats = self.calculate_market_statistics(historical_data)
            
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
        """Send Discord notification with statistics summary"""
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
                "title": f"📊 {period.title()} {metal_type.title()} Market Report",
                "color": color,
                "fields": [
                    {
                        "name": "Market Trend",
                        "value": f"{trend_emoji.get(trend, '➡️')} {trend.title()}",
                        "inline": True
                    },
                    {
                        "name": "Avg Price/gram",
                        "value": f"{stats.get('average_price_per_gram', 0):.2f} BGN",
                        "inline": True
                    },
                    {
                        "name": "Total Products",
                        "value": str(stats.get('total_products', 0)),
                        "inline": True
                    }
                ],
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": f"Period: {report.get('period_start')} to {report.get('period_end')}"}
            }
            
            # Add trend percentage if available
            if 'trend_percentage' in stats:
                trend_sign = "+" if stats['trend_percentage'] > 0 else ""
                embed["fields"].append({
                    "name": "Price Change",
                    "value": f"{trend_sign}{stats['trend_percentage']:.1f}%",
                    "inline": True
                })
            
            # Add product breakdown
            breakdown = stats.get('product_type_breakdown', {})
            if any(breakdown.values()):
                breakdown_text = f"Bars: {breakdown.get('bars', 0)} | Coins: {breakdown.get('coins', 0)}"
                embed["fields"].append({
                    "name": "Product Types",
                    "value": breakdown_text,
                    "inline": True
                })
            
            # Add cheapest product
            cheapest = stats.get('cheapest_products', [])
            if cheapest:
                product = cheapest[0]
                embed["fields"].append({
                    "name": "Best Deal",
                    "value": f"{product.get('product_name', 'Unknown')[:50]}...\n{product.get('price_per_g_fine_bgn', 0):.2f} BGN/g",
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
