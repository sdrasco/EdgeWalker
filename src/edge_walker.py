import pandas as pd
import time
import os
import json
from polygon import RESTClient
from polygon.rest.models import TickerSnapshot
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

def find_balanced_strangle(ticker, force_coupled=False):
    # Initialize the RESTClient with API key
    polygonio_api_key = os.getenv("POLYGONIO_API_KEY")
    client = RESTClient(api_key=polygonio_api_key)

    # Limit strike prices within a buffer_factor of current stock price estimate
    stock_price = get_stock_price(client, ticker)
    max_stock_price = 150.00
    if stock_price is None or stock_price > max_stock_price:
        return None
    buffer_factor = 2.0
    strike_min = stock_price / buffer_factor
    strike_max = stock_price * buffer_factor
    
    # Make date strings that define our search range
    date_min = datetime.today() + timedelta(days=7)
    date_max = date_min + timedelta(days=90)
    date_min = date_min.strftime('%Y-%m-%d')
    date_max = date_max.strftime('%Y-%m-%d')

    # Get the filtered set of options chains
    options_chain = []
    for option in client.list_snapshot_options_chain(
        ticker,
        params={
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
            "open_interest.gte": 10,
            "volume.gte": 50,
            "premium.gte": 0.0,
            "premium.lte":5.0
        }
    ):
        options_chain.append(option)

    # Get the company name using the Polygon API
    try:
        ticker_details = client.get_ticker_details(ticker)
        if ticker_details and ticker_details.name:
            # Limit the number of words in the company name
            max_words = 3
            company_name = ' '.join(ticker_details.name.split()[:max_words])
        else:
            company_name = strangle["ticker"]
    except Exception as e:
        print(f"Warning: Could not fetch company name for {ticker}: {e}")
        company_name = ""

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
            spread = abs(ask - bid)  # Calculate bid-ask spread
        else:
            premium = (contract.last_trade.price if contract.last_trade else contract.fair_market_value)
            spread = None

        if premium is not None:
            if details.contract_type == 'call':
                calls.append({'strike': strike, 'premium': premium, 'expiration': expiration, 'bid': bid, 'ask': ask, 'spread': spread})
            elif details.contract_type == 'put':
                puts.append({'strike': strike, 'premium': premium, 'expiration': expiration, 'bid': bid, 'ask': ask, 'spread': spread})

    # Initialize best strangle found
    best_strangle = {
        'company_name': company_name,
        'ticker': ticker,
        'stock_price': stock_price,
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

        # Get the call and put strike prices and premiums
        call_strike = call['strike']
        call_premium = call['premium']

        # sanity check the premium 
        suspicious_premium = call_premium < max(0, stock_price - call_strike)

        # apply some skipping filters
        max_spread_factor = 0.2
        any_None = call['spread'] is None or call['bid'] is None or call['ask'] is None
        if (
            any_None or
            call_premium == 0 or
            call['bid'] == 0 or
            call['ask'] == 0 or
            call['spread'] > max_spread_factor * call_premium or
            suspicious_premium
        ):
            calls.remove(call)
            continue  # Skip it

        for put in puts:

            # Get the put strike prices and premiums
            put_strike = put['strike']
            put_premium = put['premium']

            # sanity check the premium 
            suspicious_premium = put_premium < max(0, stock_price - put_strike)

            # apply some skipping filters
            any_None = put['spread'] is None or put['bid'] is None or put['ask'] is None
            if (
                any_None or
                put_premium == 0 or
                put['bid'] == 0 or
                put['ask'] == 0 or
                put['spread'] > max_spread_factor * put_premium or
                suspicious_premium
            ):
                puts.remove(put)
                continue  # Skip it

            # Apply the force_coupled flag: only process pairs with matching expiration dates if force_coupled is True
            if force_coupled and call['expiration'] != put['expiration']:
                continue  # Skip if expirations don't match when forcing coupled expirations

            # update the strangles considered counter
            num_strangles_considered += 1

            # Calculate the upper and lower breakeven points
            contract_buying_fee = 0.53 # adjust to the fees you encounter when buying option contracts 
            strangle_costs = call_premium + put_premium + 2.0*contract_buying_fee
            upper_breakeven = call_strike + strangle_costs
            lower_breakeven = put_strike - strangle_costs

            # Calculate the breakeven difference
            breakeven_difference = abs(upper_breakeven - lower_breakeven)

            # Calculate the average strike price for normalization
            average_strike_price = 0.5 * (call_strike + put_strike)

            # Calculate the normalized breakeven difference (dimensionless)
            normalized_difference = breakeven_difference / average_strike_price

            # Calculate the cost of buying the call and put options
            cost_call = call_premium * 100.0  # Multiply by 100 to get cost in dollars
            cost_put = put_premium * 100.0    # Multiply by 100 to get cost in dollars

            # If this strangle has a smaller normalized breakeven difference, update best_strangle
            if normalized_difference < best_strangle['normalized_difference']:
                best_strangle = {
                    'company_name': company_name,
                    'ticker': ticker,
                    'stock_price': stock_price,
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

def is_market_open(client):
    try:
        # Fetch market status
        result = client.get_market_status()

        # Access the 'market' attribute directly from the MarketStatus object
        return result.market == 'open'
    except Exception as e:
        print(f"Warning: Error fetching market status: {e}")
        return False

def get_stock_price(client, ticker):
    try:
        # Check if the market is open
        market_open = is_market_open(client)

        # Fetch snapshot for the provided ticker
        snapshot = client.get_snapshot_all("stocks", [ticker])

        if snapshot and isinstance(snapshot[0], TickerSnapshot):
            if market_open and snapshot[0].min:
                # If the market is open, use min.close (minute-level data)
                return snapshot[0].min.close
            elif not market_open and snapshot[0].prev_day:
                # If the market is closed, use prev_day.close
                return snapshot[0].prev_day.close

        print(f"Warning: No valid price data available for {ticker}.")
        return None

    except Exception as e:
        print(f"Warning: Error fetching stock price for {ticker}: {e}")
        return None

def display_strangle(best_strangle):

    # Check if best_strangle is None first
    if not best_strangle:
        return

    if best_strangle and (best_strangle['call_strike'] is None or best_strangle['put_strike'] is None):
        print(f"No valid strangle found for {best_strangle['ticker']}\n")
        return
    
    # Display the best strangle details
    print(f"{best_strangle['company_name']} ({best_strangle['ticker']}): ${best_strangle['stock_price']:.2f}")
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
        'company_name',
        'ticker', 'call_expiration', 'put_expiration', 'call_strike', 'put_strike',
        'cost_call', 'cost_put', 'upper_breakeven', 'lower_breakeven',
        'breakeven_difference', 'normalized_difference'
    ]
    
    if any(strangle[key] is None for key in required_keys):
        return None  # Skip this strangle if any required value is None


    # Generate the HTML with the company name (or fallback to ticker symbol)
    return ''.join([
        f'<div class="panel" data-position="{position}">',
        f'{strangle["company_name"]} ({strangle["ticker"]}): ${strangle["stock_price"]:.2f}<br>',
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

def write_reports(results, execution_details):

    # define template location
    template_file = 'template_report.html'

    # Try to read the template file and handle the case where the file is not found
    try:
        with open(template_file, 'r') as file:
            soup = BeautifulSoup(file, 'html.parser')
    except FileNotFoundError:
        print(f"Error: Template file '{template_file}' not found. Aborting report generation.")
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

    # Sort the results first by 'normalized_difference' and then by total strangle price ('cost_call' + 'cost_put')
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
            -x['num_strangles_considered'],  # Second priority (descending)
            x['cost_call'] + x['cost_put'],  # Third priority (ascending)
        )
    )

    # Generate all the HTML content once
    all_results = [
        result_html for idx, result in enumerate(sorted_results) 
        if (result_html := generate_html_table(result, idx + 1)) is not None
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
        # Clear and re-populate the entire grid for the full report
        grid_container.clear()
        for idx, result in enumerate(all_results):
            new_panel = soup.new_tag("div", **{'class': 'panel', 'data-position': str(idx + 1)})
            new_content = BeautifulSoup(result, 'html.parser').div.decode_contents()  # Extract inner content
            new_panel.append(BeautifulSoup(new_content, 'html.parser'))  # Append the content
            grid_container.append(new_panel)

        # Re-insert the logo panel at position 5
        logo_panel = soup.new_tag("div", **{'class': 'panel', 'id': 'logo', 'data-position': 'logo'})
        logo_img = soup.new_tag("img", src="EdgeWalker.png", alt="Edge Walker Logo")
        logo_panel.append(logo_img)
        grid_container.insert(4, logo_panel)  # Insert at the fifth position

        # Write the full report to file
        with open(full_output_file, 'w') as file:
            file.write(str(soup))

# main exectution
def main():
    # Start the timer
    start_time = time.time()

    # Load tickers from the tickers.json file
    with open('tickers.json', 'r') as f:
        tickers_data = json.load(f)

    # Choose the list of tickers you want to use
    ticker_collection = 'sp500_tickers'
    tickers = sorted(set(tickers_data[ticker_collection]))

    # initialize results storage
    results = []  
    num_tickers_processed = 0
    num_strangles_considered = 0

    # Main loop over tickers
    for ticker in tickers:
        num_tickers_processed += 1
        strangle = find_balanced_strangle(ticker)

        if strangle is not None:
            num_strangles_considered += strangle.get('num_strangles_considered', 0)
            results.append(strangle)
            display_strangle(strangle)

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
    main()
