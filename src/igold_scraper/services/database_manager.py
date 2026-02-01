#!/usr/bin/env python3
"""
Database manager for igold scraper using SQLite.
Manages product metadata and price history in a relational database.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import logging

from igold_scraper.scrapers.base import Product
from igold_scraper.config import DEFAULT_DB_PATH

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages product data in SQLite database."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Initialize database connection and create tables.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Access columns by name
        self._create_tables()
        self._create_indexes()

    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                product_name TEXT NOT NULL,
                metal_type TEXT NOT NULL CHECK(metal_type IN ('gold', 'silver')),
                product_type TEXT NOT NULL CHECK(product_type IN ('bar', 'coin', 'unknown')),
                total_weight_g REAL NOT NULL,
                purity_per_mille REAL NOT NULL,
                UNIQUE(product_name, metal_type)
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                sell_price_eur REAL NOT NULL,
                buy_price_eur REAL NOT NULL,
                UNIQUE(product_id, timestamp),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    def _create_indexes(self) -> None:
        """Create indexes for faster queries."""
        self.conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_products_url ON products(url);
            CREATE INDEX IF NOT EXISTS idx_products_metal ON products(metal_type);
            CREATE INDEX IF NOT EXISTS idx_products_type ON products(product_type);
            CREATE INDEX IF NOT EXISTS idx_price_timestamp ON price_history(timestamp);
            CREATE INDEX IF NOT EXISTS idx_price_product_time ON price_history(product_id, timestamp DESC);
        """)
        self.conn.commit()

    def product_exists(self, url: str) -> bool:
        """
        Check if product exists in database.

        Args:
            url: Product URL

        Returns:
            True if product exists
        """
        cursor = self.conn.execute("SELECT 1 FROM products WHERE url = ? LIMIT 1", (url,))
        return cursor.fetchone() is not None

    def save_product(self, product: Product) -> bool:
        """
        Save or update product metadata.

        Args:
            product: Product instance

        Returns:
            True if successful
        """
        try:
            # Insert or update product
            self.conn.execute("""
                INSERT INTO products (
                    url, product_name, metal_type, product_type,
                    total_weight_g, purity_per_mille
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_name, metal_type) DO UPDATE SET
                    url = excluded.url,
                    product_type = excluded.product_type,
                    total_weight_g = excluded.total_weight_g,
                    purity_per_mille = excluded.purity_per_mille
            """, (
                product.url,
                product.name,
                product.metal_type,
                product.product_type,
                product.weight,
                product.purity
            ))

            self.conn.commit()
            return True

        except sqlite3.Error as e:
            logger.error("Failed to save product %s: %s", product.url, e)
            self.conn.rollback()
            return False

    def add_price_entry(
        self,
        url: str,
        sell_price_eur: Optional[float] = None,
        buy_price_eur: Optional[float] = None,
        timestamp: Optional[int] = None
    ) -> bool:
        """
        Add price entry to product history.

        Args:
            url: Product URL
            sell_price_eur: Selling price
            buy_price_eur: Buying price
            timestamp: Optional Unix timestamp (defaults to now)

        Returns:
            True if successful
        """
        # Validate prices
        if sell_price_eur is None or sell_price_eur <= 0:
            logger.warning("Invalid sell price for %s: %s", url, sell_price_eur)
            return False

        if buy_price_eur is None or buy_price_eur < 0:
            logger.warning("Invalid buy price for %s: %s", url, buy_price_eur)
            return False

        try:
            # Get product ID
            cursor = self.conn.execute(
                "SELECT id FROM products WHERE url = ?",
                (url,)
            )
            row = cursor.fetchone()

            if not row:
                logger.warning("Product %s not found, cannot add price", url)
                return False

            product_id = row['id']

            if timestamp is None:
                timestamp = int(datetime.now().timestamp())

            # Insert price entry (UNIQUE constraint prevents duplicates)
            try:
                self.conn.execute("""
                    INSERT INTO price_history (
                        product_id, timestamp, sell_price_eur, buy_price_eur
                    ) VALUES (?, ?, ?, ?)
                """, (product_id, timestamp, sell_price_eur, buy_price_eur))
            except sqlite3.IntegrityError:
                # Duplicate entry - update instead
                self.conn.execute("""
                    UPDATE price_history
                    SET sell_price_eur = ?, buy_price_eur = ?
                    WHERE product_id = ? AND timestamp = ?
                """, (sell_price_eur, buy_price_eur, product_id, timestamp))

            self.conn.commit()
            return True

        except sqlite3.Error as e:
            logger.exception("Failed to add price for %s: %s", url, e)
            self.conn.rollback()
            return False

    def get_all_products(self, metal_type: str) -> List[Dict]:
        """
        Load all products for a metal type.

        Args:
            metal_type: Metal type (gold/silver)

        Returns:
            List of product data dicts
        """
        cursor = self.conn.execute("""
            SELECT
                url,
                product_name,
                metal_type,
                product_type,
                total_weight_g,
                purity_per_mille
            FROM products
            WHERE metal_type = ?
            ORDER BY product_name
        """, (metal_type,))

        return [dict(row) for row in cursor.fetchall()]

    def get_latest_prices(self, metal_type: str) -> List[Dict]:
        """
        Get latest prices for all products of a metal type.

        Args:
            metal_type: 'gold' or 'silver'

        Returns:
            List of dicts with product info and latest price
        """
        cursor = self.conn.execute("""
            SELECT
                p.url,
                p.product_name,
                p.metal_type,
                p.product_type,
                p.total_weight_g,
                p.purity_per_mille,
                (p.total_weight_g * p.purity_per_mille / 1000.0) as fine_metal_g,
                ph.sell_price_eur,
                ph.buy_price_eur,
                CASE 
                    WHEN ph.sell_price_eur > 0 THEN (ph.sell_price_eur / (p.total_weight_g * p.purity_per_mille / 1000.0))
                    ELSE NULL
                END as price_per_g_fine_eur,
                CASE
                    WHEN ph.sell_price_eur > 0 THEN ROUND((ph.sell_price_eur - ph.buy_price_eur) / ph.sell_price_eur * 100, 2)
                    ELSE NULL
                END as spread_percentage
            FROM products p
            LEFT JOIN price_history ph ON p.id = ph.product_id
            WHERE p.metal_type = ?
                AND ph.id = (
                    SELECT id FROM price_history
                    WHERE product_id = p.id
                    ORDER BY timestamp DESC
                    LIMIT 1
                )
            ORDER BY price_per_g_fine_eur ASC
        """, (metal_type,))

        return [dict(row) for row in cursor.fetchall()]

    def get_price_history(
        self,
        url: str,
        days: Optional[int] = None
    ) -> List[Dict]:
        """
        Get price history for a product.

        Args:
            url: Product URL
            days: Optional number of days to retrieve

        Returns:
            List of price entries ordered by timestamp descending
        """
        query = """
            SELECT
                ph.timestamp,
                ph.sell_price_eur,
                ph.buy_price_eur,
                (ph.sell_price_eur / (p.total_weight_g * p.purity_per_mille / 1000.0)) as price_per_g_fine_eur
            FROM price_history ph
            JOIN products p ON ph.product_id = p.id
            WHERE p.url = ?
        """

        params: Tuple = (url,)

        if days:
            query += " AND datetime(ph.timestamp) >= datetime('now', '-' || ? || ' days')"
            params = (url, days)

        query += " ORDER BY ph.timestamp DESC"

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self, metal_type: str) -> Dict:
        """
        Get statistics for a metal type.

        Args:
            metal_type: 'gold' or 'silver'

        Returns:
            Dict with counts of products by type
        """
        cursor = self.conn.execute("""
            SELECT
                COUNT(*) as total_products,
                COUNT(CASE WHEN product_type = 'bar' THEN 1 END) as bars,
                COUNT(CASE WHEN product_type = 'coin' THEN 1 END) as coins,
                COUNT(CASE WHEN product_type = 'unknown' THEN 1 END) as unknown
            FROM products
            WHERE metal_type = ?
        """, (metal_type,))

        return dict(cursor.fetchone())

    def add_price_entries_batch(
        self,
        entries: List[Dict[str, Any]]
    ) -> int:
        """
        Add multiple price entries in a single transaction.
        Much faster than individual inserts for bulk operations.

        Args:
            entries: List of dicts with keys: url, sell_price_eur, buy_price_eur, timestamp (optional)

        Returns:
            Number of entries successfully added

        Example:
            entries = [
                {'url': '/product-1', 'sell_price_eur': 100.0, 'buy_price_eur': 95.0},
                {'url': '/product-2', 'sell_price_eur': 200.0, 'buy_price_eur': 190.0},
            ]
            count = db.add_price_entries_batch(entries)
        """
        if not entries:
            return 0

        current_timestamp = int(datetime.now().timestamp())
        added_count = 0

        try:
            # Get all product IDs and fine_metal_g in one query
            urls = [e['url'] for e in entries]
            placeholders = ','.join('?' * len(urls))
            cursor = self.conn.execute(
                f"SELECT url, id, fine_metal_g FROM products WHERE url IN ({placeholders})",
                urls
            )
            product_lookup = {row['url']: (row['id'], row['fine_metal_g']) for row in cursor}

            # Prepare batch insert data
            batch_data = []
            update_timestamps = []

            for entry in entries:
                url = entry['url']
                if url not in product_lookup:
                    logger.warning("Product %s not found, skipping", url)
                    continue

                sell_price = entry['sell_price_eur']
                buy_price = entry['buy_price_eur']

                # Validate prices
                if sell_price is None or sell_price <= 0 or buy_price is None or buy_price < 0:
                    logger.warning("Invalid prices for %s, skipping", url)
                    continue

                product_id, fine_metal_g = product_lookup[url]
                timestamp = entry.get('timestamp', current_timestamp)

                # Calculate price per gram
                price_per_g = None
                if fine_metal_g and fine_metal_g > 0:
                    price_per_g = round(sell_price / fine_metal_g, 2)

                batch_data.append((product_id, timestamp, sell_price, buy_price, price_per_g))
                update_timestamps.append((timestamp, product_id))

            # Execute batch insert
            if batch_data:
                self.conn.executemany("""
                    INSERT OR IGNORE INTO price_history
                    (product_id, timestamp, sell_price_eur, buy_price_eur)
                    VALUES (?, ?, ?, ?)
                """, batch_data)

                self.conn.commit()
                added_count = len(batch_data)
                logger.info("Added %d price entries in batch", added_count)

            return added_count

        except sqlite3.Error as e:
            logger.exception("Batch insert failed: %s", e)
            self.conn.rollback()
            return 0

    def vacuum(self) -> None:
        """Optimize database by reclaiming unused space."""
        try:
            self.conn.execute("VACUUM")
            self.conn.commit()
            logger.info("Database vacuumed successfully")
        except sqlite3.Error as e:
            logger.exception("Failed to vacuum database: %s", e)

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self) -> 'DatabaseManager':
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ) -> None:
        """Context manager exit."""
        self.close()

    def __del__(self):
        """Destructor to ensure connection is closed."""
        self.close()
