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
        date_min = datetime.today() + timedelta(days=4)
        date_max = date_min + timedelta(days=30)
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
            stock_price=options_df['stock_price'].iloc[0],
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
        # Immediately return if critical columns are missing
        required_columns = ['details', 'underlying_asset', 'last_quote', 'implied_volatility']
        if not all(col in options_df.columns for col in required_columns):
            return pd.DataFrame()

        # Filter on implied volatility before extracting other fields
        options_df = options_df[options_df['implied_volatility'] > 0]
        if options_df.empty:
            return pd.DataFrame()

        # Use vectorized assignments to extract required fields from nested dictionaries
        options_df = options_df.assign(
            expiration_date=[x.get('expiration_date') for x in options_df['details']],
            strike_price=[x.get('strike_price') for x in options_df['details']],
            exercise_style=[x.get('exercise_style') for x in options_df['details']],
            shares_per_contract=[x.get('shares_per_contract') for x in options_df['details']],
            contract_type=[x.get('contract_type') for x in options_df['details']],
            stock_price=[x.get('price') for x in options_df['underlying_asset']],
            bid=[x.get('bid') for x in options_df['last_quote']],
            ask=[x.get('ask') for x in options_df['last_quote']],
            midpoint=[x.get('midpoint') for x in options_df['last_quote']],
            premium=[x.get('fmv', None) for x in options_df['details']]
        ).dropna(subset=[
            'expiration_date', 'strike_price', 'exercise_style', 'shares_per_contract',
            'contract_type', 'stock_price', 'bid', 'ask', 'midpoint'
        ])

        if options_df.empty:
            return pd.DataFrame()

        # Fill missing premiums with midpoint
        options_df['premium'] = pd.to_numeric(options_df['premium'], errors='coerce')
        options_df['midpoint'] = pd.to_numeric(options_df['midpoint'], errors='coerce')
        options_df['premium'] = options_df['premium'].fillna(options_df['midpoint'])

        # Store stock price once to avoid repeated access
        stock_price = options_df['stock_price'].iloc[0]

        # Apply all filtering conditions in a single step
        options_df = options_df[
            (options_df['exercise_style'] == 'american') &
            (options_df['shares_per_contract'] == 100) &
            (options_df['open_interest'] > 5) &
            (options_df['premium'] > 0.01 * stock_price) &
            (options_df['premium'] < 20.0) &
            (options_df['strike_price'].between(stock_price / 10, stock_price * 10)) &
            ((options_df['ask'] - options_df['bid']).abs() <= 0.3 * options_df['premium']) &
            # Ensure premium is reasonably close to the prevailing market quotes
            (options_df['premium'] >= options_df['bid'] - 0.1 * options_df['midpoint']) &
            (options_df['premium'] <= options_df['ask'] + 0.1 * options_df['midpoint']) &
            ~(
                ((options_df['contract_type'] == 'put') & (options_df['premium'] < (options_df['strike_price'] - stock_price))) |
                ((options_df['contract_type'] == 'call') & (options_df['premium'] < (stock_price - options_df['strike_price'])))
            )
        ]

        # Define columns to return
        columns_to_return = ['stock_price', 'expiration_date', 'strike_price', 'contract_type', 'premium', 'implied_volatility']

        return options_df[columns_to_return]


