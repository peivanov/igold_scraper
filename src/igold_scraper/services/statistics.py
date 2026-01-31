#!/usr/bin/env python3
"""
Statistics generator for igold scraper using SQLite database.
Generates market analysis reports from database.
"""

import argparse
import logging
import statistics as stats_module
from datetime import datetime, timedelta
from typing import Dict, List

from igold_scraper.services.database_manager import DatabaseManager
from igold_scraper.config import DEFAULT_DB_PATH

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StatisticsGenerator:
    """Generates market analysis reports for precious metals."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Initialize statistics generator.

        Args:
            db_path: Path to SQLite database
        """
        self.db = DatabaseManager(db_path)

    def get_top_products(
        self,
        metal_type: str,
        top_n: int = 10,
        days: int = 30
    ) -> List[Dict]:
        """
        Get top N products with best price per fine gram within the specified period.

        Args:
            metal_type: 'gold' or 'silver'
            top_n: Number of top products to return
            days: Number of days to look back for prices

        Returns:
            List of product dicts sorted by price per gram
        """
        cutoff_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())

        # Get latest prices within the time period
        cursor = self.db.conn.execute("""
            WITH RankedPrices AS (
                SELECT
                    p.id,
                    p.product_name,
                    p.product_type,
                    p.total_weight_g,
                    ph.sell_price_eur,
                    ph.buy_price_eur,
                    ph.price_per_g_fine_eur,
                    ph.timestamp,
                    ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY ph.timestamp DESC) as rn
                FROM products p
                JOIN price_history ph ON p.id = ph.product_id
                WHERE p.metal_type = ?
                AND ph.timestamp >= ?
                AND ph.price_per_g_fine_eur IS NOT NULL
            )
            SELECT
                product_name,
                product_type,
                total_weight_g,
                sell_price_eur,
                buy_price_eur,
                price_per_g_fine_eur
            FROM RankedPrices
            WHERE rn = 1
            ORDER BY price_per_g_fine_eur ASC
            LIMIT ?
        """, (metal_type, cutoff_timestamp, top_n))

        return [dict(row) for row in cursor.fetchall()]

    def get_price_statistics(
        self,
        metal_type: str,
        days: int = 30
    ) -> Dict:
        """
        Calculate price statistics over specified period.

        Args:
            metal_type: 'gold' or 'silver'
            days: Number of days to analyze

        Returns:
            Dict with statistics (avg, min, max, volatility, etc.)
        """
        cutoff_timestamp = int((datetime.now() - timedelta(days=days)).timestamp())

        # Query all prices for metal type in the period
        cursor = self.db.conn.execute("""
            SELECT
                ph.timestamp,
                ph.sell_price_eur,
                ph.price_per_g_fine_eur,
                p.product_type
            FROM price_history ph
            JOIN products p ON ph.product_id = p.id
            WHERE p.metal_type = ? AND ph.timestamp >= ?
            ORDER BY ph.timestamp
        """, (metal_type, cutoff_timestamp))

        prices = cursor.fetchall()

        if not prices:
            return {
                'period_days': days,
                'total_price_entries': 0,
                'error': 'No data available for period'
            }

        # Extract price per gram values
        price_per_g_values = [
            p['price_per_g_fine_eur']
            for p in prices
            if p['price_per_g_fine_eur']
        ]

        if not price_per_g_values:
            return {
                'period_days': days,
                'total_price_entries': len(prices),
                'error': 'No valid price per gram data'
            }

        # Calculate statistics
        avg_price = stats_module.mean(price_per_g_values)
        min_price = min(price_per_g_values)
        max_price = max(price_per_g_values)

        # Calculate volatility (standard deviation)
        volatility = stats_module.stdev(price_per_g_values) if len(price_per_g_values) > 1 else 0

        # Calculate trend (compare first 7 days vs last 7 days)
        trend = 'stable'
        if len(price_per_g_values) >= 14:
            first_week_avg = stats_module.mean(price_per_g_values[:7])
            last_week_avg = stats_module.mean(price_per_g_values[-7:])
            change_pct = ((last_week_avg - first_week_avg) / first_week_avg) * 100

            if change_pct > 2:
                trend = 'increasing'
            elif change_pct < -2:
                trend = 'decreasing'

        # Count product types
        type_counts = {}
        for p in prices:
            ptype = p['product_type']
            type_counts[ptype] = type_counts.get(ptype, 0) + 1

        return {
            'period_days': days,
            'total_price_entries': len(prices),
            'avg_price_per_g': round(avg_price, 2),
            'min_price_per_g': round(min_price, 2),
            'max_price_per_g': round(max_price, 2),
            'volatility': round(volatility, 2),
            'volatility_pct': round((volatility / avg_price) * 100, 2),
            'price_trend': trend,
            'product_type_distribution': type_counts
        }

    def get_product_type_breakdown(self, metal_type: str) -> Dict:
        """
        Get breakdown of products by type.

        Args:
            metal_type: 'gold' or 'silver'

        Returns:
            Dict with counts by product type
        """
        return self.db.get_statistics(metal_type)

    def generate_report(
        self,
        metal_type: str,
        days: int = 30,
        top_n: int = 10
    ) -> str:
        """
        Generate a formatted market analysis report.

        Args:
            metal_type: 'gold' or 'silver'
            days: Number of days to analyze
            top_n: Number of top products to show

        Returns:
            Formatted report string
        """
        logger.info("Generating %s report for last %d days...", metal_type, days)

        # Get statistics
        stats = self.get_price_statistics(metal_type, days)
        top_products = self.get_top_products(metal_type, top_n, days)
        type_breakdown = self.get_product_type_breakdown(metal_type)

        # Build report
        report_lines = [
            f"{'=' * 70}",
            f"{metal_type.upper()} MARKET ANALYSIS REPORT",
            f"Period: Last {days} days",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'=' * 70}",
            "",
            "📊 MARKET STATISTICS",
            f"  Total price entries: {stats.get('total_price_entries', 0):,}",
            f"  Average price/g: €{stats.get('avg_price_per_g', 0):.2f}",
            f"  Min price/g: €{stats.get('min_price_per_g', 0):.2f}",
            f"  Max price/g: €{stats.get('max_price_per_g', 0):.2f}",
            f"  Volatility: €{stats.get('volatility', 0):.2f} ({stats.get('volatility_pct', 0):.1f}%)",
            f"  Price trend: {stats.get('price_trend', 'unknown')}",
            "",
            "📦 PRODUCT TYPE DISTRIBUTION",
            f"  Total products: {type_breakdown.get('total_products', 0)}",
            f"  Bars: {type_breakdown.get('bars', 0)}",
            f"  Coins: {type_breakdown.get('coins', 0)}",
            f"  Unknown: {type_breakdown.get('unknown', 0)}",
            "",
            f"🏆 TOP {top_n} BEST PRICES (per gram of fine metal)",
            ""
        ]

        for i, product in enumerate(top_products, 1):
            report_lines.extend([
                f"{i}. {product['product_name']}",
                f"   Price/g: €{product['price_per_g_fine_eur']:.2f} | "
                f"Sell: €{product['sell_price_eur']:.2f} | "
                f"Buy: €{product['buy_price_eur']:.2f}",
                f"   Type: {product['product_type']} | "
                f"Weight: {product.get('total_weight_g', 0):.2f}g",
                ""
            ])

        report_lines.append(f"{'=' * 70}")

        return "\n".join(report_lines)

    def close(self) -> None:
        """Close database connection."""
        self.db.close()


def main():
    """Main entry point for statistics generation."""
    parser = argparse.ArgumentParser(
        description='Generate market statistics from igold scraper database'
    )
    parser.add_argument(
        '--metal',
        choices=['gold', 'silver', 'both'],
        default='both',
        help='Metal type to analyze (default: both)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to analyze (default: 30)'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=10,
        help='Number of top products to show (default: 10)'
    )
    parser.add_argument(
        '--db',
        default=DEFAULT_DB_PATH,
        help=f'Path to database file (default: {DEFAULT_DB_PATH})'
    )

    args = parser.parse_args()

    generator = StatisticsGenerator(args.db)

    try:
        metals = ['gold', 'silver'] if args.metal == 'both' else [args.metal]

        for metal in metals:
            report = generator.generate_report(metal, args.days, args.top)
            print(report)
            print()  # Extra line between reports

    finally:
        generator.close()


if __name__ == '__main__':
    main()
