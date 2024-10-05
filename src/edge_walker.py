import pandas as pd
import time
import os
import json
from polygon import RESTClient
from datetime import datetime, timedelta

def find_balanced_strangle(ticker, force_coupled=False):
    # Initialize the RESTClient with API key
    polygonio_api_key = os.getenv("POLYGONIO_API_KEY")
    client = RESTClient(api_key=polygonio_api_key)

    # Create a dictionary to store all options
    options_chain = []
    
    # Calculate one week from today's date
    today = datetime.today()
    one_week_from_today = today + timedelta(weeks=1)
    one_week_from_today_str = one_week_from_today.strftime('%Y-%m-%d')
    
    # Fetch the options chain with no strike price filter, just by expiration date
    for option in client.list_snapshot_options_chain(
        ticker,
        params={
            "expiration_date.gte": one_week_from_today_str,
            "strike_price.gte": 0
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
    for call in calls:
        for put in puts:
            # Apply the force_coupled flag: only process pairs with matching expiration dates if force_coupled is True
            if force_coupled and call['expiration'] != put['expiration']:
                continue  # Skip if expirations don't match when forcing coupled expirations

            # Get the nearest expiration (earlier of the two)
            strangle_expiration = min(call['expiration'], put['expiration'])

            # Get the call and put strike prices and premiums
            call_strike = call['strike']
            call_premium = call['premium']
            put_strike = put['strike']
            put_premium = put['premium']

            # Skip anything with zero premium
            if call_premium == 0 or put_premium == 0:
                continue  # Skip 

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
                    'expiration': strangle_expiration
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
        'ticker', 'expiration', 'call_strike', 'put_strike',
        'cost_call', 'cost_put', 'upper_breakeven', 'lower_breakeven',
        'breakeven_difference', 'normalized_difference'
    ]
    
    if any(strangle[key] is None for key in required_keys):
        return None  # Skip this strangle if any required value is None

    # If all required values are present, proceed to generate HTML and return it as one compact line
    return ''.join([
        f'<div class="panel" data-position="{position}">',
        f'{strangle["ticker"]}<br>',
        f'Normalized Breakeven Difference: {strangle["normalized_difference"]:.3f}',
        f'Cost of strangle: ${strangle["cost_call"] + strangle["cost_put"]:.2f}<br>',
        f'Expiration: {strangle["expiration"]}<br>',
        f'Call strike: ${strangle["call_strike"]:.2f}<br>',
        f'Put strike: ${strangle["put_strike"]:.2f}<br>',
        f'Cost of call: ${strangle["cost_call"]:.2f}<br>',
        f'Cost of put: ${strangle["cost_put"]:.2f}<br>',
        f'Upper breakeven: ${strangle["upper_breakeven"]:.3f}<br>',
        f'Lower breakeven: ${strangle["lower_breakeven"]:.3f}<br>',
        f'Breakeven difference: ${strangle["breakeven_difference"]:.3f}<br>',
        '</div>'
    ])

# Start the timer
start_time = time.time()

# Load tickers from the tickers.json file
with open('tickers.json', 'r') as f:
    tickers_data = json.load(f)

# Choose the list of tickers you want to use (see tickers.json for what's on offer)
tickers = tickers_data['tickers_5']  

# Remove duplicates and sort alphabetically
tickers = sorted(set(tickers))

# initialize results storage
results = []  

# Initialize usage/resource counters
num_tickers_processed = 0
num_requests_sent = 0
num_html_panels_generated = 0

# Main loop over tickers
for ticker in tickers:
    num_tickers_processed += 1  # Increment the ticker count

    # Search for the best strangle for each ticker
    strangle = find_balanced_strangle(ticker)
    
    # Store the result
    results.append(strangle)
    
    # Increment the request count (assuming 1 request per ticker)
    num_requests_sent += 1
    
    # Display the result
    display_strangle(strangle)

# Sort the results first by 'normalized_difference' and then by total strangle price ('cost_call' + 'cost_put')
sorted_results = sorted(
    results, 
    key=lambda x: (x['normalized_difference'], x['cost_call'] + x['cost_put'])
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
filename = f"results_{tickers}_{timestamp}.txt"
with open(filename, 'w') as f:
    # Write the execution time details and counts as a header
    f.write(f"Number of tickers processed: {num_tickers_processed}\n")
    f.write(f"Number of requests sent to Polygon.io: {num_requests_sent}\n")
    f.write(f"Number of HTML panels generated: {num_html_panels_generated}\n")
    f.write(f"Execution time: {execution_time:.2f} seconds\n")
    f.write(f"Execution time per ticker: {execution_time_per_ticker:.2f} seconds\n\n")
    
    # Write the HTML panels
    f.write(final_html)

# display summary
print(f"Results written to {filename}")
print(f"Number of tickers processed: {num_tickers_processed}")
print(f"Number of requests sent to Polygon.io: {num_requests_sent}")
print(f"Number of HTML panels generated: {num_html_panels_generated}")
print(f"Execution time: {execution_time:.2f} seconds")
print(f"Execution time per ticker: {execution_time_per_ticker:.2f} seconds\n")
