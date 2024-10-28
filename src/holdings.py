"""
Strangle Tracker Dashboard (First Effort)

This is an initial version of a real-time dashboard for monitoring a portfolio of "strangle" option positions.
Built using Dash and the Polygon.io API, it updates each strangle’s breakeven range and current price every minute.

Current Features:
- Solid green line shows the breakeven range, with the current price marked by a bold red line and marker.
- Ticker, company name, and expiration date are displayed on the x-axis.
- Layout is functional but basic; styling improvements are planned for future versions.

Usage:
1. Set your Polygon.io API key in the environment as "POLYGONIO_API_KEY".
2. Run this script and check the console for the local URL (e.g., "http://127.0.0.1:8050/").
3. Open the URL in a browser to view the dashboard.

Requirements:
- Python environment with Dash installed
- Polygon.io API access with the API key in the environment
"""

import os
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd
import requests
from models import Strangle
from datetime import datetime

app = dash.Dash(__name__)

# Sample list of strangles
strangles = [
    Strangle("GILD", "Gilead Sciences", 0, "2024-11-01", "2024-11-01", 88, 88, 0.0, 0.0, 0.0, 0.0, 90.83, 85.17, 90.83 - 85.17, 0.0, 0.0, 1),
    Strangle("VZ", "Verizon Communications", 0, "2024-11-08", "2024-11-08", 42.5, 42, 0.0, 0.0, 0.0, 0.0, 43.67, 40.83, 43.67 - 40.83, 0.0, 0.0, 1),
    Strangle("VZ", "Verizon Communications", 0, "2024-11-15", "2024-11-15", 42, 42, 0.0, 0.0, 0.0, 0.0, 43.56, 40.44, 43.56 - 40.44, 0.0, 0.0, 1),
    Strangle("VCLT", "Vanguard Long-Term Corporate Bond ETF", 0, "2024-11-15", "2024-11-15", 79, 79, 0.0, 0.0, 0.0, 0.0, 81.33, 76.67, 81.33 - 76.67, 0.0, 0.0, 1),
    Strangle("CAG", "Conagra Brands", 0, "2024-11-15", "2024-11-15", 29, 30, 0.0, 0.0, 0.0, 0.0, 30.82, 28.18, 30.82 - 28.18, 0.0, 0.0, 2),
    Strangle("SHY", "iShares 1-3 Year Treasury Bond ETF", 0, "2024-11-15", "2024-11-15", 83, 82, 0.0, 0.0, 0.0, 0.0, 83.43, 81.57, 83.43 - 81.57, 0.0, 0.0, 2),
    Strangle("IGIB", "iShares Intermediate-Term Corporate Bond ETF", 0, "2024-11-15", "2024-11-15", 53, 53, 0.0, 0.0, 0.0, 0.0, 53.79, 52.21, 53.79 - 52.21, 0.0, 0.0, 1),
    Strangle("IEI", "iShares 3-7 Year Treasury Bond ETF", 0, "2024-11-15", "2024-11-15", 118, 118, 0.0, 0.0, 0.0, 0.0, 119.48, 116.52, 119.48 - 116.52, 0.0, 0.0, 1),
    Strangle("TRP", "TC Energy Corporation", 0, "2024-11-15", "2024-11-15", 47.5, 47.5, 0.0, 0.0, 0.0, 0.0, 49.87, 45.13, 49.87 - 45.13, 0.0, 0.0, 1),
    Strangle("D", "Dominion Energy", 0, "2024-11-15", "2024-11-15", 60, 60, 0.0, 0.0, 0.0, 0.0, 62.95, 57.05, 62.95 - 57.05, 0.0, 0.0, 1),
    Strangle("BCE", "BCE Inc.", 0, "2024-11-15", "2024-11-15", 33, 33, 0.0, 0.0, 0.0, 0.0, 34.39, 31.61, 34.39 - 31.61, 0.0, 0.0, 1),
    Strangle("DX", "Dynex Capital", 0, "2024-11-15", "2024-11-15", 12.5, 12.5, 0.0, 0.0, 0.0, 0.0, 13.01, 11.99, 13.01 - 11.99, 0.0, 0.0, 3),
    Strangle("SCHD", "Schwab U.S. Dividend Equity ETF", 0, "2024-11-15", "2024-11-15", 28.67, 38.33, 0.0, 0.0, 0.0, 0.0, 29.29, 27.71, 29.29 - 27.71, 0.0, 0.0, 1),
    Strangle("JNJ", "Johnson & Johnson", 0, "2024-11-22", "2024-11-22", 165, 165, 0.0, 0.0, 0.0, 0.0, 170.9, 159.1, 170.9 - 159.1, 0.0, 0.0, 1),
    Strangle("VZ", "Verizon Communications", 0, "2024-11-29", "2024-11-29", 42, 42, 0.0, 0.0, 0.0, 0.0, 43.96, 40.04, 43.96 - 40.04, 0.0, 0.0, 1),
    Strangle("VCSH", "Vanguard Short-Term Corporate Bond ETF", 0, "2024-12-20", "2024-12-20", 79, 78, 0.0, 0.0, 0.0, 0.0, 79.92, 77.8, 79.92 - 77.8, 0.0, 0.0, 1),
    Strangle("NLY", "Annaly Capital Management", 0, "2024-12-20", "2024-12-20", 20, 20, 0.0, 0.0, 0.0, 0.0, 21.15, 18.85, 21.15 - 18.85, 0.0, 0.0, 1)
]

# Get the API key from environment variable
API_KEY = os.getenv("POLYGONIO_API_KEY")

# Function to get stock price via options chain
def get_stock_price(ticker: str) -> float:
    url = f"https://api.polygon.io/v3/snapshot/options/{ticker}?limit=10&apiKey={API_KEY}"
    response = requests.get(url)

    try:
        data = response.json()
        # Retrieve stock price from the first result's underlying asset
        if 'results' in data and data['results']:
            return data['results'][0]['underlying_asset']['price']
        else:
            print("No results found for stock price.")
            return None
    except requests.exceptions.JSONDecodeError:
        print("Failed to decode JSON. Response content:")
        print(response.text)  # Display response for debugging
        return None

def get_contract_details(underlying_asset: str, option_contract: str) -> dict:
    # URL using the updated snapshot options format
    url = f"https://api.polygon.io/v3/snapshot/options/{underlying_asset}/{option_contract}?apiKey={API_KEY}"
    print(f"Requesting contract details with URL: {url}")  # Print URL for debugging
    response = requests.get(url)

    try:
        return response.json().get("results", {})
    except requests.exceptions.JSONDecodeError:
        print("Failed to decode JSON. Response content:")
        print(response.text)  # Print the raw response to understand the issue
        return {}

# Dash layout
app.layout = html.Div([
    dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0),
    html.Div(id='strangle-display')
])

@app.callback(
    Output('strangle-display', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_strangles(n):
    display_list = []
    
    for strangle in strangles:
        try:
            # Get the latest stock price
            strangle.stock_price = get_stock_price(strangle.ticker)
            
            # Create a line chart for the breakeven window
            fig = go.Figure()

            # Solid green line for breakeven range
            fig.add_trace(go.Scatter(
                x=[strangle.lower_breakeven, strangle.upper_breakeven],
                y=[0, 0],
                mode="lines",
                line=dict(color="green", width=2),
                name="Breakeven Range"
            ))

            # Solid, thicker red line for current price
            fig.add_trace(go.Scatter(
                x=[strangle.stock_price, strangle.stock_price],
                y=[-1, 1],  # Standard vertical range
                mode="lines",
                line=dict(color="red", width=5),
                name="Current Price"
            ))

            # Red marker at the current price
            fig.add_trace(go.Scatter(
                x=[strangle.stock_price],
                y=[0],
                mode="markers",
                marker=dict(color="red", size=12, symbol="circle", line=dict(color="black", width=1)),
                name="Current Price Marker"
            ))

            # Update layout: set background to white, add expiration in x-axis label, hide y-ticks
            fig.update_layout(
                showlegend=False,
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    title=f"{strangle.ticker} - {strangle.company_name} (Exp: {strangle.expiration_date_call})"
                ),
                yaxis=dict(showticklabels=False, showgrid=True, zeroline=True, range=[-2, 2]),
                height=200,
                plot_bgcolor="white",
                paper_bgcolor="white"
            )

            # Display with reduced padding and margin
            display_list.append(
                html.Div([
                    dcc.Graph(figure=fig)
                ], style={'padding': '0px 0', 'margin': '0px 0'})  # Reduced padding and margin
            )
        except Exception as e:
            print(f"Error updating strangle {strangle.ticker}: {e}")
            continue

    return display_list
    
# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)