# strangle_finder.py

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from market_data_client import MarketDataClient
from models import Strangle


class StrangleFinder:
    def __init__(self, market_data_client: MarketDataClient, force_coupled: bool = False):
        self.market_data_client = market_data_client
        self.force_coupled = force_coupled

    def find_balanced_strangle(self, ticker: str, market_open: bool) -> Optional[Strangle]:
        # Get current stock price estimate and make a strike price filter
        stock_price = self.market_data_client.get_stock_price(ticker, market_open)
        max_stock_price = 500.00
        min_stock_price = 25.0
        if stock_price is None or stock_price > max_stock_price or stock_price < min_stock_price:
            return None
        buffer_factor = 4.0
        strike_min = stock_price / buffer_factor
        strike_max = stock_price * buffer_factor

        # Do a volatility sanity check (throwing things out if their 30-day-variance is
        # larger than a set factor of their 30-day-mean).
        stock_sigma, stock_mu = self.market_data_client.stock_sigma_mu(ticker, days=30)
        max_fluctuation = 4.0
        if stock_sigma > max_fluctuation * stock_mu:
            return None

        # Make date strings that define our search range
        date_min = datetime.today() + timedelta(days=14)
        date_max = date_min + timedelta(days=120)
        date_min = date_min.strftime('%Y-%m-%d')
        date_max = date_max.strftime('%Y-%m-%d')

        # Define parameters for options chain retrieval
        params = {
            "expiration_date.gte": date_min,
            "expiration_date.lte": date_max,
            "strike_price.gte": strike_min,
            "strike_price.lte": strike_max,
            "contract_type.in": "call,put",
            "exercise_style": "american",
            "contract_size": 100,
            "option_type": "equity",
            "market_type": "listed",
            "contract_flag": "standard",
            "open_interest.gte": 1,
            "volume.gte": 1,
            "premium.gte": 0.5,
            "premium.lte": 10.0
        }

        # Pull the option chain for this ticker
        options_df = self.market_data_client.get_options_chain(ticker, params)
        if options_df.empty or 'contract_type' not in options_df.columns:
            return None

        # Extract calls and puts
        calls_df = options_df[options_df['contract_type'] == 'call'].copy()
        puts_df = options_df[options_df['contract_type'] == 'put'].copy()

        # Clean the lists of call and put contracts
        calls_df = self._filter_options(calls_df, stock_price)
        puts_df = self._filter_options(puts_df, stock_price)

        # Create a cartesian product of all combinations of calls and puts
        merged_df = calls_df.assign(key=1).merge(
            puts_df.assign(key=1), on='key', suffixes=('_call', '_put')
        ).drop('key', axis=1)

        # Apply the force_coupled flag if necessary
        if self.force_coupled:
            merged_df = merged_df[
                merged_df['expiration_date_call'] == merged_df['expiration_date_put']
            ]

        if merged_df.empty:
            return None

        # Calculate the strangle costs
        contract_buy_and_sell_fee = 0.53 + 0.55 # Brokerage-dependent cost
        merged_df['strangle_costs'] = (
            merged_df['premium_call'] + merged_df['premium_put'] +
            2.0 * contract_buy_and_sell_fee / 100.0
        )

        # Calculate the upper and lower breakeven points
        merged_df['upper_breakeven'] = merged_df['strike_price_call'] + merged_df['strangle_costs']
        merged_df['lower_breakeven'] = merged_df['strike_price_put'] - merged_df['strangle_costs']

        # Calculate the breakeven difference
        merged_df['breakeven_difference'] = (
            merged_df['upper_breakeven'] - merged_df['lower_breakeven']
        ).abs()

        # Calculate the average strike price for normalization
        merged_df['average_strike_price'] = 0.5 * (
            merged_df['strike_price_call'] + merged_df['strike_price_put']
        )

        # Calculate the normalized breakeven difference
        merged_df['normalized_difference'] = (
            merged_df['breakeven_difference'] / merged_df['average_strike_price']
        )

        # Check if merged_df is empty or if 'normalized_difference' has all NaN values
        if merged_df.empty or merged_df['normalized_difference'].isna().all():
            return None

        # Get the single best strangle across all calls and puts
        best_row = merged_df.loc[merged_df['normalized_difference'].idxmin()].copy()

        # Get company name
        company_name = self.market_data_client.get_ticker_details(ticker)

        # Create Strangle object
        best_strangle = Strangle(
            ticker=ticker,
            company_name=company_name,
            stock_price=stock_price,
            expiration_date_call=best_row['expiration_date_call'],
            expiration_date_put=best_row['expiration_date_put'],
            strike_price_call=best_row['strike_price_call'],
            strike_price_put=best_row['strike_price_put'],
            premium_call=best_row['premium_call'],
            premium_put=best_row['premium_put'],
            cost_call=best_row['premium_call'] * 100.0,
            cost_put=best_row['premium_put'] * 100.0,
            upper_breakeven=best_row['upper_breakeven'],
            lower_breakeven=best_row['lower_breakeven'],
            breakeven_difference=best_row['breakeven_difference'],
            normalized_difference=best_row['normalized_difference'],
            variability_ratio=0.0,  # Will be calculated
            escape_ratio=0.0,       # Will be calculated
            num_strangles_considered=len(calls_df) * len(puts_df)
        )

        # Calculate additional ratios
        best_strangle.calculate_variability_ratio(stock_sigma)
        best_strangle.calculate_escape_ratio()

        return best_strangle

    def _filter_options(
        self, options_df: pd.DataFrame, stock_price: float, max_spread_factor: float = 0.5
    ) -> pd.DataFrame:
        # Calculate bid and ask based on 'last_quote'
        options_df.loc[:, 'bid'] = options_df.apply(
            lambda row: row['last_quote'].get('bid', None)
            if 'last_quote' in row and row['last_quote'] is not None else None,
            axis=1
        )
        options_df.loc[:, 'ask'] = options_df.apply(
            lambda row: row['last_quote'].get('ask', None)
            if 'last_quote' in row and row['last_quote'] is not None else None,
            axis=1
        )

        # Calculate the premium using bid-ask midpoint, falling back to last_trade or fair_market_value
        options_df.loc[:, 'premium'] = options_df.apply(
            lambda row: (row['bid'] + row['ask']) / 2.0
            if pd.notna(row['bid']) and pd.notna(row['ask'])
            else (
                row['last_trade'].get('price', None)
                if 'last_trade' in row and row['last_trade'] is not None and
                row['last_trade'].get('price', None) is not None
                else row['fair_market_value']
            ),
            axis=1
        )

        # Calculate the spread if both bid and ask are available
        options_df.loc[:, 'spread'] = options_df.apply(
            lambda row: abs(row['ask'] - row['bid'])
            if pd.notna(row['bid']) and pd.notna(row['ask']) else None,
            axis=1
        )

        options_df.loc[:, 'suspicious_premium'] = options_df.apply(
            lambda row: row['premium'] < max(0, row['strike_price'] - stock_price)
            if row['contract_type'] == 'put' and pd.notna(row['premium']) and pd.notna(row['strike_price'])
            else row['premium'] < max(0, stock_price - row['strike_price'])
            if pd.notna(row['premium']) and pd.notna(row['strike_price'])
            else False,
            axis=1
        )

        # Check for any None values in bid, ask, or spread
        options_df.loc[:, 'any_None'] = (
            options_df['spread'].isna() |
            options_df['bid'].isna() |
            options_df['ask'].isna()
        )

        # Apply the filtering conditions
        filtered_options_df = options_df[
            ~options_df['any_None'] &  # No None values
            (options_df['premium'] != 0) &
            (options_df['bid'] != 0) &
            (options_df['ask'] != 0) &
            (options_df['spread'] <= max_spread_factor * options_df['premium']) &
            ~options_df['suspicious_premium']
        ].copy()

        # Strip off the columns that we are done with
        keep_columns = ['expiration_date', 'strike_price', 'premium']
        filtered_options_df = filtered_options_df[keep_columns]

        return filtered_options_df