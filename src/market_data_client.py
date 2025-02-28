# market_data_client.py

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import requests
import aiohttp
import asyncio

# Configure basic logging.  show warning or higher for external modules.
logging.basicConfig(
    level=logging.WARNING,  
    format='%(message)s'
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Show info level logger events for this module
logger.setLevel(logging.INFO)

class MarketDataClient:
    def __init__(self, api_key: str):

        # store the api key 
        self.api_key = api_key

        # initialize base URLs for the various API endpoints
        self.options_url = "https://api.polygon.io/v3/snapshot/options"
        self.ticker_details_url = "https://api.polygon.io/v3/reference/tickers"

    async def get_options_chain(self, ticker: str, params: dict, semaphore=None) -> pd.DataFrame:
        options_chain = []
        url = f"{self.options_url}/{ticker}"
        params['apiKey'] = self.api_key
        params['limit'] = 250  # Set a limit for pagination

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
                                logger.warning(f"Failed to fetch options chain for {ticker}. Status code: {response.status}")
                                return pd.DataFrame()  # Return an empty DataFrame on failure

        except Exception as e:
            logger.warning(f"Warning: Error fetching options chain for {ticker}: {e}")
            return pd.DataFrame()  # Return an empty DataFrame on error
        # Convert options_chain to pandas DataFrame
        options_df = pd.DataFrame(options_chain)
        return options_df

    async def get_ticker_details(self, ticker: str, semaphore=None) -> Optional[str]:
        try:
            url = f"{self.ticker_details_url}/{ticker}"
            async with semaphore:
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
                            logger.warning(f"Warning: Failed to fetch details for {ticker}. Status code: {response.status}")
                            return f"({ticker})"
        except Exception as e:
            logger.warning(f"Warning: Could not fetch company name for {ticker}: {e}")
            return ""