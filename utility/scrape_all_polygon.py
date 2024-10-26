import requests
import os
import json

# Set up your API key from environment variables
polygonio_api_key = os.getenv("POLYGONIO_API_KEY")
filename = "../src/tickers.json"

def fetch_all_tickers():
    base_url = "https://api.polygon.io/v3/reference/tickers"
    params = {
        "market": "stocks",
        "active": "true",
        "limit": 1000,
        "apiKey": polygonio_api_key
    }

    tickers = []
    next_url = None

    while True:
        # Append the API key to the next_url if it exists
        url = next_url or base_url
        if next_url:
            url = f"{next_url}&apiKey={polygonio_api_key}"

        response = requests.get(url, params=None if next_url else params)
        data = response.json()

        if response.status_code != 200 or "results" not in data:
            print(f"Error fetching data: {data}")
            break

        tickers.extend([item["ticker"] for item in data["results"]])

        # Get the next URL for pagination, if any
        next_url = data.get("next_url")
        if not next_url:
            break

    return tickers

def add_all_polygon_collection(new_tickers):
    # Load existing data if the file exists
    if os.path.exists(filename):
        with open(filename, "r") as f:
            data = json.load(f)
    else:
        data = {}

    # Add the new "all_polygon" collection
    data["all_polygon"] = new_tickers

    return data

def save_tickers_to_json(data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def main():
    # Fetch, organize, and save the tickers
    new_tickers = fetch_all_tickers()
    updated_data = add_all_polygon_collection(new_tickers)
    save_tickers_to_json(updated_data)

if __name__ == "__main__":
    main()