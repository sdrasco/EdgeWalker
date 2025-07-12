import os
import logging
import sys
import time
import json
import asyncio

# Adjust the Python path to ensure modules can be imported when running main.py directly
src_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(src_path)

# Import classes from the EdgeWalker package (src directory)
from market_data_client import MarketDataClient
from strangle_finder import StrangleFinder
from report_writer import ReportWriter

# Configure basic logging.  show warning or higher for external modules.
logging.basicConfig(
    level=logging.WARNING,  
    format='%(message)s'
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Show info level logger events for this module
logger.setLevel(logging.INFO)

async def main():  
    # Start the timer
    start_time = time.time()

    # Load tickers from the tickers.json file
    tickers_file = os.path.join(os.path.dirname(__file__), 'tickers.json')
    with open(tickers_file, 'r') as f:
        tickers_data = json.load(f)

    # Define the collections you want to include
    collections_to_include = [
        #'1_tickers',
        #'5_tickers',
        #'25_tickers',
        #'100_tickers',
        #'sp500_tickers',
        #'russell1000_tickers',
        #'nyse_tickers',
        #'nasdaq_tickers',
        'all_polygon'
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
    seconds_per_ticker = 0.0039
    estimated_time_seconds = num_tickers * seconds_per_ticker

    # Print a descriptive summary with the estimated time remaining
    logger.info(f"Using collections: {', '.join(collections_to_include)}\n")
    logger.info(
        f"We will process {num_tickers:,} unique tickers.\n"
        f"\nExpect {estimated_time_seconds:.0f} "
        f"to {3*estimated_time_seconds:.0f} seconds, "
        f"depending on API traffic, market status, etc.\n"
    )

    # Set a limit for the concurrent API requests.
    # Hard to know when you will break the limits.
    # Advice: start from 2 and build up.
    concurrent_requests = 50
    semaphore = asyncio.Semaphore(concurrent_requests) 

    # Initialize the MarketDataClient
    polygonio_api_key = os.getenv("POLYGONIO_API_KEY")
    market_data_client = MarketDataClient(api_key=polygonio_api_key)

    # Initialize the StrangleFinder
    strangle_finder = StrangleFinder(market_data_client=market_data_client)

    # Initialize results storage
    results = []
    num_tickers_processed = 0
    num_strangles_considered = 0

    # Main loop over tickers with asynchronous execution
    tasks = []
    for ticker in tickers:
        tasks.append(strangle_finder.find_balanced_strangle(ticker, semaphore=semaphore))

    # Process all tasks concurrently
    strangle_results = await asyncio.gather(*tasks)

    # After all the tasks complete, process the results
    for ticker, strangle in zip(tickers, strangle_results):
        num_tickers_processed += 1

        if strangle is not None:
            num_strangles_considered += strangle.num_strangles_considered

            # Only put interesting results into reports or output
            max_normalized_difference = 0.1  # Adjust as needed
            if strangle.normalized_difference < max_normalized_difference:
                results.append(strangle)

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
    report_writer = ReportWriter(results, execution_details)
    report_writer.write_html()
    report_writer.write_csv()

    # Print summary
    logger.info(f"Number of tickers processed: {num_tickers_processed:,}")
    logger.info(f"Number of contract pairs tried: {num_strangles_considered:,}")
    logger.info(f"Execution time: {execution_time:.2f} seconds")
    logger.info(f"Execution time per ticker: {execution_time_per_ticker:.4f} seconds\n")

def run_async_main():
    asyncio.run(main())

if __name__ == "__main__":
    if '--profile' in sys.argv:
        import cProfile
        cProfile.run('run_async_main()', 'profile_output.prof')
    else:
        run_async_main()
