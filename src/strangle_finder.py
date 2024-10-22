import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from market_data_client import MarketDataClient
from models import Strangle

class StrangleFinder:
    def __init__(self, market_data_client: MarketDataClient, force_coupled: bool = False):
        self.market_data_client = market_data_client
        self.force_coupled = force_coupled

    async def find_balanced_strangle(self, ticker: str, semaphore=None) -> Optional[Strangle]:
        
        # set date limits
        date_min = datetime.today() + timedelta(days=30)
        date_max = date_min + timedelta(days=90)
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
        
        # divide into calls and puts
        calls_df = options_df[options_df['contract_type'] == 'call'].copy()
        puts_df = options_df[options_df['contract_type'] == 'put'].copy()

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
        company_name = await self.market_data_client.get_ticker_details(ticker, semaphore=semaphore)

        # Create Strangle object
        # (**) means _call suffix is no different from _put
        best_strangle = Strangle(
            ticker=ticker,
            company_name=company_name,
            stock_price=best_row['stock_price_call'],  # (**)
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
            implied_volatility=best_row['implied_volatility_call'],  # (**)
            num_strangles_considered=len(calls_df) * len(puts_df)
        )

        # After instantiation, calculate the optional fields
        best_strangle.calculate_escape_ratio()
        best_strangle.calculate_probability_of_profit()
        best_strangle.calculate_expected_gain()

        return best_strangle

    def _filter_options(self, options_df: pd.DataFrame) -> pd.DataFrame:

        # Make a copy to avoid SettingWithCopyWarning
        options_df = options_df.copy()

        # Ensure all necessary fields are present and not None or NaN
        required_columns = ['open_interest', 'day', 'details', 'underlying_asset', 'implied_volatility']

        # Check if all required columns exist
        for column in required_columns:
            if column not in options_df.columns:
                return pd.DataFrame()

        # Ensure all necessary fields are not None or NaN
        options_df = options_df[
            pd.notna(options_df['open_interest']) &
            pd.notna(options_df['day']) &
            pd.notna(options_df['details']) &
            pd.notna(options_df['underlying_asset']) &
            pd.notna(options_df['implied_volatility'])
        ]
        if options_df.empty:
            return pd.DataFrame() 

        # Extract what we need from the 'details' dictionary
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

        # Extract volume
        options_df['volume'] = options_df['day'].map(lambda x: x.get('volume', None))
        options_df = options_df[
            pd.notna(options_df['volume']) 
        ]
        if options_df.empty:
            return pd.DataFrame() 

        # Extract stock price from the 'underlying_asset' dictionary. Exiting if it's not there.
        stock_price = options_df['underlying_asset'].iloc[0].get('price', None) if not options_df.empty else None
        options_df['stock_price'] = stock_price
        if stock_price is None:
            return pd.DataFrame()

        # Extract 'bid' and 'ask' from the 'last_quote' dictionary
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

        # Estimate premium using fair market value, with fallback to last quote's bid-ask midpoint
        options_df['premium'] = options_df.apply(
            lambda row: row.get('fmv', None) if row.get('fmv', None) else row['midpoint'],
            axis=1
        )

        # First level requirements (tune as you like)
        strike_buffer_factor = 10.0
        strike_min = stock_price / strike_buffer_factor
        strike_max = stock_price * strike_buffer_factor
        options_df = options_df[
            (options_df['exercise_style'] == 'american') &
            (options_df['shares_per_contract'] == 100) &
            (stock_price >= 10) & 
            (stock_price <= 500) &
            (options_df['open_interest'] > 1) &
            (options_df['volume'] > 1) &
            (options_df['premium'] > 0) & 
            (options_df['premium'] < 20.0) &
            (options_df['strike_price'] >= strike_min) & 
            (options_df['strike_price'] <= strike_max) &
            (options_df['implied_volatility'] > 0)
        ]
        if options_df.empty:
            return pd.DataFrame() 


        # Filter for suspicious premiums
        options_df['suspicious_premium'] = options_df.apply(
            lambda row: row['premium'] < max(0, row['strike_price'] - stock_price)
            if row['contract_type'] == 'put'
            else row['premium'] < max(0, stock_price - row['strike_price']),
            axis=1
        )
        options_df = options_df[~options_df['suspicious_premium']]
        if options_df.empty:
            return pd.DataFrame() 

        # Calculate the spread and filter (tune as you like)
        max_spread_factor = 0.5
        options_df['spread'] = abs(options_df['ask'] - options_df['bid'])
        options_df = options_df[(options_df['spread'] <= max_spread_factor * options_df['premium'])]
        if options_df.empty:
            return pd.DataFrame() 

        # only keep necessary columns
        keep_columns = ['stock_price', 'expiration_date', 'strike_price', 'contract_type', 'premium', 'implied_volatility']
        filtered_options_df = options_df[keep_columns]

        return filtered_options_df