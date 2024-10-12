import numpy as np
import pandas as pd
import time
import os
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Replace 'polygon' client with direct HTTP requests using aiohttp

async def async_is_market_open(session, api_key, semaphore):
    async with semaphore:
        try:
            url = 'https://api.polygon.io/v1/marketstatus/now'
            params = {'apiKey': api_key}
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    print(f"Error fetching market status: HTTP {resp.status}")
                    return False
                data = await resp.json()
                return data.get('market') == 'open'
        except Exception as e:
            print(f"Error fetching market status: {e}")
            return False

async def async_get_stock_price(session, ticker, market_open, api_key, semaphore):
    async with semaphore:
        try:
            url = f'https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}'
            params = {'apiKey': api_key}
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    print(f"Error fetching stock price for {ticker}: HTTP {resp.status}")
                    return None
                data = await resp.json()
                if 'ticker' in data and data['ticker']:
                    snapshot = data['ticker']
                    if market_open and 'min' in snapshot and 'c' in snapshot['min']:
                        # If the market is open, use min.c (minute-level data)
                        return snapshot['min']['c']
                    elif not market_open and 'prevDay' in snapshot and 'c' in snapshot['prevDay']:
                        # If the market is closed, use prevDay.c
                        return snapshot['prevDay']['c']
                print(f"No valid price data available for {ticker}.\n")
                return None
        except Exception as e:
            print(f"Error fetching stock price for {ticker}: {e}")
            return None

async def async_stock_sigma_mu(session, ticker, days, api_key, semaphore):
    async with semaphore:
        try:
            end_date = datetime.today()
            start_date = end_date - timedelta(days=days)
            from_ = start_date.strftime('%Y-%m-%d')
            to_ = end_date.strftime('%Y-%m-%d')
            url = f'https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day/{from_}/{to_}'
            params = {'adjusted': 'true', 'sort': 'asc', 'limit': '120', 'apiKey': api_key}
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    print(f"Error fetching historical prices for {ticker}: HTTP {resp.status}")
                    return 0.0, 0.0
                data = await resp.json()
                if 'results' in data and data['results']:
                    closing_prices = [result['c'] for result in data['results']]
                    fluctuation = np.std(closing_prices)
                    mean_price = np.mean(closing_prices)
                    return fluctuation, mean_price
                else:
                    print(f"No price data available for {ticker} in the last {days} days.")
                    return 0.0, 0.0
        except Exception as e:
            print(f"Error fetching historical prices for {ticker}: {e}")
            return 0.0, 0.0

async def async_get_options_chain(session, ticker, params, api_key, semaphore):
    async with semaphore:
        try:
            url = 'https://api.polygon.io/v3/reference/options/contracts'
            # Add underlying_ticker to params
            params['underlying_ticker'] = ticker
            params['apiKey'] = api_key
            options_chain = []
            while True:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        print(f"Error fetching options chain for {ticker}: HTTP {resp.status}")
                        return []
                    data = await resp.json()
                    if 'results' in data and data['results']:
                        options_chain.extend(data['results'])
                    if data.get('next_url'):
                        url = data['next_url']
                        params = {}  # next_url already contains the API key
                    else:
                        break
            return options_chain
        except Exception as e:
            print(f"Error fetching options chain for {ticker}: {e}")
            return []

async def async_get_ticker_details(session, ticker, api_key, semaphore):
    async with semaphore:
        try:
            url = f'https://api.polygon.io/v3/reference/tickers/{ticker}'
            params = {'apiKey': api_key}
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    print(f"Error fetching ticker details for {ticker}: HTTP {resp.status}")
                    return None
                data = await resp.json()
                if 'results' in data:
                    return data['results']
                else:
                    print(f"No details found for {ticker}")
                    return None
        except Exception as e:
            print(f"Error fetching ticker details for {ticker}: {e}")
            return None

def filter_options(options_df, stock_price, max_spread_factor=0.5):
    # This function remains mostly unchanged, as it doesn't make any API calls
    options_df['premium'] = options_df['greeks']['mid_iv']  # Adjust according to actual data
    # ... rest of your filtering logic ...
    # Return the filtered DataFrame
    return options_df

async def find_balanced_strangle(session, ticker, market_open, api_key, semaphore, force_coupled=False):

    # get current stock price estimate and make a strike price filter
    stock_price = await async_get_stock_price(session, ticker, market_open, api_key, semaphore)
    max_stock_price = 250.00
    min_stock_price = 75.0
    if stock_price is None or stock_price > max_stock_price or stock_price < min_stock_price:
        return None
    buffer_factor = 5.0
    strike_min = stock_price / buffer_factor
    strike_max = stock_price * buffer_factor

    # do a volatility sanity check
    stock_sigma, stock_mu = await async_stock_sigma_mu(session, ticker, days=30, api_key=api_key, semaphore=semaphore)
    max_fluctuation = 3.0
    if stock_sigma > max_fluctuation * stock_mu:
        return None

    # Make date strings that define our search range
    date_min = datetime.today() + timedelta(days=10)
    date_max = date_min + timedelta(days=120)
    date_min = date_min.strftime('%Y-%m-%d')
    date_max = date_max.strftime('%Y-%m-%d')

    # Build the params dictionary
    params = {
        "expiration_date.gte": date_min,
        "expiration_date.lte": date_max,
        "strike_price.gte": strike_min,
        "strike_price.lte": strike_max,
        "contract_type": "call,put",
        "exercise_style": "american",
        "contract_size": 100,
        "option_type": "equity",
        "market": "options",
        "type": "standard",
        "open_interest.gte": 1,
        "volume.gte": 5,
        "premium.gte": 0.0,
        "premium.lte": 20.0
    }

    # Pull the option chain for this ticker
    options_chain = await async_get_options_chain(session, ticker, params, api_key, semaphore)

    # Convert options_chain to pandas DataFrame
    options_df = pd.DataFrame(options_chain)

    # Check if 'contract_type' column exists
    if 'contract_type' not in options_df.columns:
        return None

    # Extract calls and puts
    calls_df = options_df[options_df['contract_type'] == 'call'].copy()
    puts_df = options_df[options_df['contract_type'] == 'put'].copy()

    # Clean the lists of call and put contracts
    calls_df = filter_options(calls_df, stock_price)
    puts_df = filter_options(puts_df, stock_price)

    # Create a cartesian product of all combinations of calls and puts
    merged_df = calls_df.assign(key=1).merge(puts_df.assign(key=1), on='key', suffixes=('_call', '_put')).drop('key', axis=1)

    # Apply the force_coupled flag if necessary
    if force_coupled:
        merged_df = merged_df[merged_df['expiration_date_call'] == merged_df['expiration_date_put']]

    # Calculate the strangle costs
    contract_buying_fee = 0.53  # a brokerage dependent cost
    merged_df['strangle_costs'] = merged_df['premium_call'] + merged_df['premium_put'] + 2.0 * contract_buying_fee / 100.0

    # Calculate the upper and lower breakeven points
    merged_df['upper_breakeven'] = merged_df['strike_price_call'] + merged_df['strangle_costs']
    merged_df['lower_breakeven'] = merged_df['strike_price_put'] - merged_df['strangle_costs']

    # Calculate the breakeven difference
    merged_df['breakeven_difference'] = (merged_df['upper_breakeven'] - merged_df['lower_breakeven']).abs()

    # Calculate the average strike price for normalization
    merged_df['average_strike_price'] = 0.5 * (merged_df['strike_price_call'] + merged_df['strike_price_put'])

    # Calculate the normalized breakeven difference
    merged_df['normalized_difference'] = merged_df['breakeven_difference'] / merged_df['average_strike_price']

    # Check if merged_df is empty or if 'normalized_difference' has all NaN values
    if merged_df.empty or merged_df['normalized_difference'].isna().all():
        print(f"No valid strangles found for {ticker}.\n")
        return None

    # Get the single best strangle across all calls and puts
    best_strangle = merged_df.loc[merged_df['normalized_difference'].idxmin()].copy()

    # Restore the ticker and price fields on the output using .loc to avoid warnings
    best_strangle.loc['ticker'] = ticker
    best_strangle.loc['stock_price'] = stock_price

    # Add company name string to output
    try:
        ticker_details = await async_get_ticker_details(session, ticker, api_key, semaphore)
        if ticker_details and 'name' in ticker_details:
            # Limit the number of words in the company name
            max_words = 3
            company_name = ' '.join(ticker_details['name'].split()[:max_words])
        else:
            company_name = f"({ticker})"
    except Exception as e:
        print(f"Warning: Could not fetch company name for {ticker}: {e}")
        company_name = ""
    best_strangle.loc['company_name'] = company_name

    # Add total contract prices to output
    best_strangle.loc['cost_call'] = best_strangle['premium_call'] * 100.0
    best_strangle.loc['cost_put'] = best_strangle['premium_put'] * 100.0

    # Add variability ratio to output
    if best_strangle['breakeven_difference'] == 0.0:
        best_strangle.loc['variability_ratio'] = float('inf')
    else:
        best_strangle.loc['variability_ratio'] = stock_sigma / best_strangle['breakeven_difference']

    # put in the escape ratio: fractional price movement needed before strangle is profitable
    best_strangle.loc['escape_ratio'] = min(abs(stock_price - best_strangle["upper_breakeven"]),
        abs(stock_price - best_strangle["lower_breakeven"])) / stock_price

    # Add num_strangles_considered to output
    best_strangle.loc['num_strangles_considered'] = len(calls_df) * len(puts_df)

    # Return the best strangle (as a Series)
    return best_strangle

async def main():
    # Start the timer
    start_time = time.time()

    # Load tickers from the tickers.json file
    with open('tickers.json', 'r') as f:
        tickers_data = json.load(f)

    # Define the collections you want to include
    collections_to_include = [
        # '1_tickers',
        # '5_tickers',
        # '25_tickers',
        # '100_tickers',
        # 'sp500_tickers',
        # 'russell1000_tickers',
        'nyse_tickers',
        'nasdaq_tickers'
    ]

    # Initialize an empty set to store tickers and avoid duplicates
    all_tickers = set()

    # Loop through each collection and add the tickers to the set
    for collection in collections_to_include:
        all_tickers.update(tickers_data[collection])

    # Sort the combined tickers alphabetically
    tickers = sorted(all_tickers)

    # Calculate the total number of tickers and estimated time
    num_tickers = len(tickers)
    seconds_per_ticker = 0.88
    estimated_time_seconds = num_tickers * seconds_per_ticker

    # Calculate the current time and the completion time
    current_time = datetime.now()
    completion_time = current_time + timedelta(seconds=estimated_time_seconds)

    # Print a descriptive summary with the expected completion time
    print(f"Using collections: {', '.join(collections_to_include)}\n")
    print(f"We will process {num_tickers} unique tickers "
          f"and will finish around {completion_time.strftime('%H:%M')} "
          f"({completion_time.strftime('%Y-%m-%d')}).\n")

    # Initialize the API key
    api_key = os.getenv("POLYGONIO_API_KEY")

    # Create an asyncio Semaphore to limit concurrency
    semaphore = asyncio.Semaphore(5)  # Adjust based on rate limits

    # Initialize results storage
    results = []
    num_tickers_processed = 0
    num_strangles_considered = 0

    # Initialize the aiohttp session
    async with aiohttp.ClientSession() as session:
        # Get market status
        market_open = await async_is_market_open(session, api_key, semaphore)

        # Create tasks for each ticker
        tasks = [
            find_balanced_strangle(session, ticker, market_open, api_key, semaphore)
            for ticker in tickers
        ]

        # Run the tasks concurrently
        for future in asyncio.as_completed(tasks):
            strangle = await future
            num_tickers_processed += 1

            if strangle is not None and not strangle.empty:
                num_strangles_considered += strangle['num_strangles_considered']

                # only put interesting results into reports or output
                max_normalized_difference = 0.06
                if strangle["normalized_difference"] < max_normalized_difference:
                    results.append(strangle)
                    display_strangle(strangle)
                else:
                    print(f"{strangle['ticker']}: Nothing found.\n")

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
    write_reports(results, execution_details)

    # Print summary
    print(f"Number of tickers processed: {num_tickers_processed}")
    print(f"Number of contract pairs tried: {num_strangles_considered:,}")
    print(f"Execution time: {execution_time:.2f} seconds")
    print(f"Execution time per ticker: {execution_time_per_ticker:.2f} seconds\n")

if __name__ == "__main__":
    asyncio.run(main())