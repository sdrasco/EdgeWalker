import asyncio
import aiohttp
import pandas as pd
import time
import os
import json
from polygon import RESTClient
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class RateLimiter:
    def __init__(self, max_calls, period=1):
        self._max_calls = max_calls
        self._period = period
        self._call_times = []

    async def acquire(self):
        now = time.monotonic()
        while len(self._call_times) >= self._max_calls:
            elapsed = now - self._call_times[0]
            if elapsed > self._period:
                self._call_times.pop(0)
            else:
                await asyncio.sleep(self._period - elapsed)
                now = time.monotonic()
        self._call_times.append(now)

async def fetch_data(session, url, params, rate_limiter):
    await rate_limiter.acquire()
    async with session.get(url, params=params) as response:
        response.raise_for_status()
        return await response.json()

async def fetch_options_chain(session, ticker, params, rate_limiter):
    url = f"https://api.polygon.io/v3/snapshot/options/{ticker}"
    return await fetch_data(session, url, params, rate_limiter)

async def fetch_previous_close(session, ticker, rate_limiter):
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/prev"
    polygonio_api_key = os.getenv("POLYGONIO_API_KEY")
    params = {"apiKey": polygonio_api_key}
    data = await fetch_data(session, url, params, rate_limiter)
    return data['results'][0]['c'] if 'results' in data and data['results'] else None

async def process_ticker(session, ticker, params, rate_limiter):
    options_chain_task = asyncio.create_task(fetch_options_chain(session, ticker, params, rate_limiter))
    previous_close_task = asyncio.create_task(fetch_previous_close(session, ticker, rate_limiter))
    options_chain, last_close_price = await asyncio.gather(options_chain_task, previous_close_task)

    options_chain_task = asyncio.create_task(fetch_options_chain(session, ticker, params, rate_limiter))
    options_chain = await options_chain_task
    print(f"Ticker: {ticker}, Number of options fetched: {len(options_chain.get('results', []))}")

    return ticker, options_chain, last_close_price

async def main(tickers, params, max_requests_per_second):
    rate_limiter = RateLimiter(max_calls=max_requests_per_second, period=1)
    tasks = []
    async with aiohttp.ClientSession() as session:
        for ticker in tickers:
            task = asyncio.create_task(process_ticker(session, ticker, params, rate_limiter))
            tasks.append(task)
        results = await asyncio.gather(*tasks)
    return results

def find_balanced_strangle(ticker, options_chain, last_close_price, force_coupled=False):
    buffer_factor = 3.0
    strike_min = last_close_price / buffer_factor
    strike_max = last_close_price * buffer_factor

    # Organize calls and puts by expiration date
    calls = []
    puts = []
    num_strangles_considered = 0

    for contract in options_chain.get('results', []):
        details = contract['details']
        expiration = details['expiration_date']
        strike = details['strike_price']
        contract_type = details['contract_type']

        # Use the price from last_trade or fallback to fair_market_value
        last_quote = contract.get('last_quote', {})
        bid = last_quote.get('bid')
        ask = last_quote.get('ask')
        last_trade = contract.get('last_trade', {})
        fair_market_value = contract.get('greeks', {}).get('delta')  # Placeholder for fair market value

        if bid is not None and ask is not None:
            premium = (bid + ask) / 2  # Bid-ask midpoint
        else:
            premium = last_trade.get('price') or fair_market_value

        if premium is not None:
            option_data = {'strike': strike, 'premium': premium, 'expiration': expiration}
            if contract_type == 'call':
                calls.append(option_data)
            elif contract_type == 'put':
                puts.append(option_data)

    # Store the best strangle found
    best_strangle = {
        'ticker': ticker,
        'call_strike': None,
        'put_strike': None,
        'call_premium': None,
        'put_premium': None,
        'call_expiration': None,
        'put_expiration': None,
        'upper_breakeven': None,
        'lower_breakeven': None,
        'breakeven_difference': float('inf'),
        'normalized_difference': float('inf'),
        'cost_call': None,
        'cost_put': None,
        'expiration': None
    }

    # Iterate over all possible combinations of call and put
    num_strangles_considered = 0
    for call in calls:
        for put in puts:

            # Apply the force_coupled flag: only process pairs with matching expiration dates if force_coupled is True
            if force_coupled and call['expiration'] != put['expiration']:
                continue  # Skip if expirations don't match when forcing coupled expirations

            # Get the call and put strike prices and premiums
            call_strike = call['strike']
            call_premium = call['premium']
            put_strike = put['strike']
            put_premium = put['premium']

            # Skip anything with zero premium
            if call_premium == 0 or put_premium == 0:
                continue  # Skip 

            # update the strangles considered counter
            num_strangles_considered += 1

            # Calculate the upper and lower breakeven points
            upper_breakeven = call_strike + call_premium + put_premium
            lower_breakeven = put_strike - call_premium - put_premium

            # Calculate the breakeven difference
            breakeven_difference = abs(upper_breakeven - lower_breakeven)

            # Calculate the average strike price for normalization
            average_strike_price = 0.5 * (call_strike + put_strike)

            # Calculate the normalized breakeven difference (dimensionless)
            normalized_difference = breakeven_difference / average_strike_price

            # Calculate the cost of buying the call and put options
            cost_call = call_premium * 100  # Multiply by 100 to get cost in dollars
            cost_put = put_premium * 100    # Multiply by 100 to get cost in dollars

            # If this strangle has a smaller normalized breakeven difference, update best_strangle
            if normalized_difference < best_strangle['normalized_difference']:
                best_strangle = {
                    'ticker': ticker,
                    'call_strike': call_strike,
                    'put_strike': put_strike,
                    'call_premium': call_premium,
                    'put_premium': put_premium,
                    'call_expiration': call['expiration'],
                    'put_expiration': put['expiration'],
                    'upper_breakeven': upper_breakeven,
                    'lower_breakeven': lower_breakeven,
                    'breakeven_difference': breakeven_difference,
                    'normalized_difference': normalized_difference,
                    'cost_call': cost_call,
                    'cost_put': cost_put,
                    'num_strangles_considered': num_strangles_considered
                }

    # Return the best strangle found
    return best_strangle

def display_strangle(best_strangle):
    if best_strangle['call_strike'] is None or best_strangle['put_strike'] is None:
        print(f"No valid strangle found for {best_strangle['ticker']}")
        return
    
    # Display the best strangle details
    print(f"{best_strangle['ticker']}: ")
    print(f"Normalized breakeven difference: {best_strangle['normalized_difference']:.3f}")
    print(f"Cost of strangle: ${best_strangle['cost_call'] + best_strangle['cost_put']:.2f}")
    print(f"Contract pairs tried: {best_strangle['num_strangles_considered']:,}")
    print(f"Call Expiration: {best_strangle['call_expiration']}")
    print(f"Put Expiration: {best_strangle['put_expiration']}")
    print(f"Call strike: {best_strangle['call_strike']:.2f}")
    print(f"Put strike: {best_strangle['put_strike']:.2f}")
    print(f"Cost of call: ${best_strangle['cost_call']:.2f}")
    print(f"Cost of put: ${best_strangle['cost_put']:.2f}")
    print(f"Upper breakeven: ${best_strangle['upper_breakeven']:.3f}")
    print(f"Lower breakeven: ${best_strangle['lower_breakeven']:.3f}")
    print(f"Breakeven difference: ${best_strangle['breakeven_difference']:.3f}\n")
    
# Set parameters
today = datetime.today()
one_week_from_today = today + timedelta(weeks=1)
one_year_from_today = today + relativedelta(years=1)
one_week_from_today_str = one_week_from_today.strftime('%Y-%m-%d')
one_year_from_today_str = one_year_from_today.strftime('%Y-%m-%d')
polygonio_api_key = os.getenv("POLYGONIO_API_KEY")
params = {
    "apiKey": polygonio_api_key,
    "expiration_date.gte": one_week_from_today_str,
    "expiration_date.lte": one_year_from_today_str,
    "limit": 1,
    "contract_type.in": "call,put"
}

# Load tickers from the tickers.json file
with open('tickers.json', 'r') as f:
    tickers_data = json.load(f)

# Choose the list of tickers you want to use (see tickers.json for what's on offer)
#ticker_collection = 'sp500_tickers'
#ticker_collection = '100_tickers'
#ticker_collection = '25_tickers'
ticker_collection = '2_tickers'
tickers = tickers_data[ticker_collection]  

# Remove duplicates and sort alphabetically
tickers = sorted(set(tickers))

# Run the event loop
max_requests_per_second = 15  # Polygon.io rate limits suggest this should be well below 100
loop = asyncio.get_event_loop()
results = loop.run_until_complete(main(tickers, params, max_requests_per_second))

# Process the results
for ticker, options_chain, last_close_price in results:
    if options_chain and last_close_price:
        strangle = find_balanced_strangle(ticker, options_chain, last_close_price)
        display_strangle(strangle)
    else:
        print(f"Data missing for {ticker}")