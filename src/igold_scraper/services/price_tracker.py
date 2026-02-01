#!/usr/bin/env python3
"""
Price change tracker using SQLite database.
Tracks price changes and can notify about significant changes.
"""

import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from igold_scraper.services.database_manager import DatabaseManager
from igold_scraper.config import (
    DEFAULT_DB_PATH,
    DEFAULT_PRICE_CHANGE_THRESHOLD,
)
from igold_scraper.constants import (
    METAL_TYPE_GOLD,
    METAL_TYPE_SILVER,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PriceTracker:
    """Tracks precious metals price changes using database."""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        threshold: float = DEFAULT_PRICE_CHANGE_THRESHOLD
    ):
        """
        Initialize price tracker.

        Args:
            db_path: Path to SQLite database
            threshold: Percentage change threshold for notifications (default: 5%)
        """
        self.db = DatabaseManager(db_path)
        self.threshold = threshold

    def get_price_changes(
        self,
        metal_type: str,
        hours: int = 24
    ) -> List[Dict]:
        """
        Get products with significant price changes in the last N hours.

        Args:
            metal_type: 'gold' or 'silver'
            hours: Number of hours to look back

        Returns:
            List of dicts with product info and price change percentage
        """
        cutoff = int((datetime.now() - timedelta(hours=hours)).timestamp())

        # Get products with multiple price entries in the period
        cursor = self.db.conn.execute("""
            WITH latest_prices AS (
                SELECT
                    ph.product_id,
                    ph.sell_price_eur as current_price,
                    ph.timestamp as current_timestamp,
                    ROW_NUMBER() OVER (PARTITION BY ph.product_id ORDER BY ph.timestamp DESC) as rn
                FROM price_history ph
                WHERE ph.timestamp >= ?
            ),
            earliest_prices AS (
                SELECT
                    ph.product_id,
                    ph.sell_price_eur as previous_price,
                    ph.timestamp as previous_timestamp,
                    ROW_NUMBER() OVER (PARTITION BY ph.product_id ORDER BY ph.timestamp ASC) as rn
                FROM price_history ph
                WHERE ph.timestamp >= ?
            )
            SELECT
                p.product_name,
                p.url,
                p.product_type,
                p.total_weight_g,
                p.purity_per_mille,
                lp.current_price,
                ROUND(lp.current_price / (p.total_weight_g * p.purity_per_mille / 1000.0), 4) as current_price_per_g,
                ep.previous_price,
                ROUND(ep.previous_price / (p.total_weight_g * p.purity_per_mille / 1000.0), 4) as previous_price_per_g,
                lp.current_timestamp,
                ep.previous_timestamp,
                ROUND(((lp.current_price - ep.previous_price) / ep.previous_price) * 100, 2) as change_pct,
                ROUND(((lp.current_price / (p.total_weight_g * p.purity_per_mille / 1000.0) - 
                        ep.previous_price / (p.total_weight_g * p.purity_per_mille / 1000.0)) / 
                       (ep.previous_price / (p.total_weight_g * p.purity_per_mille / 1000.0))) * 100, 2) as change_per_g_pct
            FROM products p
            JOIN latest_prices lp ON p.id = lp.product_id AND lp.rn = 1
            JOIN earliest_prices ep ON p.id = ep.product_id AND ep.rn = 1
            WHERE p.metal_type = ?
                AND lp.current_timestamp != ep.previous_timestamp
                AND ABS(((lp.current_price - ep.previous_price) / ep.previous_price) * 100) >= ?
            ORDER BY ABS(change_pct) DESC
        """, (cutoff, cutoff, metal_type, self.threshold))

        results = []
        for row in cursor.fetchall():
            results.append({
                'product_name': row['product_name'],
                'url': row['url'],
                'product_type': row['product_type'],
                'weight_g': row['total_weight_g'],
                'current_price': row['current_price'],
                'previous_price': row['previous_price'],
                'change_pct': row['change_pct'],
                'current_price_per_g': row['current_price_per_g'],
                'previous_price_per_g': row['previous_price_per_g'],
                'change_per_g_pct': row['change_per_g_pct'],
                'current_timestamp': row['current_timestamp'],
                'previous_timestamp': row['previous_timestamp']
            })

        return results

    def get_top_movers(
        self,
        metal_type: str,
        hours: int = 24,
        limit: int = 10
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Get top price increases and decreases.

        Args:
            metal_type: 'gold' or 'silver'
            hours: Number of hours to look back
            limit: Number of results per category

        Returns:
            Tuple of (increases, decreases) lists
        """
        changes = self.get_price_changes(metal_type, hours)

        increases = [c for c in changes if c['change_pct'] > 0]
        decreases = [c for c in changes if c['change_pct'] < 0]

        # Sort and limit
        increases.sort(key=lambda x: x['change_pct'], reverse=True)
        decreases.sort(key=lambda x: x['change_pct'])

        return increases[:limit], decreases[:limit]

    def generate_report(
        self,
        metal_type: str,
        hours: int = 24
    ) -> str:
        """
        Generate a price change report.

        Args:
            metal_type: 'gold' or 'silver'
            hours: Number of hours to analyze

        Returns:
            Formatted report string
        """
        logger.info("Generating price change report for %s (last %d hours)...", metal_type, hours)

        increases, decreases = self.get_top_movers(metal_type, hours, limit=10)

        report_lines = [
            f"{'=' * 70}",
            f"{metal_type.upper()} PRICE CHANGE REPORT",
            f"Period: Last {hours} hours",
            f"Threshold: ≥{self.threshold}% change",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"{'=' * 70}",
            ""
        ]

        if increases:
            report_lines.extend([
                "📈 TOP PRICE INCREASES",
                ""
            ])
            for i, item in enumerate(increases, 1):
                report_lines.extend([
                    f"{i}. {item['product_name']}",
                    f"   Price: €{item['previous_price']:.2f} → €{item['current_price']:.2f} "
                    f"({item['change_pct']:+.2f}%)",
                    f"   Per gram: €{item['previous_price_per_g']:.2f} → €{item['current_price_per_g']:.2f} "
                    f"({item['change_per_g_pct']:+.2f}%)",
                    ""
                ])
        else:
            report_lines.extend([
                "📈 NO SIGNIFICANT PRICE INCREASES",
                ""
            ])

        if decreases:
            report_lines.extend([
                "📉 TOP PRICE DECREASES",
                ""
            ])
            for i, item in enumerate(decreases, 1):
                report_lines.extend([
                    f"{i}. {item['product_name']}",
                    f"   Price: €{item['previous_price']:.2f} → €{item['current_price']:.2f} "
                    f"({item['change_pct']:+.2f}%)",
                    f"   Per gram: €{item['previous_price_per_g']:.2f} → €{item['current_price_per_g']:.2f} "
                    f"({item['change_per_g_pct']:+.2f}%)",
                    ""
                ])
        else:
            report_lines.extend([
                "📉 NO SIGNIFICANT PRICE DECREASES",
                ""
            ])

        report_lines.append(f"{'=' * 70}")

        return "\n".join(report_lines)

    def close(self) -> None:
        """Close database connection."""
        self.db.close()


def main():
    """Main entry point for price tracking."""
    parser = argparse.ArgumentParser(
        description='Track price changes from igold scraper database'
    )
    parser.add_argument(
        '--metal',
        choices=[METAL_TYPE_GOLD, METAL_TYPE_SILVER, 'both'],
        default='both',
        help='Metal type to track (default: both)'
    )
    parser.add_argument(
        '--hours',
        type=int,
        default=24,
        help='Number of hours to analyze (default: 24)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=5.0,
        help='Minimum percentage change to report (default: 5.0)'
    )
    parser.add_argument(
        '--db',
        default=DEFAULT_DB_PATH,
        help=f'Path to database file (default: {DEFAULT_DB_PATH})'
    )

    args = parser.parse_args()

    tracker = PriceTracker(args.db, args.threshold)

    try:
        metals = ['gold', 'silver'] if args.metal == 'both' else [args.metal]

        for metal in metals:
            report = tracker.generate_report(metal, args.hours)
            print(report)
            print()  # Extra line between reports

    finally:
        tracker.close()


if __name__ == '__main__':
    main()
