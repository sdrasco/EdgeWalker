# market_data_client.py

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

import numpy as np
from polygon import RESTClient
from polygon.rest.models import TickerSnapshot, Agg

class MarketDataClient:
    def __init__(self, api_key: str):
        self.client = RESTClient(api_key=api_key)

    def is_market_open(self) -> bool:
        try:
            # Fetch market status
            result = self.client.get_market_status()
            return result.market == 'open'
        except Exception as e:
            print(f"Warning: Error fetching market status: {e}")
            return False

    def get_stock_price(self, ticker: str, market_open: bool) -> Optional[float]:
        try:
            # Fetch snapshot for the provided ticker
            snapshot = self.client.get_snapshot_all("stocks", [ticker])

            if snapshot and isinstance(snapshot[0], TickerSnapshot):
                if market_open and snapshot[0].min:
                    # If the market is open, use min.close (minute-level data)
                    return snapshot[0].min.close
                elif not market_open and snapshot[0].prev_day:
                    # If the market is closed, use prev_day.close
                    return snapshot[0].prev_day.close

            print(f"Warning: No valid price data available for {ticker}.\n")
            return None

        except Exception as e:
            print(f"Warning: Error fetching stock price for {ticker}: {e}")
            return None

    def stock_sigma_mu(self, ticker: str, days: int = 30) -> Tuple[float, float]:
        """
        Computes the fluctuation (std dev) and mean of a stock's closing prices over the specified number of days.
        Default is 30 days.
        """
        # Define the period for fetching historical data
        end_date = datetime.today()
        start_date = end_date - timedelta(days=days)

        # Fetch historical stock prices for the specified period using Polygon's API
        try:
            response = self.client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=start_date.strftime('%Y-%m-%d'),
                to=end_date.strftime('%Y-%m-%d')
            )

            # Check if response is a list of Agg objects or an object with results attribute
            if isinstance(response, list):
                closing_prices = [agg.close for agg in response]  # Directly process the list of Agg objects
            elif response and hasattr(response, 'results') and len(response.results) > 0:
                closing_prices = [agg.c for agg in response.results]  # 'c' is the close price

            # Calculate fluctuation and mean if we have closing prices
            if closing_prices:
                fluctuation = np.std(closing_prices)  # Standard deviation of closing prices
                mean_price = np.mean(closing_prices)  # Mean of closing prices
                return fluctuation, mean_price
            else:
                print(f"No price data available for {ticker} in the last {days} days.")
                return 0.0, 0.0

        except Exception as e:
            print(f"Error fetching historical prices for {ticker}: {e}")

    def get_options_chain(self, ticker: str, params: dict) -> 'pd.DataFrame':
        import pandas as pd

        # Pull the option chain for this ticker
        options_chain = []
        try:
            for option in self.client.list_snapshot_options_chain(ticker, params=params):
                # Collect data into options_chain for each option contract
                options_chain.append({
                    "ticker": option.details.ticker,
                    "expiration_date": option.details.expiration_date,
                    "strike_price": option.details.strike_price,
                    "contract_type": option.details.contract_type,
                    "last_quote": option.last_quote,
                    "last_trade": option.last_trade,
                    "fair_market_value": option.fair_market_value,
                    "open_interest": option.open_interest
                })
        except Exception as e:
            print(f"Warning: Error fetching options chain for {ticker}: {e}")
            return pd.DataFrame()

        # Convert options_chain to pandas DataFrame
        options_df = pd.DataFrame(options_chain)
        return options_df

    def get_ticker_details(self, ticker: str) -> Optional[str]:
        try:
            ticker_details = self.client.get_ticker_details(ticker)
            if ticker_details and ticker_details.name:
                # Limit the number of words in the company name
                max_words = 3
                company_name = ' '.join(ticker_details.name.split()[:max_words])
                return company_name
            else:
                return f"({ticker})"
        except Exception as e:
            print(f"Warning: Could not fetch company name for {ticker}: {e}")
            return ""
