#!/usr/bin/env python3
"""
Daily Precious Metals Market Report Generator
Generates daily reports comparing today's top products vs yesterday using database
"""

import argparse
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import requests

from igold_scraper.services.database_manager import DatabaseManager
from igold_scraper.config import DEFAULT_DB_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", handlers=[logging.StreamHandler()]
)
logger = logging.getLogger()


class DailyReportGenerator:
    """Generates daily precious metals market reports from database and sends Discord notifications."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Initialize report generator.

        Args:
            db_path: Path to SQLite database
        """
        self.db = DatabaseManager(db_path)
        self.data_dir = Path("data")
        self.stats_dir = self.data_dir / "statistics"
        self.stats_dir.mkdir(parents=True, exist_ok=True)

    def get_day_boundaries(self, date: datetime) -> tuple[int, int]:
        """
        Get start and end timestamps for a calendar day.

        Args:
            date: Date to get boundaries for

        Returns:
            Tuple of (start_timestamp, end_timestamp)
        """
        day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
        return int(day_start.timestamp()), int(day_end.timestamp())

    def get_top_products(
        self, metal_type: str, timestamp_start: int, timestamp_end: int, top_n: int = 10
    ) -> List[Dict]:
        """
        Get top N products with best price per fine gram within time range.

        Args:
            metal_type: 'gold' or 'silver'
            timestamp_start: Start timestamp (Unix epoch)
            timestamp_end: End timestamp (Unix epoch)
            top_n: Number of top products to return

        Returns:
            List of product dicts with latest prices in range
        """
        cursor = self.db.conn.execute(
            """
            WITH RankedPrices AS (
                SELECT
                    p.id,
                    p.product_name,
                    p.product_type,
                    p.total_weight_g,
                    p.purity_per_mille,
                    p.url,
                    ph.sell_price_eur,
                    ph.buy_price_eur,
                    (p.total_weight_g * p.purity_per_mille / 1000.0) as fine_metal_g,
                    (ph.sell_price_eur / (p.total_weight_g * p.purity_per_mille / 1000.0)) as price_per_g_fine_eur,
                    ph.timestamp,
                    ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY ph.timestamp DESC) as rn
                FROM products p
                JOIN price_history ph ON p.id = ph.product_id
                WHERE p.metal_type = ?
                AND ph.timestamp >= ?
                AND ph.timestamp < ?
                AND ph.sell_price_eur > 0
            )
            SELECT
                id,
                product_name,
                product_type,
                total_weight_g,
                url,
                sell_price_eur,
                buy_price_eur,
                price_per_g_fine_eur
            FROM RankedPrices
            WHERE rn = 1
            ORDER BY price_per_g_fine_eur ASC
            LIMIT ?
        """,
            (metal_type, timestamp_start, timestamp_end, top_n),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_affordable_deals(self, metal_type: str, timestamp: int, price_limit: float, top_n: int = 10) -> List[Dict]:
        """
        Get affordable products under price limit.

        Args:
            metal_type: 'gold' or 'silver'
            timestamp: Unix timestamp for latest prices
            price_limit: Maximum price in EUR
            top_n: Number of products to return

        Returns:
            List of affordable products sorted by price per gram
        """
        # Get latest prices before timestamp
        day_start = timestamp - 86400  # 24 hours before

        cursor = self.db.conn.execute(
            """
            WITH RankedPrices AS (
                SELECT
                    p.id,
                    p.product_name,
                    p.product_type,
                    p.total_weight_g,
                    p.purity_per_mille,
                    ph.sell_price_eur,
                    ph.buy_price_eur,
                    (ph.sell_price_eur / (p.total_weight_g * p.purity_per_mille / 1000.0)) as price_per_g_fine_eur,
                    ph.timestamp,
                    ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY ph.timestamp DESC) as rn
                FROM products p
                JOIN price_history ph ON p.id = ph.product_id
                WHERE p.metal_type = ?
                AND ph.timestamp >= ?
                AND ph.timestamp <= ?
                AND ph.sell_price_eur > 0
                AND ph.sell_price_eur < ?
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
        """,
            (metal_type, day_start, timestamp, price_limit, top_n),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_product_count(self, metal_type: str, timestamp_start: int, timestamp_end: int) -> int:
        """Get count of unique products with prices in time range."""
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(DISTINCT p.id)
            FROM products p
            JOIN price_history ph ON p.id = ph.product_id
            WHERE p.metal_type = ?
            AND ph.timestamp >= ?
            AND ph.timestamp <= ?
        """,
            (metal_type, timestamp_start, timestamp_end),
        )
        return cursor.fetchone()[0]

    def get_market_statistics(self, metal_type: str, timestamp_start: int, timestamp_end: int) -> Dict:
        """
        Get comprehensive market statistics for a period.

        Returns: Dict with avg, min, max, median price per gram
        """
        cursor = self.db.conn.execute(
            """
            WITH LatestPrices AS (
                SELECT
                    p.id,
                    (ph.sell_price_eur / (p.total_weight_g * p.purity_per_mille / 1000.0)) as price_per_g_fine_eur,
                    ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY ph.timestamp DESC) as rn
                FROM products p
                JOIN price_history ph ON p.id = ph.product_id
                WHERE p.metal_type = ?
                AND ph.timestamp >= ?
                AND ph.timestamp <= ?
                AND ph.sell_price_eur > 0
            )
            SELECT
                AVG(price_per_g_fine_eur) as avg_price,
                MIN(price_per_g_fine_eur) as min_price,
                MAX(price_per_g_fine_eur) as max_price,
                COUNT(*) as product_count
            FROM LatestPrices
            WHERE rn = 1
        """,
            (metal_type, timestamp_start, timestamp_end),
        )

        row = cursor.fetchone()
        return {
            "avg": round(row["avg_price"], 2) if row["avg_price"] else 0,
            "min": round(row["min_price"], 2) if row["min_price"] else 0,
            "max": round(row["max_price"], 2) if row["max_price"] else 0,
            "count": row["product_count"],
        }

    def get_price_movers(
        self,
        metal_type: str,
        today_start: int,
        today_end: int,
        yesterday_start: int,
        yesterday_end: int,
        limit: int = 5,
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Get products with biggest price changes (increases and decreases).

        Returns: Tuple of (increases, decreases) - each a list of dicts
        """
        cursor = self.db.conn.execute(
            """
            WITH TodayPrices AS (
                SELECT
                    p.id,
                    p.product_name,
                    p.url,
                    (ph.sell_price_eur / (p.total_weight_g * p.purity_per_mille / 1000.0)) as today_price,
                    ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY ph.timestamp DESC) as rn
                FROM products p
                JOIN price_history ph ON p.id = ph.product_id
                WHERE p.metal_type = ?
                AND ph.timestamp >= ? AND ph.timestamp <= ?
                AND ph.sell_price_eur > 0
            ),
            YesterdayPrices AS (
                SELECT
                    p.id,
                    (ph.sell_price_eur / (p.total_weight_g * p.purity_per_mille / 1000.0)) as yesterday_price,
                    ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY ph.timestamp DESC) as rn
                FROM products p
                JOIN price_history ph ON p.id = ph.product_id
                WHERE p.metal_type = ?
                AND ph.timestamp >= ? AND ph.timestamp <= ?
                AND ph.sell_price_eur > 0
            )
            SELECT
                t.id,
                t.product_name,
                t.url,
                t.today_price,
                y.yesterday_price,
                ((t.today_price - y.yesterday_price) / y.yesterday_price * 100) as change_pct
            FROM TodayPrices t
            JOIN YesterdayPrices y ON t.id = y.id
            WHERE t.rn = 1 AND y.rn = 1
            AND y.yesterday_price > 0
            ORDER BY change_pct DESC
        """,
            (metal_type, today_start, today_end, metal_type, yesterday_start, yesterday_end),
        )

        all_movers = [dict(row) for row in cursor.fetchall()]

        # Split into increases (positive) and decreases (negative)
        increases = [m for m in all_movers if m["change_pct"] > 0][:limit]
        decreases = [m for m in all_movers if m["change_pct"] < 0][-limit:]  # Take last N (most negative)
        decreases.reverse()  # Show biggest decrease first

        return increases, decreases

    def get_new_products(
        self, metal_type: str, today_start: int, today_end: int, yesterday_start: int, yesterday_end: int
    ) -> List[Dict]:
        """Get products that have prices today but not yesterday."""
        cursor = self.db.conn.execute(
            """
            SELECT DISTINCT
                p.id,
                p.product_name,
                p.url,
                (ph.sell_price_eur / (p.total_weight_g * p.purity_per_mille / 1000.0)) as price_per_g_fine_eur,
                ph.sell_price_eur
            FROM products p
            JOIN price_history ph ON p.id = ph.product_id
            WHERE p.metal_type = ?
            AND ph.timestamp >= ? AND ph.timestamp <= ?
            AND p.id NOT IN (
                SELECT DISTINCT ph2.product_id
                FROM price_history ph2
                WHERE ph2.timestamp >= ? AND ph2.timestamp <= ?
            )
            ORDER BY price_per_g_fine_eur ASC
            LIMIT 10
        """,
            (metal_type, today_start, today_end, yesterday_start, yesterday_end),
        )

        return [dict(row) for row in cursor.fetchall()]

    def load_data(self, metal_type: str, date: datetime) -> Optional[Dict]:
        """
        Load product data for a specific date from database.

        Args:
            metal_type: 'gold' or 'silver'
            date: Date to load data for

        Returns:
            Dict with products and metadata, or None if no data
        """
        # Get timestamp range for the day
        day_start = int(date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        day_end = int(date.replace(hour=23, minute=59, second=59, microsecond=999999).timestamp())

        # Check if we have data for this day
        cursor = self.db.conn.execute(
            """
            SELECT COUNT(*)
            FROM price_history ph
            JOIN products p ON ph.product_id = p.id
            WHERE p.metal_type = ?
            AND ph.timestamp >= ?
            AND ph.timestamp < ?
        """,
            (metal_type, day_start, day_end),
        )

        count = cursor.fetchone()[0]
        if count == 0:
            return None

        # Get all products with their latest price for the day
        products = self.get_top_products(metal_type, day_start, day_end, top_n=1000)

        return {
            "date": date.strftime("%Y-%m-%d"),
            "scrape_time": date.isoformat(),
            "source": "database",
            "product_type": metal_type,
            "products": products,
        }

    def load_live_price(self, metal_type: str, date: datetime) -> Optional[float]:
        """Load live price for a specific date"""
        date_str = date.strftime("%Y-%m-%d")
        file_path = self.data_dir / "live_prices" / metal_type / f"{date_str}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Handle both array and object formats
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]  # Take first entry if it's an array
                if isinstance(data, dict):
                    return data.get("price_eur_per_g")
                return None
        except (OSError, json.JSONDecodeError) as e:
            logger.exception("Error loading live price from %s: %s", file_path, e)
            return None

    def calculate_daily_statistics(
        self,
        today: datetime,
        yesterday: datetime,
        today_live_price: Optional[float],
        yesterday_live_price: Optional[float],
        metal_type: str = "gold",
    ) -> Dict:
        """
        Calculate comprehensive daily market statistics.

        Args:
            today: Today's date
            yesterday: Yesterday's date
            today_live_price: Live metal price today (per gram)
            yesterday_live_price: Live metal price yesterday (per gram)
            metal_type: 'gold' or 'silver'

        Returns:
            Dict with comprehensive statistics
        """
        # Get calendar day boundaries
        today_start, today_end = self.get_day_boundaries(today)
        yesterday_start, yesterday_end = self.get_day_boundaries(yesterday)
        week_ago_start, week_ago_end = self.get_day_boundaries(today - timedelta(days=7))

        # Get comprehensive market statistics
        today_stats = self.get_market_statistics(metal_type, today_start, today_end)
        yesterday_stats = self.get_market_statistics(metal_type, yesterday_start, yesterday_end)
        week_ago_stats = self.get_market_statistics(metal_type, week_ago_start, week_ago_end)

        # Get top 5 products for today
        today_top_5 = self.get_top_products(metal_type, today_start, today_end, top_n=5)

        # Product type breakdown for top 5
        bars_count = sum(1 for p in today_top_5 if p.get("product_type") == "bar")
        coins_count = sum(1 for p in today_top_5 if p.get("product_type") == "coin")

        # Calculate price changes
        price_change_pct = 0
        week_price_change_pct = 0
        trend = "stable"

        if yesterday_stats["avg"] > 0:
            price_change_pct = (today_stats["avg"] - yesterday_stats["avg"]) / yesterday_stats["avg"] * 100

            # Determine trend
            if abs(price_change_pct) < 1.0:
                trend = "stable"
            elif price_change_pct > 0:
                trend = "increasing"
            else:
                trend = "decreasing"

        if week_ago_stats["avg"] > 0:
            week_price_change_pct = (today_stats["avg"] - week_ago_stats["avg"]) / week_ago_stats["avg"] * 100

        # Get product counts
        total_products_today = self.get_product_count(metal_type, today_start, today_end)
        total_products_yesterday = self.get_product_count(metal_type, yesterday_start, yesterday_end)

        # Get new products
        new_products = self.get_new_products(metal_type, today_start, today_end, yesterday_start, yesterday_end)

        # Get price movers
        price_increases, price_decreases = self.get_price_movers(
            metal_type, today_start, today_end, yesterday_start, yesterday_end, limit=5
        )

        # Live price comparison
        live_price_change_pct = 0
        if today_live_price and yesterday_live_price:
            live_price_change_pct = (today_live_price - yesterday_live_price) / yesterday_live_price * 100

        # Get affordable deals
        price_limit = 2500 if metal_type == "gold" else 1000
        affordable_products = self.get_affordable_deals(metal_type, today_end, price_limit, top_n=10)

        return {
            "today_date": today.strftime("%Y-%m-%d"),
            "yesterday_date": yesterday.strftime("%Y-%m-%d"),
            # Market statistics
            "market_avg_price": today_stats["avg"],
            "market_min_price": today_stats["min"],
            "market_max_price": today_stats["max"],
            "yesterday_avg_price": yesterday_stats["avg"],
            "week_ago_avg_price": week_ago_stats["avg"],
            # Price changes
            "price_change_pct": round(price_change_pct, 2),
            "week_price_change_pct": round(week_price_change_pct, 2),
            "trend": trend,
            # Product information
            "total_products_today": total_products_today,
            "total_products_yesterday": total_products_yesterday,
            "new_products_count": len(new_products),
            "new_products": new_products,
            # Top deals
            "best_deals": today_top_5,
            "product_types_top5": {"bars": bars_count, "coins": coins_count},
            "affordable_deals": affordable_products,
            # Price movers
            "price_increases": price_increases,
            "price_decreases": price_decreases,
            # Live prices
            "live_price_today": today_live_price,
            "live_price_yesterday": yesterday_live_price,
            "live_price_change_pct": (
                round(live_price_change_pct, 2) if today_live_price and yesterday_live_price else None
            ),
        }

    def format_discord_message(self, stats: Dict, metal_type: str) -> Dict:
        """Format statistics as Discord embed message."""

        metal_emoji = "💰" if metal_type == "gold" else "🪙"
        metal_name = metal_type.capitalize()

        # Trend emoji
        trend_emoji = {"increasing": "📈", "decreasing": "📉", "stable": "➡️"}.get(stats["trend"], "➡️")

        # Price change emoji
        if stats["price_change_pct"] > 1:
            change_emoji = "📈"
        elif stats["price_change_pct"] < -1:
            change_emoji = "📉"
        else:
            change_emoji = "➡️"

        # Build best deals list (top 5)
        best_deals_text = ""
        for i, product in enumerate(stats["best_deals"][:5], 1):
            name = product["product_name"][:50]
            price_per_g = product["price_per_g_fine_eur"]
            sell_price = product.get("sell_price_eur", 0)

            deal_line = f"{i}. **{name}**\n   {price_per_g:.2f} €/g | Total: {sell_price:.0f} €"
            best_deals_text += deal_line + "\n"

        # Build affordable deals
        affordable_text = ""
        if "affordable_deals" in stats and stats["affordable_deals"]:
            for i, product in enumerate(stats["affordable_deals"][:5], 1):
                name = product["product_name"][:50]
                price_per_g = product["price_per_g_fine_eur"]
                sell_price = product.get("sell_price_eur", 0)

                deal_line = f"{i}. **{name}**\n   {price_per_g:.2f} €/g | {sell_price:.0f} €"
                affordable_text += deal_line + "\n"

        # Build price movers (biggest decreases - good for buyers!)
        price_drops_text = ""
        if stats.get("price_decreases"):
            for i, mover in enumerate(stats["price_decreases"][:5], 1):
                name = mover["product_name"][:50]
                change = mover["change_pct"]
                today_price = mover["today_price"]

                drop_line = f"{i}. **{name}**\n   {change:.1f}% drop → {today_price:.2f} €/g"
                price_drops_text += drop_line + "\n"

        # Build embed fields
        fields = [
            {
                "name": "📊 Market Overview",
                "value": (
                    f"Average: {stats['market_avg_price']:.2f} €/g\n"
                    f"Range: {stats['market_min_price']:.2f} - {stats['market_max_price']:.2f} €/g\n"
                    f"Products: {stats['total_products_today']}"
                ),
                "inline": True,
            },
            {
                "name": "📈 Price Changes",
                "value": (
                    f"24h: {change_emoji} {stats['price_change_pct']:+.2f}%\n"
                    f"7d: {stats['week_price_change_pct']:+.2f}%\n"
                    f"Trend: {trend_emoji} {stats['trend'].capitalize()}"
                ),
                "inline": True,
            },
        ]

        # Add live price if available
        if stats.get("live_price_today"):
            live_change = stats.get("live_price_change_pct", 0)
            live_emoji = "📈" if live_change > 0 else "📉" if live_change < 0 else "➡️"
            fields.append(
                {
                    "name": "🌍 Live Spot Price",
                    "value": (f"{stats['live_price_today']:.2f} €/g\n" f"Change: {live_emoji} {live_change:+.2f}%"),
                    "inline": True,
                }
            )

        # Add new products if any
        if stats["new_products_count"] > 0:
            new_text = f"{stats['new_products_count']} new product(s) today"
            if stats.get("new_products"):
                new_text += "\n" + "\n".join([f"• {p['product_name'][:40]}" for p in stats["new_products"][:3]])
            fields.append({"name": "🆕 New Listings", "value": new_text, "inline": False})

        # Best deals
        if best_deals_text:
            fields.append(
                {
                    "name": f"{metal_emoji} Top 5 Best Prices (per gram)",
                    "value": best_deals_text or "No data available",
                    "inline": False,
                }
            )

        # Price drops (best opportunities)
        if price_drops_text:
            fields.append(
                {"name": "🎯 Biggest Price Drops (Buy Opportunities)", "value": price_drops_text, "inline": False}
            )

        # Affordable deals
        if affordable_text:
            price_limit_str = "€2500" if metal_type == "gold" else "€1000"
            fields.append(
                {"name": f"💰 Affordable Deals (Under {price_limit_str})", "value": affordable_text, "inline": False}
            )

        # Color based on trend
        color = {
            "increasing": 0xFF4444,  # Red
            "decreasing": 0x44FF44,  # Green (good for buyers)
            "stable": 0xFFAA00,  # Orange
        }.get(stats["trend"], 0xFFAA00)

        embed = {
            "embeds": [
                {
                    "title": f"📊 Daily {metal_name} Market Report",
                    "description": f"Top 5 products comparison: {stats['today_date']}",
                    "color": color,
                    "fields": fields,
                    "footer": {"text": "Tracking top 5 products by price per gram • Data from igold.bg"},
                    "timestamp": datetime.now().isoformat(),
                }
            ]
        }

        return embed

    def send_discord_notification(self, message: Dict) -> bool:
        """Send notification to Discord webhook"""
        webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if not webhook_url:
            logger.warning("DISCORD_WEBHOOK_URL not set, skipping Discord notification")
            return False

        try:
            response = requests.post(webhook_url, json=message, timeout=10)
            response.raise_for_status()
            logger.info("Successfully sent Discord notification")
            return True
        except requests.RequestException as e:
            logger.error("Failed to send Discord notification: %s", e)
            return False

    def generate_daily_reports(self):
        """Generate and send daily reports for all metals."""
        today = datetime.now()
        yesterday = today - timedelta(days=1)

        for metal_type in ["gold", "silver"]:
            logger.info("Generating daily %s report...", metal_type)

            # Check if we have data for today
            today_start, today_end = self.get_day_boundaries(today)
            product_count = self.get_product_count(metal_type, today_start, today_end)

            if product_count == 0:
                today_str = today.strftime("%Y-%m-%d")
                logger.warning("No %s data found for today (%s)", metal_type, today_str)
                continue

            # Load live prices
            today_live_price = self.load_live_price(metal_type, today)
            yesterday_live_price = self.load_live_price(metal_type, yesterday)

            # Calculate statistics from database
            stats = self.calculate_daily_statistics(
                today, yesterday, today_live_price, yesterday_live_price, metal_type
            )

            # Save report
            report = {
                "report_type": "daily",
                "metal_type": metal_type,
                "report_date": today.strftime("%Y-%m-%d"),
                "statistics": stats,
            }

            report_file = self.stats_dir / f"{metal_type}_daily_{today.strftime('%Y-%m-%d')}.json"
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            logger.info("Saved daily %s report to %s", metal_type, report_file)

            # Send Discord notification
            discord_message = self.format_discord_message(stats, metal_type)
            self.send_discord_notification(discord_message)

        logger.info("Daily reports generation completed")

    def close(self) -> None:
        """Close database connection."""
        self.db.close()


def main():
    """Generate and send daily reports for all precious metals."""
    parser = argparse.ArgumentParser(description="Generate daily market reports from database")
    parser.add_argument(
        "--db",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})"
    )

    args = parser.parse_args()

    generator = DailyReportGenerator(args.db)
    try:
        generator.generate_daily_reports()
    finally:
        generator.close()


if __name__ == "__main__":
    main()
