import pandas as pd
import time
import os
import json
from polygon import RESTClient
from datetime import datetime
from dateutil.relativedelta import relativedelta

def find_balanced_strangle(ticker, force_coupled=False):
    # Initialize the RESTClient with API key
    polygonio_api_key = os.getenv("POLYGONIO_API_KEY")
    client = RESTClient(api_key=polygonio_api_key)

    # Create a dictionary to store all options
    options_chain = []
    
    # Calculate one week from today's date
    today = datetime.today()
    one_week_from_today = today + relativedelta(weeks=1)
    one_month_from_today = today + relativedelta(months=1)
    one_year_from_today = today + relativedelta(years=1)
    one_week_from_today_str = one_week_from_today.strftime('%Y-%m-%d')
    one_month_from_today_str = one_month_from_today.strftime('%Y-%m-%d')
    one_year_from_today_str = one_year_from_today.strftime('%Y-%m-%d')

    # Limit strike prices within a generous buffer_factor the last closing stock price
    try:
        last_close_price = client.get_previous_close_agg(ticker)[0].close
    except Exception as e:
        print(f"Warning: No stock price data for {ticker}: {e}. Moving to next ticker.\n")
        return None  # Skip this ticker if we can't get any price data
    buffer_factor = 3.0
    strike_min = last_close_price / buffer_factor
    strike_max = last_close_price * buffer_factor
    
    # Fetch the options chains with some filters
    for option in client.list_snapshot_options_chain(
        ticker,
        params={
            "expiration_date.gte": one_week_from_today_str,
            "expiration_date.lte": one_year_from_today_str,
            "strike_price.gte": strike_min,
            "strike_price.lte": strike_max,
            "contract_type.in": "call,put"
        }
    ):
        options_chain.append(option)

    # Organize calls and puts by expiration date
    calls = []
    puts = []
    for contract in options_chain:
        details = contract.details
        expiration = details.expiration_date
        strike = details.strike_price
        # Use the price from last_trade or fallback to fair_market_value
        bid = contract.last_quote.bid if contract.last_quote else None
        ask = contract.last_quote.ask if contract.last_quote else None
        if bid is not None and ask is not None:
            premium = (bid + ask) / 2  # Bid-ask midpoint
        else:
            premium = (contract.last_trade.price if contract.last_trade else contract.fair_market_value)

        if premium is not None:
            if details.contract_type == 'call':
                calls.append({'strike': strike, 'premium': premium, 'expiration': expiration})
            elif details.contract_type == 'put':
                puts.append({'strike': strike, 'premium': premium, 'expiration': expiration})

    # Store the best strangle found
    best_strangle = {
        'ticker': ticker,
        'last_close': last_close_price,
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
                    'last_close': last_close_price,
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
    if best_strangle and (best_strangle['call_strike'] is None or best_strangle['put_strike'] is None):
        print(f"No valid strangle found for {best_strangle['ticker']}\n")
        return
    
    # Display the best strangle details
    print(f"{best_strangle['ticker']}: ${best_strangle['last_close']:.2f}")
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
    
def generate_html_table(strangle, position):
    # Check if any of the key values are None, return None if so
    required_keys = [
        'ticker', 'call_expiration','put_expiration', 'call_strike', 'put_strike',
        'cost_call', 'cost_put', 'upper_breakeven', 'lower_breakeven',
        'breakeven_difference', 'normalized_difference'
    ]
    
    if any(strangle[key] is None for key in required_keys):
        return None  # Skip this strangle if any required value is None

    # If all required values are present, proceed to generate HTML and return it as one compact line
    return ''.join([
        f'<div class="panel" data-position="{position}">',
        f'{strangle["ticker"]}: ${strangle["last_close"]:.2f}<br>',
        f'Normalized Breakeven Difference: {strangle["normalized_difference"]:.3f}<br>',
        f'Cost of strangle: ${strangle["cost_call"] + strangle["cost_put"]:.2f}<br>',
        f'Contract pairs tried: {strangle["num_strangles_considered"]:,}<br>',
        f'Call expiration: {strangle["call_expiration"]}<br>',
        f'Call strike: ${strangle["call_strike"]:.2f}<br>',
        f'Call cost: ${strangle["cost_call"]:.2f}<br>',
        f'Put expiration: {strangle["put_expiration"]}<br>',
        f'Put strike: ${strangle["put_strike"]:.2f}<br>',
        f'Put cost: ${strangle["cost_put"]:.2f}<br>',
        f'Upper breakeven: ${strangle["upper_breakeven"]:.3f}<br>',
        f'Lower breakeven: ${strangle["lower_breakeven"]:.3f}<br>',
        f'Breakeven difference: ${strangle["breakeven_difference"]:.3f}',
        '</div>'
    ])

# Start the timer
start_time = time.time()

# Load tickers from the tickers.json file
with open('tickers.json', 'r') as f:
    tickers_data = json.load(f)

# Choose the list of tickers you want to use (see tickers.json for what's on offer)
ticker_collection = 'sp500_tickers'
#ticker_collection = '100_tickers'
#ticker_collection = '25_tickers'
#ticker_collection = '2_tickers'
tickers = tickers_data[ticker_collection]  

# Remove duplicates and sort alphabetically
tickers = sorted(set(tickers))

# initialize results storage
results = []  

# Initialize usage/resource counters
num_tickers_processed = 0
num_html_panels_generated = 0
num_strangles_considered = 0

# Main loop over tickers
for ticker in tickers:
    num_tickers_processed += 1  # Increment the ticker count

    # Search for the best strangle for each ticker
    strangle = find_balanced_strangle(ticker)
    if strangle and 'num_strangles_considered' in strangle:
        num_strangles_considered += strangle['num_strangles_considered']
    
    # Store the result
    results.append(strangle)
    
    # Display the result
    display_strangle(strangle)

# Sort the results first by 'normalized_difference' and then by total strangle price ('cost_call' + 'cost_put')
# Filter out entries where 'cost_call' or 'cost_put' or 'normalized_difference' or 'num_strangles_considered' is None
filtered_results = [
    x for x in results 
    if (x.get('cost_call') is not None and 
    x.get('cost_put') is not None and 
    x.get('normalized_difference') is not None and 
    x.get('num_strangles_considered') is not None)
]

sorted_results = sorted(
    filtered_results, 
    key=lambda x: (
        x['normalized_difference'],  # First priority (ascending)
        -x['num_strangles_considered'],  # Second priority (decending)
        x['cost_call'] + x['cost_put'],  # Third priority (ascending)
    )
)

# Generate HTML for each result
html_tables = []
for idx, strangle in enumerate(sorted_results, start=1):
    html_table = generate_html_table(strangle, idx)
    if html_table:  # Only append if the table is not None
        html_tables.append(html_table)
        num_html_panels_generated += 1  # Increment the HTML panel count

# Join the HTML tables into a single string for faster I/O
final_html = '\n\n'.join(html_tables)

# Calculate the execution time
execution_time = time.time() - start_time
execution_time_per_ticker = execution_time / len(tickers)

# Get the current time and format it for the filename
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# Write the execution details and final HTML to a file with a timestamp and tickers collection name in the filename
filename = f"results_{ticker_collection}_{timestamp}.txt"
with open(filename, 'w') as f:
    # Write the execution time details and counts as a header
    f.write(f"Number of tickers processed: {num_tickers_processed}\n")
    f.write(f"Number of contract pairs tried: {num_strangles_considered:,}\n")
    f.write(f"Number of HTML panels generated: {num_html_panels_generated}\n")
    f.write(f"Execution time: {execution_time:.2f} seconds\n")
    f.write(f"Execution time per ticker: {execution_time_per_ticker:.2f} seconds\n\n")
    
    # Write the HTML panels
    f.write(final_html)

# display summary
print(f"Results written to {filename}")
print(f"Number of tickers processed: {num_tickers_processed}")
print(f"Number of HTML panels generated: {num_html_panels_generated}")
print(f"Number of contract pairs tried: {num_strangles_considered:,}")
print(f"Execution time: {execution_time:.2f} seconds")
print(f"Execution time per ticker: {execution_time_per_ticker:.2f} seconds\n")
