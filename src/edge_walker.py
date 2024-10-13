# Standard library imports
# import cProfile is performed before main execution
# if --profile flag is provided via the command line
import json
import os
import sys
import time
from datetime import datetime, timedelta

# Third-party imports
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
from polygon import RESTClient
from polygon.rest.models import TickerSnapshot

# Data classes
from dataclasses import dataclass
from typing import Optional, List, Tuple


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

            # Extract the closing prices from the list of Agg objects
            if isinstance(response, list) and len(response) > 0:
                closing_prices = [agg.close for agg in response]  # Extract 'close' prices

                # If closing prices are found, calculate std dev and mean
                if closing_prices:
                    fluctuation = np.std(closing_prices)  # Standard deviation of closing prices
                    mean_price = np.mean(closing_prices)  # Mean of closing prices

                    return fluctuation, mean_price
                else:
                    print(f"No price data available for {ticker} in the last {days} days.")
                    return 0.0, 0.0  # Handle case where no data is available
            else:
                print(f"No valid data found for {ticker}.")
                return 0.0, 0.0

        except Exception as e:
            print(f"Error fetching historical prices for {ticker}: {e}")
            return 0.0, 0.0  # Handle error case

    def get_options_chain(self, ticker: str, params: dict) -> pd.DataFrame:
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


@dataclass
class Strangle:
    ticker: str
    company_name: str
    stock_price: float
    expiration_date_call: str
    expiration_date_put: str
    strike_price_call: float
    strike_price_put: float
    premium_call: float
    premium_put: float
    cost_call: float
    cost_put: float
    upper_breakeven: float
    lower_breakeven: float
    breakeven_difference: float
    normalized_difference: float
    variability_ratio: float
    escape_ratio: float
    num_strangles_considered: int

    def calculate_variability_ratio(self, stock_sigma: float) -> None:
        if self.breakeven_difference == 0.0:
            self.variability_ratio = float('inf')
        else:
            self.variability_ratio = stock_sigma / self.breakeven_difference

    def calculate_escape_ratio(self) -> None:
        self.escape_ratio = min(
            abs(self.stock_price - self.upper_breakeven),
            abs(self.stock_price - self.lower_breakeven)
        ) / self.stock_price


class StrangleFinder:
    def __init__(self, market_data_client: MarketDataClient, force_coupled: bool = False):
        self.market_data_client = market_data_client
        self.force_coupled = force_coupled

    def find_balanced_strangle(self, ticker: str, market_open: bool) -> Optional[Strangle]:
        # Get current stock price estimate and make a strike price filter
        stock_price = self.market_data_client.get_stock_price(ticker, market_open)
        max_stock_price = 250.00
        min_stock_price = 75.0
        if stock_price is None or stock_price > max_stock_price or stock_price < min_stock_price:
            return None
        buffer_factor = 5.0
        strike_min = stock_price / buffer_factor
        strike_max = stock_price * buffer_factor

        # Do a volatility sanity check
        stock_sigma, stock_mu = self.market_data_client.stock_sigma_mu(ticker, days=30)
        max_fluctuation = 3.0
        if stock_sigma > max_fluctuation * stock_mu:
            return None

        # Make date strings that define our search range
        date_min = datetime.today() + timedelta(days=10)
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
            "premium.gte": 0.0,
            "premium.lte": 20.0
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
        contract_buying_fee = 0.53  # a brokerage dependent cost
        merged_df['strangle_costs'] = (
            merged_df['premium_call'] + merged_df['premium_put'] +
            2.0 * contract_buying_fee / 100.0
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
            lambda row: row['last_quote'].bid
            if 'last_quote' in row and row['last_quote'] is not None else None,
            axis=1
        )
        options_df.loc[:, 'ask'] = options_df.apply(
            lambda row: row['last_quote'].ask
            if 'last_quote' in row and row['last_quote'] is not None else None,
            axis=1
        )

        # Calculate the premium using bid-ask midpoint, falling back to last_trade or fair_market_value
        options_df.loc[:, 'premium'] = options_df.apply(
            lambda row: (row['bid'] + row['ask']) / 2.0
            if pd.notna(row['bid']) and pd.notna(row['ask'])
            else (
                row['last_trade'].price
                if 'last_trade' in row and row['last_trade'] is not None and
                row['last_trade'].price is not None
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

        # Sanity check: throw out suspicious premiums
        options_df.loc[:, 'suspicious_premium'] = options_df.apply(
            lambda row: row['premium'] < max(0, row['strike_price'] - stock_price)
            if row['contract_type'] == 'put'
            else row['premium'] < max(0, stock_price - row['strike_price']),
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


class ReportGenerator:
    def __init__(self, template_file: str):
        self.template_file = template_file

    def display_strangle(self, strangle: Strangle) -> None:
        # Check if any required fields are missing
        if not strangle:
            return

        # Display the strangle details
        print(f"{strangle.company_name} ({strangle.ticker}): ${strangle.stock_price:.2f}")
        print(f"Normalized breakeven difference: {strangle.normalized_difference:.3f}")
        print(f"Variability Ratio: {strangle.variability_ratio:.3f}")
        print(f"Escape Ratio: {strangle.escape_ratio:.3f}")
        print(f"Cost of strangle: ${strangle.cost_call + strangle.cost_put:.2f}")
        print(f"Contract pairs tried: {strangle.num_strangles_considered:,}")
        print(f"Call Expiration: {strangle.expiration_date_call}")
        print(f"Call strike: ${strangle.strike_price_call:.2f}")
        print(f"Call premium: ${strangle.cost_call / 100.0:.2f}")
        print(f"Put Expiration: {strangle.expiration_date_put}")
        print(f"Put strike: ${strangle.strike_price_put:.2f}")
        print(f"Put premium: ${strangle.cost_put / 100.0:.2f}")
        print(f"Upper breakeven: ${strangle.upper_breakeven:.3f}")
        print(f"Lower breakeven: ${strangle.lower_breakeven:.3f}")
        print(f"Breakeven difference: ${strangle.breakeven_difference:.3f}\n")

    def generate_html_table(self, strangle: Strangle, position: int) -> Optional[str]:
        # Check if any of the required fields are NaN
        required_fields = [
            'company_name', 'ticker', 'expiration_date_call', 'expiration_date_put',
            'strike_price_call', 'strike_price_put', 'cost_call', 'cost_put',
            'upper_breakeven', 'lower_breakeven', 'breakeven_difference',
            'normalized_difference'
        ]

        if any(getattr(strangle, field) is None for field in required_fields):
            return None  # Skip this strangle if any required value is None

        # Generate the HTML with the company name (or fallback to ticker symbol)
        return ''.join([
            f'<div class="panel" data-position="{position}">',
            f'{strangle.company_name} ({strangle.ticker}): ${strangle.stock_price:.2f}<br>',
            f'Normalized Breakeven Difference: {strangle.normalized_difference:.3f}<br>',
            f'Escape ratio: {strangle.escape_ratio:.3f}<br>',
            f'Variability Ratio: {strangle.variability_ratio:.3f}<br>',
            f'Cost of strangle: ${strangle.cost_call + strangle.cost_put:.2f}<br>',
            f'Contract pairs tried: {strangle.num_strangles_considered:,}<br>',
            f'Call expiration: {strangle.expiration_date_call}<br>',
            f'Call strike: ${strangle.strike_price_call:.2f}<br>',
            f'Call premium: ${strangle.cost_call / 100.0:.2f}<br>',
            f'Put expiration: {strangle.expiration_date_put}<br>',
            f'Put strike: ${strangle.strike_price_put:.2f}<br>',
            f'Put premium: ${strangle.cost_put / 100.0:.2f}<br>',
            f'Upper breakeven: ${strangle.upper_breakeven:.3f}<br>',
            f'Lower breakeven: ${strangle.lower_breakeven:.3f}<br>',
            f'Breakeven difference: ${strangle.breakeven_difference:.3f}',
            '</div>'
        ])

    def write_reports(self, results: List[Strangle], execution_details: dict) -> None:
        # Try to read the template file and handle the case where the file is not found
        try:
            with open(self.template_file, 'r') as file:
                soup = BeautifulSoup(file, 'html.parser')
        except FileNotFoundError:
            print(f"Error: Template file '{self.template_file}' not found. Aborting report generation.")
            return  # Exit the function if the template file is not found

        # Extract execution details
        num_tickers_processed = execution_details.get('num_tickers_processed')
        num_strangles_considered = execution_details.get('num_strangles_considered')
        execution_time = execution_details.get('execution_time')
        execution_time_per_ticker = execution_details.get('execution_time_per_ticker')

        # Generate the current date in the desired format
        current_date = datetime.now().strftime("%A, %d %B, %Y")  # Example: "Sunday, 6 October, 2024"

        # Create a wide header panel that spans all columns and includes the current date
        header_panel = (
            f'{current_date}: '
            f'Processed {num_tickers_processed} tickers. '
            f'Considered {num_strangles_considered:,} contract pairs. '
            f'Finished in {execution_time/60.0:.0f} minutes, or '
            f'{execution_time_per_ticker:.0f} seconds per ticker.'
        )

        # Find the header panel and insert the content
        header_div = soup.find("div", {"class": "header", "data-position": "header"})
        if header_div:
            header_div.clear()  # Clear any existing content
            header_div.append(BeautifulSoup(header_panel, 'html.parser'))

        # Sort the results
        filtered_results = [
            x for x in results
            if (
                x.cost_call is not None and
                x.cost_put is not None and
                x.normalized_difference is not None and
                x.num_strangles_considered is not None
            )
        ]

        sorted_results = sorted(
            filtered_results,
            key=lambda x: (
                x.normalized_difference,   # First priority (ascending)
                -x.variability_ratio,      # Second priority (descending)
                -x.num_strangles_considered,  # Third priority (descending)
                x.cost_call + x.cost_put,  # Fourth priority (ascending)
            )
        )

        # Generate all the HTML content once
        all_results = [
            result_html for idx, result in enumerate(sorted_results)
            if (result_html := self.generate_html_table(result, idx + 1)) is not None
        ]

        # Get the current time and format it for the filename
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f'summary_report_{stamp}.html'
        full_output_file = f'full_report_{stamp}.html'

        # Find the grid container
        grid_container = soup.find("div", class_="grid-container")

        # Replace the top 8 panels (or fewer if there are not enough results)
        top_8_results = all_results[:8]  # Use the first 8 panels
        for idx, result in enumerate(top_8_results):
            data_position = idx + 1  # Data positions for panels are 1-indexed
            panel = grid_container.find("div", {"data-position": str(data_position)})
            if panel:
                new_content = BeautifulSoup(result, 'html.parser').div.decode_contents()  # Extract inner content
                panel.clear()  # Clear any existing content
                panel.append(BeautifulSoup(new_content, 'html.parser'))  # Insert the new content

        # Write the top 8 report to file
        with open(output_file, 'w') as file:
            file.write(str(soup))

        # Only create the full report if there are more than 8 panels
        if len(all_results) > 8:
            # Add the remaining results to the grid
            for idx, result in enumerate(all_results[8:], start=8):  # Continue from the 9th result
                new_panel = soup.new_tag("div", **{'class': 'panel', 'data-position': str(idx + 1)})
                new_content = BeautifulSoup(result, 'html.parser').div.decode_contents()  # Extract inner content
                new_panel.append(BeautifulSoup(new_content, 'html.parser'))  # Append the content
                grid_container.append(new_panel)

            # Write the full report to file
            with open(full_output_file, 'w') as file:
                file.write(str(soup))


class MainApplication:
    def __init__(self):
        self.market_data_client = MarketDataClient(api_key=os.getenv("POLYGONIO_API_KEY"))
        self.strangle_finder = StrangleFinder(market_data_client=self.market_data_client)
        self.report_generator = ReportGenerator(template_file='template_report.html')

    def load_tickers(self, collections_to_include: List[str]) -> List[str]:
        # Load tickers from the tickers.json file
        with open('tickers.json', 'r') as f:
            tickers_data = json.load(f)

        # Initialize an empty set to store tickers and avoid duplicates
        all_tickers = set()

        # Loop through each collection and add the tickers to the set
        for collection in collections_to_include:
            all_tickers.update(tickers_data[collection])

        # Sort the combined tickers alphabetically
        tickers = sorted(all_tickers)
        return tickers

    def process_ticker(self, ticker: str, market_open: bool) -> Optional[Strangle]:
        strangle = self.strangle_finder.find_balanced_strangle(ticker, market_open)
        return strangle

    def run(self):
        # Start the timer
        start_time = time.time()

        # Define the collections you want to include
        collections_to_include = [
            # '1_tickers',
            # '5_tickers',
             '25_tickers',
            # '100_tickers',
            # 'sp500_tickers',
            # 'russell1000_tickers',
            #'nyse_tickers',
            #'nasdaq_tickers'
        ]

        tickers = self.load_tickers(collections_to_include)

        # Calculate the total number of tickers and estimated time
        num_tickers = len(tickers)
        seconds_per_ticker = 0.88
        estimated_time_seconds = num_tickers * seconds_per_ticker

        # Calculate the current time and the completion time
        current_time = datetime.now()
        completion_time = current_time + timedelta(seconds=estimated_time_seconds)

        # Print a descriptive summary with the expected completion time
        print(f"Using collections: {', '.join(collections_to_include)}\n")
        print(
            f"We will process {num_tickers} unique tickers "
            f"and will finish around {completion_time.strftime('%H:%M')} "
            f"({completion_time.strftime('%Y-%m-%d')}).\n"
        )

        # Get market status (affects pricing estimate used)
        market_open = self.market_data_client.is_market_open()

        # Initialize results storage
        results = []
        num_tickers_processed = 0
        num_strangles_considered = 0

        # Main loop over tickers
        for ticker in tickers:
            num_tickers_processed += 1
            strangle = self.process_ticker(ticker, market_open)

            if strangle is None:
                print(f"{ticker}: Nothing interesting.\n")
            else:
                num_strangles_considered += strangle.num_strangles_considered

                # Only put interesting results into reports or output
                max_normalized_difference = 0.06
                if strangle.normalized_difference < max_normalized_difference:
                    results.append(strangle)
                    self.report_generator.display_strangle(strangle)
                else:
                    print(f"{ticker}: Nothing interesting.\n")

        # Calculate execution time
        execution_time = time.time() - start_time
        execution_time_per_ticker = execution_time / len(tickers)

        # Prepare execution details for the report
        execution_details = {
            'num_tickers_processed': num_tickers_processed,
            'num_strangles_considered': num_strangles_considered,
            'execution_time': execution_time,
            'execution_time_per_ticker': execution_time_per_ticker
        }

        # Write reports
        self.report_generator.write_reports(results, execution_details)

        # Print summary
        print(f"Number of tickers processed: {num_tickers_processed}")
        print(f"Number of contract pairs tried: {num_strangles_considered:,}")
        print(f"Execution time: {execution_time:.2f} seconds")
        print(f"Execution time per ticker: {execution_time_per_ticker:.2f} seconds\n")


if __name__ == "__main__":
    if '--profile' in sys.argv:
        import cProfile
        cProfile.run('MainApplication().run()', 'profile_output.prof')
    else:
        MainApplication().run()
