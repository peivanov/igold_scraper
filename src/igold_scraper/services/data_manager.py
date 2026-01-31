#!/usr/bin/env python3
"""
Data management utilities for igold scraper
Handles CSV to JSON conversion, data organization, and cleanup
"""

import os
import json
import csv
import glob
import argparse
from datetime import datetime, timedelta
import logging

from igold_scraper.config import DEFAULT_DATA_DIR
from igold_scraper.constants import (
    DATA_DIR_GOLD,
    DATA_DIR_SILVER,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def csv_to_json(csv_file):
    """Convert CSV file to JSON format"""
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            data = []
            for row in reader:
                # Convert numeric strings to appropriate types
                for key, value in row.items():
                    if value and value.replace('.', '').replace(',', '').replace('-', '').isdigit():
                        try:
                            if '.' in value or ',' in value:
                                row[key] = float(value.replace(',', '.'))
                            else:
                                row[key] = int(value)
                        except ValueError:
                            pass  # Keep as string if conversion fails
                data.append(row)
            return data
    except (OSError, ValueError, UnicodeDecodeError) as e:
        logger.exception("Error converting %s to JSON: %s", csv_file, e)
        return None

def organize_daily_data():
    """Organize CSV files into dated JSON files in appropriate directories"""
    today = datetime.now().strftime('%Y-%m-%d')

    # Find today's CSV files
    # Be specific to avoid matching silver CSV with gold pattern (igold_silver has "gold" in it)
    # Handle both regular and tavex-comparison CSV files
    gold_files = (
        glob.glob('igold_gold_products_sorted*.csv')
        + glob.glob('igold_tavex_gold_products_sorted*.csv')
    )
    silver_files = glob.glob('igold_silver_products_sorted*.csv')

    for csv_file in gold_files:
        if os.path.exists(csv_file):
            logger.info("Processing gold file: %s", csv_file)
            data = csv_to_json(csv_file)
            if data:
                output_file = f"{DEFAULT_DATA_DIR}/{DATA_DIR_GOLD}/{today}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'date': today,
                        'scrape_time': datetime.now().isoformat(),
                        'source': 'igold.bg',
                        'product_type': 'gold',
                        'products': data
                    }, f, ensure_ascii=False, indent=2)
                logger.info("Gold data saved to %s", output_file)

                # Clean up CSV file
                os.remove(csv_file)

    for csv_file in silver_files:
        if os.path.exists(csv_file):
            logger.info("Processing silver file: %s", csv_file)
            data = csv_to_json(csv_file)
            if data:
                output_file = f"{DEFAULT_DATA_DIR}/{DATA_DIR_SILVER}/{today}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'date': today,
                        'scrape_time': datetime.now().isoformat(),
                        'source': 'igold.bg',
                        'product_type': 'silver',
                        'products': data
                    }, f, ensure_ascii=False, indent=2)
                logger.info("Silver data saved to %s", output_file)

                # Clean up CSV file
                os.remove(csv_file)

def cleanup_old_data():
    """Remove data older than 6 months"""
    cutoff_date = datetime.now() - timedelta(days=180)  # 6 months
    cutoff_str = cutoff_date.strftime('%Y-%m-%d')

    for metal_type in ['gold', 'silver']:
        data_dir = f"data/{metal_type}"
        if os.path.exists(data_dir):
            for file in glob.glob(f"{data_dir}/*.json"):
                filename = os.path.basename(file)
                if filename.replace('.json', '') < cutoff_str:
                    logger.info("Removing old data file: %s", file)
                    os.remove(file)

def main():
    """Main entry point for data management CLI."""
    parser = argparse.ArgumentParser(description='Data management for igold scraper')
    parser.add_argument('--cleanup', action='store_true', help='Clean up old data files')
    args = parser.parse_args()

    if args.cleanup:
        cleanup_old_data()
    else:
        organize_daily_data()

if __name__ == '__main__':
    main()
