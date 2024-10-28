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
    Strangle(
        ticker="GILD",
        company_name="Gilead Sciences",
        stock_price=0,  # Placeholder; updated in real-time
        expiration_date_call="2024-11-01",
        expiration_date_put="2024-11-01",
        strike_price_call=88,
        strike_price_put=88,
        premium_call=0.0,    # Placeholder for required field
        premium_put=0.0,     # Placeholder for required field
        cost_call=0.0,       # Placeholder for required field
        cost_put=0.0,        # Placeholder for required field
        upper_breakeven=90.83,
        lower_breakeven=85.17,
        breakeven_difference=90.83 - 85.17,
        normalized_difference=0.0,
        implied_volatility=0.0,
        num_strangles_considered=1
    ),
    Strangle(
        ticker="VZ",
        company_name="Verizon Communications",
        stock_price=0,  # Placeholder; updated in real-time
        expiration_date_call="2024-11-08",
        expiration_date_put="2024-11-08",
        strike_price_call=42.5,
        strike_price_put=42,
        premium_call=0.0,
        premium_put=0.0,
        cost_call=0.0,
        cost_put=0.0,
        upper_breakeven=43.67,
        lower_breakeven=40.83,
        breakeven_difference=43.67 - 40.83,
        normalized_difference=0.0,
        implied_volatility=0.0,
        num_strangles_considered=1
    ),
    Strangle(
        ticker="VCLT",
        company_name="Vanguard Long-Term Corporate Bond ETF",
        stock_price=0,  # Placeholder; updated in real-time
        expiration_date_call="2024-11-15",
        expiration_date_put="2024-11-15",
        strike_price_call=79,
        strike_price_put=79,
        premium_call=0.0,
        premium_put=0.0,
        cost_call=0.0,
        cost_put=0.0,
        upper_breakeven=81.33,
        lower_breakeven=76.67,
        breakeven_difference=81.33 - 76.67,
        normalized_difference=0.0,
        implied_volatility=0.0,
        num_strangles_considered=1
    )
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
    html.H1("Strangle Tracker"),
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
            fig.add_trace(go.Scatter(
                x=[strangle.lower_breakeven, strangle.upper_breakeven],
                y=[0, 0],
                mode="lines",
                line=dict(color="green", width=4),
                name="Breakeven Range"
            ))
            fig.add_trace(go.Scatter(
                x=[strangle.stock_price],
                y=[0],
                mode="markers",
                marker=dict(color="red", size=15, symbol="circle", line=dict(color="black", width=2)),
                name="Current Price"
            ))

            # Customize layout: no axis labels, remove legend, and hide vertical axis
            fig.update_layout(
                showlegend=False,
                xaxis=dict(showgrid=False, zeroline=False, title=""),  # No x-axis label
                yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),  # Hide y-axis
                height=100  # Reduce plot height
            )

            # Display only essential details and breakeven range chart
            display_list.append(
                html.Div([
                    html.H3(f"{strangle.ticker} - {strangle.company_name}"),
                    dcc.Graph(figure=fig)
                ], style={'border': '1px solid black', 'padding': '10px', 'margin': '10px'})
            )
        except Exception as e:
            # Log the error in the terminal and continue with the next strangle
            print(f"Error updating strangle {strangle.ticker}: {e}")
            continue

    return display_list
    
# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)