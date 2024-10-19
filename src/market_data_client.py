# market_data_client.py

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import requests
import aiohttp
import asyncio

class MarketDataClient:
    def __init__(self, api_key: str):

        # store the api key 
        self.api_key = api_key

        # initialize base URLs for the various API endpoints
        self.options_url = "https://api.polygon.io/v3/snapshot/options"
        self.market_status_url = "https://api.polygon.io/v1/marketstatus/now"
        self.historical_url = "https://api.polygon.io/v2/aggs/ticker"
        self.ticker_details_url = "https://api.polygon.io/v3/reference/tickers"

    async def is_market_open(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.market_status_url, params={"apiKey": self.api_key}) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('market') == 'open'
                    else:
                        print(f"Warning: Failed to fetch market status, HTTP status code: {response.status}")
                        return False
        except Exception as e:
            print(f"Warning: Error fetching market status: {e}")
            return False

    async def stock_sigma_mu(self, ticker: str, days: int = 30, semaphore=None) -> Tuple[float, float]:
        end_date = datetime.today()
        start_date = end_date - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        url = f"{self.historical_url}/{ticker}/range/1/day/{start_date_str}/{end_date_str}"
        closing_prices = []
        
        try:
            async with aiohttp.ClientSession() as session:
                while url:
                    async with session.get(url, params={"apiKey": self.api_key}) as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'results' in data and len(data['results']) > 0:
                                closing_prices.extend([agg['c'] for agg in data['results']])
                            url = data.get('next_url')
                        else:
                            print(f"Failed to fetch historical data. Status code: {response.status}")
                            return 0.0, 0.0

                if closing_prices:
                    fluctuation = np.std(closing_prices)
                    mean_price = np.mean(closing_prices)
                    return fluctuation, mean_price
                else:
                    print(f"No price data available for {ticker} in the last {days} days.")
                    return 0.0, 0.0
        except Exception as e:
            print(f"Error fetching historical prices for {ticker}: {e}")
            return 0.0, 0.0

    async def get_options_chain(self, ticker: str, params: dict, semaphore=None) -> pd.DataFrame:
        options_chain = []
        url = f"{self.options_url}/{ticker}"
        params['apiKey'] = self.api_key
        params['limit'] = 25  # Set a limit for pagination

        try:
            # Use the semaphore to limit concurrency
            async with semaphore:
                async with aiohttp.ClientSession() as session:
                    while url:  # Loop to handle pagination
                        async with session.get(url, params=params) as response:
                            if response.status == 200:
                                data = await response.json()

                                # Collect options data from 'results'
                                if 'results' in data and data['results']:
                                    options_chain.extend(data['results'])

                                # Check for pagination (next_url)
                                if data.get('next_url'):
                                    url = f"{data.get('next_url')}&apiKey={self.api_key}"
                                    params = {}  # Reset params if `next_url` already includes them
                                else:
                                    break  # No more pages
                            else:
                                print(f"Failed to fetch options chain for {ticker}. Status code: {response.status}")
                                return pd.DataFrame()  # Return an empty DataFrame on failure

        except Exception as e:
            print(f"Warning: Error fetching options chain for {ticker}: {e}")
            return pd.DataFrame()  # Return an empty DataFrame on error
        # Convert options_chain to pandas DataFrame
        options_df = pd.DataFrame(options_chain)
        return options_df

    async def get_ticker_details(self, ticker: str, semaphore=None) -> Optional[str]:
        try:
            url = f"{self.ticker_details_url}/{ticker}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"apiKey": self.api_key}) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'results' in data and data['results'].get('name'):
                            max_words = 3
                            company_name = ' '.join(data['results']['name'].split()[:max_words])
                            return company_name
                        else:
                            return f"({ticker})"
                    else:
                        print(f"Warning: Failed to fetch details for {ticker}. Status code: {response.status}")
                        return f"({ticker})"
        except Exception as e:
            print(f"Warning: Could not fetch company name for {ticker}: {e}")
            return ""