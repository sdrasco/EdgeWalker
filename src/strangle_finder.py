import os
import sys
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Optional

from market_data_client import MarketDataClient
from models import Strangle
from strangle_module import Option, StrangleCombination, find_min_spread  # Import C++ bindings

# Configure basic logging. Show warning or higher for external modules.
logging.basicConfig(
    level=logging.WARNING,
    format='%(message)s'
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Show info level logger events for this module
logger.setLevel(logging.INFO)

class StrangleFinder:
    def __init__(self, market_data_client: MarketDataClient):
        self.market_data_client = market_data_client

    async def find_balanced_strangle(self, ticker: str, semaphore=None) -> Optional[Strangle]:
        
        # Set date limits
        date_min = datetime.today() + timedelta(days=7)
        date_max = date_min + timedelta(days=180)
        date_min = date_min.strftime('%Y-%m-%d')
        date_max = date_max.strftime('%Y-%m-%d')

        # Define parameters for options chain retrieval
        params = {
            "expiration_date.gte": date_min,
            "expiration_date.lte": date_max,
        }

        # Pull the option chain for this ticker asynchronously
        options_df = await self.market_data_client.get_options_chain(ticker, params, semaphore=semaphore)
        if options_df.empty:
            return None

        # Filter the contracts
        options_df = self._filter_options(options_df)
        if options_df.empty:
            return None

        # Divide options into calls and puts, and extract expiration dates
        calls = [
            Option(row['premium'], row['strike_price'], row['implied_volatility'], row['contract_type'])
            for _, row in options_df[options_df['contract_type'] == 'call'].iterrows()
        ]
        puts = [
            Option(row['premium'], row['strike_price'], row['implied_volatility'], row['contract_type'])
            for _, row in options_df[options_df['contract_type'] == 'put'].iterrows()
        ]
        
        if not calls or not puts:
            return None  # Ensure there are both calls and puts to process

        # Call the C++ function to find the best strangle
        best_combination: StrangleCombination = find_min_spread(calls, puts)

        # Get company name and expiration dates for the selected strangle
        company_name = await self.market_data_client.get_ticker_details(ticker, semaphore=semaphore)

        # Find expiration dates for the selected options
        expiration_date_call = options_df.loc[
            (options_df['strike_price'] == best_combination.call.strike_price) &
            (options_df['contract_type'] == 'call'),
            'expiration_date'
        ].values[0]
        expiration_date_put = options_df.loc[
            (options_df['strike_price'] == best_combination.put.strike_price) &
            (options_df['contract_type'] == 'put'),
            'expiration_date'
        ].values[0]

        # Use a weighted IV for the strangle IV
        total_premium = best_combination.call.premium + best_combination.put.premium
        if total_premium != 0:
            strangle_iv = (best_combination.call.premium * best_combination.call.implied_volatility +
                           best_combination.put.premium * best_combination.put.implied_volatility) / total_premium
        else:
            return None

        # Create Strangle object
        best_strangle = Strangle(
            ticker=ticker,
            company_name=company_name,
            stock_price=best_combination.call.strike_price,  # no different from _put
            expiration_date_call=expiration_date_call,
            expiration_date_put=expiration_date_put,
            strike_price_call=best_combination.call.strike_price,
            strike_price_put=best_combination.put.strike_price,
            premium_call=best_combination.call.premium,
            premium_put=best_combination.put.premium,
            cost_call=best_combination.call.premium * 100.0,
            cost_put=best_combination.put.premium * 100.0,
            upper_breakeven=best_combination.upper_breakeven,
            lower_breakeven=best_combination.lower_breakeven,
            breakeven_difference=best_combination.breakeven_difference,
            normalized_difference=best_combination.normalized_difference,
            implied_volatility=strangle_iv,
            num_strangles_considered=len(calls) * len(puts)
        )

        # After instantiation, calculate the optional fields
        best_strangle.calculate_escape_ratio()
        best_strangle.calculate_probability_of_profit()
        best_strangle.calculate_expected_gain()

        return best_strangle

    def _filter_options(self, options_df: pd.DataFrame) -> pd.DataFrame:
        # Filtering logic remains the same as provided
        options_df = options_df.copy()
        required_columns = ['open_interest', 'day', 'details', 'underlying_asset', 'implied_volatility']
        
        for column in required_columns:
            if column not in options_df.columns:
                return pd.DataFrame()

        options_df = options_df[
            pd.notna(options_df['open_interest']) &
            pd.notna(options_df['day']) &
            pd.notna(options_df['details']) &
            pd.notna(options_df['underlying_asset']) &
            pd.notna(options_df['implied_volatility'])
        ]
        if options_df.empty:
            return pd.DataFrame()

        options_df['expiration_date'] = options_df['details'].map(lambda x: x.get('expiration_date', None))
        options_df['strike_price'] = options_df['details'].map(lambda x: x.get('strike_price', None))
        options_df['exercise_style'] = options_df['details'].map(lambda x: x.get('exercise_style', None))
        options_df['shares_per_contract'] = options_df['details'].map(lambda x: x.get('shares_per_contract', None))
        options_df['contract_type'] = options_df['details'].map(lambda x: x.get('contract_type', None))
        options_df = options_df[
            pd.notna(options_df['expiration_date']) &
            pd.notna(options_df['strike_price']) &
            pd.notna(options_df['exercise_style']) &
            pd.notna(options_df['contract_type']) &
            pd.notna(options_df['shares_per_contract'])
        ]
        if options_df.empty:
            return pd.DataFrame()

        options_df['volume'] = options_df['day'].map(lambda x: x.get('volume', None))
        options_df = options_df[pd.notna(options_df['volume'])]
        if options_df.empty:
            return pd.DataFrame()

        stock_price = options_df['underlying_asset'].iloc[0].get('price', None) if not options_df.empty else None
        options_df['stock_price'] = stock_price
        if stock_price is None:
            return pd.DataFrame()

        options_df['bid'] = options_df['last_quote'].map(lambda x: x.get('bid', None))
        options_df['ask'] = options_df['last_quote'].map(lambda x: x.get('ask', None))
        options_df['midpoint'] = options_df['last_quote'].map(lambda x: x.get('midpoint', None))
        options_df = options_df[
            pd.notna(options_df['bid']) &
            pd.notna(options_df['ask']) &
            pd.notna(options_df['midpoint'])
        ]
        if options_df.empty:
            return pd.DataFrame()

        options_df['premium'] = options_df.apply(
            lambda row: row.get('fmv', None) if row.get('fmv', None) else row['midpoint'],
            axis=1
        )

        strike_buffer_factor = 10.0
        strike_min = stock_price / strike_buffer_factor
        strike_max = stock_price * strike_buffer_factor
        options_df = options_df[
            (options_df['exercise_style'] == 'american') &
            (options_df['shares_per_contract'] == 100) &
            (stock_price >= 10) & 
            (stock_price <= 500) &
            (options_df['open_interest'] > 5) &
            (options_df['volume'] > 5) &
            (options_df['premium'] > 0.01 * stock_price) & 
            (options_df['premium'] < 20.0) &
            (options_df['strike_price'] >= strike_min) & 
            (options_df['strike_price'] <= strike_max) &
            (options_df['implied_volatility'] > 0)
        ]
        if options_df.empty:
            return pd.DataFrame()

        options_df['suspicious_premium'] = options_df.apply(
            lambda row: row['premium'] < max(0, row['strike_price'] - stock_price)
            if row['contract_type'] == 'put'
            else row['premium'] < max(0, stock_price - row['strike_price']),
            axis=1
        )
        options_df = options_df[~options_df['suspicious_premium']]
        if options_df.empty:
            return pd.DataFrame()

        max_spread_factor = 0.3
        options_df['spread'] = abs(options_df['ask'] - options_df['bid'])
        options_df = options_df[(options_df['spread'] <= max_spread_factor * options_df['premium'])]
        if options_df.empty:
            return pd.DataFrame()

        keep_columns = ['stock_price', 'expiration_date', 'strike_price', 'contract_type', 'premium', 'implied_volatility']
        filtered_options_df = options_df[keep_columns]

        return filtered_options_df