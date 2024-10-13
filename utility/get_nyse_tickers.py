import json
import os
from polygon import RESTClient

# Initialize the Polygon client
api_key = os.getenv("POLYGONIO_API_KEY")
client = RESTClient(api_key)

# Initialize an empty list to store tickers
tickers = []

# Fetch all NYSE tickers from the generator
for ticker in client.list_tickers(market='stocks', exchange='XNYS', limit=1000):
    tickers.append(ticker.ticker)

# Load the existing JSON file
with open('tickers.json', 'r') as f:
    data = json.load(f)

# Add the new tickers to the JSON file in the desired format
data["nyse_tickers"] = tickers

# Write the updated data back to the JSON file
with open('tickers.json', 'w') as f:
    json.dump(data, f, indent=4)

print(f"Successfully added {len(tickers)} NYSE tickers to tickers.json.")