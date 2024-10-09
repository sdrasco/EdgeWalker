import requests
from bs4 import BeautifulSoup
import json

"""
=================================================================================
                        Ticker Scraper and JSON Updater
---------------------------------------------------------------------------------
This script is designed to scrape ticker symbols from a Wikipedia page and store 
them in a JSON file under a user-defined list name. The script will:
  1. Scrape ticker symbols from the specified Wikipedia URL.
  2. Store the tickers in the JSON file under the provided list name.
  3. Alphabetize all ticker lists in the JSON file for consistency.
  4. Remove any duplicates from the ticker lists during the cleaning process.

Usage:
---------------------------------------------------------------------------------
1. Set the name of the ticker list you'd like to add to your JSON file.
2. Provide the URL of the Wikipedia page containing the ticker symbols.
3. Run the script, and it will scrape the tickers, update your JSON file, 
   alphabetize all existing lists, and remove duplicates.

Example:
---------------------------------------------------------------------------------
If you want to scrape and store the Russell 1000 tickers from Wikipedia:

ticker_list_name = "russell1000_tickers"
wikipedia_url = "https://en.wikipedia.org/wiki/Russell_1000_Index"
json_file_path = "your_ticker_collection.json"

# Call the function:
scrape_and_update_tickers(ticker_list_name, wikipedia_url, json_file_path)

To scrape a different list, simply change the 'wikipedia_url' and the name of
the 'ticker_list_name' for how you want it to be saved in the JSON file.

---------------------------------------------------------------------------------
Be nice to Wikipedia:
---------------------------------------------------------------------------------
Wikipedia prefers that users access its content via their official API rather than 
through scraping. However, this script is intended for occasional use and should 
not be used repeatedly, so as not to cause undue strain or be offensive to 
Wikipedia's infrastructure. Here are a few guidelines to follow:

  - Limit your use of this.  How many times do you really need to get these tickers?
  - Consider using Wikipedia's API rather than this script
  - Donate to wikipedia to make up for your sins https://donate.wikimedia.org/

---------------------------------------------------------------------------------
Dependencies:
- requests: To fetch the Wikipedia page.
- beautifulsoup4: To parse the HTML and extract the tickers.
- json: To read and update the JSON file.
=================================================================================
"""

# Function to scrape tickers from a Wikipedia page
def scrape_tickers_from_wikipedia(url, ticker_column_name='Symbol'):
    response = requests.get(url)

    # Check if the request was successful
    if response.status_code != 200:
        print(f"Failed to retrieve data from {url}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the table with the list of companies
    table = soup.find('table', {'class': 'wikitable sortable'})

    tickers = []

    if table:
        # Extract table rows
        rows = table.find_all('tr')

        # Get the header row to find the ticker column index
        header = rows[0].find_all('th')
        ticker_col_index = None

        for i, column in enumerate(header):
            if column.get_text(strip=True) == ticker_column_name:
                ticker_col_index = i
                break

        # Ensure the ticker column was found
        if ticker_col_index is None:
            print(f"{ticker_column_name} column not found in the table header")
            return []

        # Iterate through the rows to extract tickers
        for row in rows[1:]:  # Skip the header row
            columns = row.find_all('td')
            if len(columns) > ticker_col_index:  # Ensure there are enough columns in the row
                ticker = columns[ticker_col_index].get_text(strip=True)  # Extract ticker from the correct column
                tickers.append(ticker)

    return tickers

# Function to update JSON file with the scraped tickers and alphabetize all lists, removing duplicates
def update_ticker_collection(ticker_list_name, new_ticker_list, collection_file):
    with open(collection_file, 'r') as f:
        data = json.load(f)

    # Alphabetize and remove duplicates from all existing ticker lists
    for key, ticker_list in data.items():
        data[key] = sorted(set(ticker_list))

    # Add the new ticker list, remove duplicates, alphabetize it and add to the file
    data[ticker_list_name] = sorted(set(new_ticker_list))

    # Write the updated data back to the JSON file
    with open(collection_file, 'w') as f:
        json.dump(data, f, indent=4)

# Callable function to scrape and update tickers
def scrape_and_update_tickers(ticker_list_name, wikipedia_url, collection_file):
    # Scrape the tickers from the provided Wikipedia URL
    tickers = scrape_tickers_from_wikipedia(wikipedia_url)

    if tickers:
        # Update the JSON file with the new tickers under the specified name
        update_ticker_collection(ticker_list_name, tickers, collection_file)
        print(f"{ticker_list_name} tickers added, cleaned, and alphabetized in {collection_file}")
    else:
        print(f"Failed to scrape tickers from {wikipedia_url}")

# Main function to execute the script
def main():
    # Name of the ticker list to be added and the Wikipedia page URL
    ticker_list_name = "russell1000_tickers"
    wikipedia_url = "https://en.wikipedia.org/wiki/Russell_1000_Index"
    json_file_path = 'tickers.json'

    # Call the function with the specified inputs
    scrape_and_update_tickers(ticker_list_name, wikipedia_url, json_file_path)

# Execute the script
if __name__ == "__main__":
    main()