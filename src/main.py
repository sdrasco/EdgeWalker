# main.py

import os
import sys
import time
import json
from datetime import datetime, timedelta

# Adjust the Python path to ensure modules can be imported when running main.py directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import classes from the EdgeWalker package (src directory)
from market_data_client import MarketDataClient
from strangle_finder import StrangleFinder
from report_generator import ReportGenerator

def main():
    # Start the timer
    start_time = time.time()

    # Load tickers from the tickers.json file
    tickers_file = os.path.join(os.path.dirname(__file__), 'tickers.json')
    with open(tickers_file, 'r') as f:
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
    print(
        f"We will process {num_tickers} unique tickers "
        f"and will finish around {completion_time.strftime('%H:%M')} "
        f"({completion_time.strftime('%Y-%m-%d')}).\n"
    )

    # Initialize the MarketDataClient
    polygonio_api_key = os.getenv("POLYGONIO_API_KEY")
    market_data_client = MarketDataClient(api_key=polygonio_api_key)

    # Initialize the StrangleFinder
    strangle_finder = StrangleFinder(market_data_client=market_data_client)

    # Initialize the ReportGenerator
    report_generator = ReportGenerator(template_file='template_report.html')

    # Get market status (affects pricing estimate used)
    market_open = market_data_client.is_market_open()

    # Initialize results storage
    results = []
    num_tickers_processed = 0
    num_strangles_considered = 0

    # Main loop over tickers
    for ticker in tickers:
        num_tickers_processed += 1
        strangle = strangle_finder.find_balanced_strangle(ticker, market_open)

        if strangle is None:
            print(f"{ticker}: Nothing interesting.\n")
        else:
            num_strangles_considered += strangle.num_strangles_considered

            # Only put interesting results into reports or output
            max_normalized_difference = 0.06
            if strangle.normalized_difference < max_normalized_difference:
                results.append(strangle)
                report_generator.display_strangle(strangle)
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
    report_generator.write_reports(results, execution_details)

    # Print summary
    print(f"Number of tickers processed: {num_tickers_processed}")
    print(f"Number of contract pairs tried: {num_strangles_considered:,}")
    print(f"Execution time: {execution_time:.2f} seconds")
    print(f"Execution time per ticker: {execution_time_per_ticker:.2f} seconds\n")

if __name__ == "__main__":
    if '--profile' in sys.argv:
        import cProfile
        cProfile.run('main()', 'profile_output.prof')
    else:
        main()