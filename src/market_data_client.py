# market_data_client.py

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import requests
from polygon import RESTClient
from polygon.rest.models import TickerSnapshot, Agg

class MarketDataClient:
    def __init__(self, api_key: str):

        # store the api key 
        self.api_key = api_key

        # initialize base URLs for the various API endpoints
        self.base_url = "https://api.polygon.io/v3/snapshot/options"
        self.market_status_url = "https://api.polygon.io/v1/marketstatus/now"
        self.stock_snapshot_url = "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers"
        self.historical_url = "https://api.polygon.io/v2/aggs/ticker"
        self.ticker_details_url = "https://api.polygon.io/v3/reference/tickers"

    def is_market_open(self) -> bool:
        try:
            # Make an HTTP GET request to the API endpoint for market status
            response = requests.get(self.market_status_url, params={"apiKey": self.api_key})
            
            # Check if the request was successful
            if response.status_code == 200:
                result = response.json()
                return result.get('market') == 'open'
            else:
                print(f"Warning: Failed to fetch market status, HTTP status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"Warning: Error fetching market status: {e}")
            return False

    def get_stock_price(self, ticker: str, market_open: bool) -> Optional[float]:
        try:
            # Make an HTTP GET request to fetch snapshot data for the provided ticker
            url = f"{self.stock_snapshot_url}/{ticker}"
            response = requests.get(url, params={"apiKey": self.api_key})
            
            # Check if the request was successful
            if response.status_code == 200:
                # Extract the JSON data from the response
                data = response.json()
                snapshot = data.get('ticker')
                
                if snapshot:
                    # Check if the 'day' or 'min' close prices are non-zero
                    if 'day' in snapshot and snapshot['day']['c'] != 0:
                        return snapshot['day']['c']
                    elif market_open and 'min' in snapshot and snapshot['min']['c'] != 0:
                        return snapshot['min']['c']
                    # Fall back to 'prevDay' close price if 'day' and 'min' are zeros
                    elif 'prevDay' in snapshot and snapshot['prevDay']['c'] != 0:
                        return snapshot['prevDay']['c']
                    else:
                        print(f"Warning: No valid price data available for {ticker}.")
                        return None

            print(f"Warning: No valid price data available for {ticker}.")
            return None

        except Exception as e:
            print(f"Warning: Error fetching stock price for {ticker}: {e}")
            return None

    def stock_sigma_mu(self, ticker: str, days: int = 30) -> Tuple[float, float]:
        """
        Computes the fluctuation (std dev) and mean of a stock's closing prices over the specified number of days.
        Handles pagination.
        """
        # Define the period for fetching historical data
        end_date = datetime.today()
        start_date = end_date - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')

        # Construct the initial API URL for fetching historical data
        url = f"{self.historical_url}/{ticker}/range/1/day/{start_date_str}/{end_date_str}"
        closing_prices = []

        try:
            while url:  # Loop to handle pagination
                response = requests.get(url, params={"apiKey": self.api_key})
                
                # Check if the request was successful
                if response.status_code == 200:
                    data = response.json()

                    # Extract closing prices from the results
                    if 'results' in data and len(data['results']) > 0:
                        closing_prices.extend([agg['c'] for agg in data['results']])

                    # Check for the next URL for pagination
                    url = data.get('next_url')
                else:
                    print(f"Failed to fetch historical data. Status code: {response.status_code}")
                    return 0.0, 0.0

            # Calculate fluctuation (std deviation) and mean if closing prices exist
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

    def get_options_chain(self, ticker: str, params: dict) -> pd.DataFrame:
        options_chain = []
        try:
            # Construct the URL with supported params (ticker, expiration_date, strike_price, etc.)
            url = f"{self.base_url}/{ticker}"
            # Add the API key to the params
            params['apiKey'] = self.api_key
            params['limit'] = 25

            # Make the initial request
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise an exception for bad responses
            
            # Parse the JSON response
            data = response.json()

            # Collect options data from the 'results' key
            if 'results' in data and data['results']:
                for option in data['results']:
                    # Post-processing and filtering will be done here
                    options_chain.append({
                        "ticker": option['details']['ticker'],
                        "expiration_date": option['details']['expiration_date'],
                        "strike_price": option['details']['strike_price'],
                        "contract_type": option['details']['contract_type'],
                        "last_quote": option['last_quote'],
                        "last_trade": option['last_trade'],
                        "fair_market_value": option.get('fmv', None),  # Sometimes fmv can be missing
                        "open_interest": option.get('open_interest', None)
                    })

            # Handle pagination (if `next_url` is provided, loop through it to fetch more results)
            while 'next_url' in data:
                next_url = data['next_url'] + f"&apiKey={self.api_key}"
                response = requests.get(next_url)
                response.raise_for_status()
                data = response.json()
                if 'results' in data and data['results']:
                    for option in data['results']:
                        options_chain.append({
                            "ticker": option['details']['ticker'],
                            "expiration_date": option['details']['expiration_date'],
                            "strike_price": option['details']['strike_price'],
                            "contract_type": option['details']['contract_type'],
                            "last_quote": option['last_quote'],
                            "last_trade": option['last_trade'],
                            "fair_market_value": option.get('fmv', None),
                            "open_interest": option.get('open_interest', None)
                        })
        
        except Exception as e:
            print(f"Request URL: {response.url}")
            print(f"Warning: Error fetching options chain for {ticker}: {e}")
            return pd.DataFrame()

        # Convert options_chain to pandas DataFrame
        options_df = pd.DataFrame(options_chain)

        return options_df

    def get_ticker_details(self, ticker: str) -> Optional[str]:
        """
        Fetches the details of the given ticker (e.g., company name) and returns a shortened version.
        """
        try:
            # Make an HTTP GET request to fetch ticker details
            url = f"{self.ticker_details_url}/{ticker}"
            response = requests.get(url, params={"apiKey": self.api_key})

            # Check if the request was successful
            if response.status_code == 200:
                data = response.json()

                # Extract the company name from the ticker details
                if 'results' in data and data['results'].get('name'):
                    max_words = 3
                    company_name = ' '.join(data['results']['name'].split()[:max_words])
                    return company_name
                else:
                    return f"({ticker})"
            else:
                print(f"Warning: Failed to fetch details for {ticker}. Status code: {response.status_code}")
                return f"({ticker})"

        except Exception as e:
            print(f"Warning: Could not fetch company name for {ticker}: {e}")
            return ""