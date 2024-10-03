import yfinance as yf
import pandas as pd
import time

# Function to calculate breakeven points and look for the best-balanced strangle
def find_balanced_strangle(ticker):
    # Fetch the options chain for the given ticker
    stock = yf.Ticker(ticker)
    
    # if you want all the possible dates
    expiration_dates = stock.options
    
    # if you only want the most recent
    # N = 4  
    # expiration_dates = stock.options[:N]
    
    # Store the best strangle found (with smallest normalized breakeven difference)
    best_strangle = {
        'call_strike': None,
        'put_strike': None,
        'call_premium': None,
        'put_premium': None,
        'upper_breakeven': None,
        'lower_breakeven': None,
        'breakeven_difference': float('inf'),
        'normalized_difference': float('inf'),
        'cost_call': None,
        'cost_put': None,
        'expiration': None
    }
    
    # Loop over expiration dates
    for expiration in expiration_dates:
        options = stock.option_chain(expiration)
        
        calls = options.calls
        puts = options.puts
        
        # Iterate over all possible combinations of call and put
        for _, call in calls.iterrows():
            for _, put in puts.iterrows():
                Active = (call['bid'] != 0) and (call['ask'] != 0) and (put['bid'] != 0) and (put['ask'] != 0)
                if Active:
                    # Get the call and put strike prices and premiums
                    call_strike = call['strike']
                    call_premium = 0.5*(call['bid'] + call['ask'])
                    put_strike = put['strike']
                    put_premium = 0.5*(put['bid'] + put['ask'])
                    
                    # Calculate the upper and lower breakeven points
                    upper_breakeven = call_strike + call_premium + put_premium
                    lower_breakeven = put_strike - call_premium - put_premium
                    
                    # Calculate the breakeven difference
                    breakeven_difference = abs(upper_breakeven - lower_breakeven)
                    
                    # Calculate the average strike price for normalization
                    average_strike_price = 0.5*(call_strike + put_strike)
                    
                    # Calculate the normalized breakeven difference (dimensionless)
                    normalized_difference = breakeven_difference / average_strike_price
                    
                    # Calculate the cost of buying the call and put options
                    cost_call = call_premium * 100  # Multiply by 100 to get cost in dollars
                    cost_put = put_premium * 100    # Multiply by 100 to get cost in dollars
                    
                    # If this strangle has a smaller normalized breakeven difference, update best_strangle
                    if normalized_difference < best_strangle['normalized_difference']:
                        best_strangle = {
                            'call_strike': call_strike,
                            'put_strike': put_strike,
                            'call_premium': call_premium,
                            'put_premium': put_premium,
                            'upper_breakeven': upper_breakeven,
                            'lower_breakeven': lower_breakeven,
                            'breakeven_difference': breakeven_difference,
                            'normalized_difference': normalized_difference,
                            'cost_call': cost_call,
                            'cost_put': cost_put,
                            'expiration': expiration  
                        }
    
    # Return the best strangle found
    return best_strangle

def show_findings(best_strangle):
    # Print the results
    if best_strangle['call_strike']:
        print(f"{best_strangle['ticker']} Best Balanced Strangle Search result:")
        print(f"Expiration: {best_strangle['expiration']}")
        print(f"Call strike: {best_strangle['call_strike']:.2f} at premium: ${best_strangle['call_premium']:.2f}")
        print(f"Put strike: {best_strangle['put_strike']:.2f} at premium: ${best_strangle['put_premium']:.2f}")
        print(f"Cost of strangle: ${best_strangle['cost_call']+best_strangle['cost_put']:.2f}")
        print(f"Cost of call: ${best_strangle['cost_call']:.2f}")
        print(f"Cost of put: ${best_strangle['cost_put']:.2f}")
        print(f"Upper breakeven: ${best_strangle['upper_breakeven']:.3f}")
        print(f"Lower breakeven: ${best_strangle['lower_breakeven']:.3f}")
        print(f"Breakeven difference: ${best_strangle['breakeven_difference']:.3f}")
        print(f"Normalized breakeven difference: {best_strangle['normalized_difference']:.2f}\n")

# Start the timer
start_time = time.time()

# Make our list of stocks to search
tickers = ['AAPL', 'AMZN', 'GOOGL']

# Remove duplicates and sort alphabetically
tickers = sorted(set(tickers))

# Collect results in a list
results = []

# main loop to search for best ballanced strangles
for ticker in tickers:
    new_result = find_balanced_strangle(ticker)
    new_result['ticker'] = ticker  
    results.append(new_result)

# Filter out results with no valid strangle
valid_results = [r for r in results if r['call_strike']]
invalid_results = [r for r in results if not r['call_strike']]

# Sort the valid results by normalized breakeven difference
sorted_results = sorted(valid_results, key=lambda x: x['normalized_difference'])

# Display any valid results
if valid_results:
    for result in valid_results:
        show_findings(result)

# Display any invalid results
invalid_tickers = [r['ticker'] for r in invalid_results]
if invalid_results:
    print(f"Didn't find any suitable put/call contract pairs for: {invalid_tickers}\n")

# display the execution time taken
execution_time = time.time() - start_time
print(f"Execution time: {execution_time:.2f} seconds\n")
print(f"Average time per ticker: {execution_time/len(tickers):.2f} seconds\n")
