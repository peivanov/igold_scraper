#!/usr/bin/env python3
"""
Live precious metals price fetcher
Fetches XAU/EUR (gold) and XAG/EUR (silver) prices
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Optional

import requests

from igold_scraper.config import DEFAULT_DATA_DIR
from igold_scraper.constants import DATA_DIR_LIVE_PRICES
from igold_scraper.exceptions import ConfigurationError, NetworkError, ValidationError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LivePriceFetcher:
    """Fetches live precious metals prices from API."""

    def __init__(self, api_base_url: str = None):
        """
        Initialize the fetcher
        API base URL must be provided via PRECIOUS_METALS_API_BASE environment variable
        """
        self.api_base_url = api_base_url or os.getenv('PRECIOUS_METALS_API_BASE')

        if not self.api_base_url:
            raise ConfigurationError("PRECIOUS_METALS_API_BASE environment variable must be set")

    def _validate_api_response(self, data: any, metal: str) -> None:
        """
        Validate API response structure.

        Args:
            data: API response data
            metal: Metal symbol (XAU or XAG)

        Raises:
            ValidationError: If response structure is invalid
        """
        if not data:
            raise ValidationError(f"Empty response from API for {metal}")

        if not isinstance(data, list) or len(data) == 0:
            raise ValidationError(f"Invalid response format for {metal}: expected non-empty list")

        platform_data = data[0]
        if not isinstance(platform_data, dict):
            raise ValidationError(f"Invalid platform data format for {metal}: expected dict")

        # Validate required fields
        required_fields = ['spreadProfilePrices']
        missing = [f for f in required_fields if f not in platform_data]
        if missing:
            raise ValidationError(f"Missing required fields in {metal} response: {missing}")

        spread_prices = platform_data.get('spreadProfilePrices', [])
        if not spread_prices:
            raise ValidationError(f"No spread profile prices found for {metal}")

    def fetch_live_price(self, metal: str = 'XAU') -> Optional[Dict]:
        """
        Fetch current metal price from the API

        Args:
            metal: 'XAU' for gold or 'XAG' for silver
        """
        api_url = f"{self.api_base_url}/{metal}/EUR"
        metal_name = 'gold' if metal == 'XAU' else 'silver'

        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Validate response structure
            self._validate_api_response(data, metal)

            # Get the first platform's data
            platform_data = data[0]

            # Get the 'elite' spread profile (best prices, smallest spread)
            spread_prices = platform_data.get('spreadProfilePrices', [])
            elite_price = None

            for profile in spread_prices:
                if profile.get('spreadProfile') == 'elite':
                    elite_price = profile
                    break

            # Fallback to first available profile if elite not found
            if not elite_price and spread_prices:
                elite_price = spread_prices[0]

            if not elite_price:
                logger.error("No price data found in API response for %s", metal_name)
                return None

            # Extract bid/ask prices (these are EUR per troy ounce)
            bid_eur_oz = elite_price.get('bid', 0)
            ask_eur_oz = elite_price.get('ask', 0)
            spread = elite_price.get('bidSpread', 0)

            # Calculate mid price
            mid_eur_oz = (bid_eur_oz + ask_eur_oz) / 2

            # Convert to EUR per gram (1 troy ounce = 31.1035 grams)
            troy_oz_to_grams = 31.1035
            mid_eur_g = mid_eur_oz / troy_oz_to_grams
            bid_eur_g = bid_eur_oz / troy_oz_to_grams
            ask_eur_g = ask_eur_oz / troy_oz_to_grams

            # Get timestamp
            timestamp = platform_data.get('ts', int(datetime.now().timestamp() * 1000))
            price_datetime = datetime.fromtimestamp(timestamp / 1000)

            price_data = {
                'timestamp': price_datetime.isoformat(),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'metal': metal,
                'metal_name': metal_name,
                'source': f'Live {metal}/EUR Market Data',
                'platform': 'MarketData',
                'spread_profile': 'standard',
                'prices': {
                    'eur_per_oz': {
                        'bid': round(bid_eur_oz, 2),
                        'ask': round(ask_eur_oz, 2),
                        'mid': round(mid_eur_oz, 2),
                        'spread': round(spread, 2)
                    },
                    'eur_per_gram': {
                        'bid': round(bid_eur_g, 2),
                        'ask': round(ask_eur_g, 2),
                        'mid': round(mid_eur_g, 2)
                    }
                }
            }

            logger.info("Fetched live %s price: %.2f EUR/g", metal_name, mid_eur_g)
            return price_data

        except requests.exceptions.RequestException as e:
            logger.exception("Failed to fetch live %s price: %s", metal_name, e)
            raise NetworkError(f"Failed to fetch live {metal_name} price: {e}") from e
        except (KeyError, ValueError, IndexError) as e:
            logger.exception("Failed to parse API response for %s: %s", metal_name, e)
            return None

    def save_price(self, price_data: Dict, metal: str = 'XAU') -> bool:
        """Save price data to JSON file in appropriate directory"""
        try:
            metal_name = 'gold' if metal == 'XAU' else 'silver'
            directory = f"{DEFAULT_DATA_DIR}/{DATA_DIR_LIVE_PRICES}/{metal_name}"
            os.makedirs(directory, exist_ok=True)

            date = price_data.get('date', datetime.now().strftime('%Y-%m-%d'))
            filename = f"{directory}/{date}.json"

            # If file exists for today, append to it (for historical tracking)
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = [existing_data]
                existing_data.append(price_data)
                data_to_save = existing_data
            else:
                data_to_save = [price_data]

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)

            logger.info("Saved live %s price data to %s", metal_name, filename)
            return True

        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.exception("Failed to save price data: %s", e)
            return False

    def get_latest_price(self, metal: str = 'XAU') -> Optional[Dict]:
        """Fetch and return the latest price without saving"""
        return self.fetch_live_price(metal)

def main():
    """Fetch and save current live precious metals prices"""
    parser = argparse.ArgumentParser(description='Fetch live precious metals prices')
    parser.add_argument('--metals', nargs='+', default=['XAU', 'XAG'],
                       choices=['XAU', 'XAG'],
                       help='Metals to fetch prices for (XAU=gold, XAG=silver)')
    args = parser.parse_args()

    # Get API base URL from environment or use default
    api_base = os.getenv('PRECIOUS_METALS_API_BASE')
    fetcher = LivePriceFetcher(api_base_url=api_base)

    success_count = 0

    for metal in args.metals:
        metal_name = 'Gold' if metal == 'XAU' else 'Silver'
        logger.info("Fetching %s (%s) price...", metal_name, metal)

        price_data = fetcher.fetch_live_price(metal)

        if price_data:
            fetcher.save_price(price_data, metal)

            # Print summary
            eur_price = price_data['prices']['eur_per_gram']['mid']
            print(f"\n✅ Live {metal_name} Price:")
            print(f"   {eur_price:.2f} EUR/g")
            print(f"   Source: {price_data['source']}")
            print(f"   Time: {price_data['timestamp']}")

            success_count += 1
        else:
            logger.error("Failed to fetch live %s price", metal_name)

    if success_count == 0:
        logger.error("Failed to fetch any live prices")
        sys.exit(1)
    else:
        print(f"\n✅ Successfully fetched {success_count}/{len(args.metals)} prices")

if __name__ == '__main__':
    main()
