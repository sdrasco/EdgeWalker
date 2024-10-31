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
import logging
import dash
import json
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import aiohttp
import asyncio
from models import Strangle

app = dash.Dash(__name__)

# Configure basic logging.  show warning or higher for external modules.
logging.basicConfig(
    level=logging.WARNING,  
    format='%(message)s'
)

# Create a logger for this module
logger = logging.getLogger(__name__)

# Show info level logger events for this module
logger.setLevel(logging.INFO)

# Suppress werkzeug HTTP request logs
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.ERROR)

# Load strangles from holdings.json
with open('holdings.json', 'r') as f:
    strangles_data = json.load(f)

# Initialize strangle objects
strangles = [Strangle(**data) for data in strangles_data]

# Get the API key from environment variable
API_KEY = os.getenv("POLYGONIO_API_KEY")

# Unified asynchronous function to get stock price, premium, and implied volatility
async def get_contract_details(session, underlying_asset: str, option_contract: str) -> dict:
    url = f"https://api.polygon.io/v3/snapshot/options/{underlying_asset}/{option_contract}?apiKey={API_KEY}"
    async with session.get(url) as response:
        if response.status == 200:
            contract_data = await response.json()
            contract_data = contract_data.get("results", {})
            stock_price = contract_data.get("underlying_asset", {}).get("price", 0)
            iv = contract_data.get("implied_volatility", 0)
            premium = contract_data.get("fmv", contract_data.get("last_quote", {}).get("midpoint", 0))

            return {"stock_price": stock_price, "implied_volatility": iv, "premium": premium}
        else:
            logger.info(f"Failed to fetch details for {option_contract} with status {response.status}")
            return {"stock_price": 0, "implied_volatility": 0, "premium": 0}

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
    
    # Run the async fetch function
    asyncio.run(fetch_and_update_strangles(display_list))
    
    return display_list

# Asynchronous function to fetch and update strangles concurrently
async def fetch_and_update_strangles(display_list):
    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_and_update_single_strangle(session, strangle)
            for strangle in strangles
        ]
        
        # Await all tasks and ensure updates are done
        await asyncio.gather(*tasks)
    
    # Sort strangles by ticker symbol alphabetically after all updates
    strangles.sort(key=lambda s: s.ticker)
    
    # Build the display list after sorting
    for strangle in strangles:
        x_min = strangle.lower_breakeven - (strangle.breakeven_difference * 0.25)
        x_max = strangle.upper_breakeven + (strangle.breakeven_difference * 0.25)
        # Adjust if stock_price is outside the range
        if strangle.stock_price < x_min:
            x_min = strangle.stock_price - (strangle.breakeven_difference * 0.1)
        if strangle.stock_price > x_max:
            x_max = strangle.stock_price + (strangle.breakeven_difference * 0.1)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[x_min, x_max],
            y=[0, 0],
            mode="lines",
            line=dict(color="black", width=1),
            name="Axis Line",
            showlegend=False
        ))
        fig.add_trace(go.Scatter(
            x=[strangle.lower_breakeven, strangle.upper_breakeven],
            y=[0, 0],
            mode="lines",
            line=dict(color="green", width=2),
            name="Breakeven Range"
        ))

        fig.add_trace(go.Scatter(
            x=[strangle.lower_breakeven],
            y=[0], 
            mode="markers",
            marker=dict(color="green", size=12, symbol="cross", line_width=0),
            name="Breakeven Marker"
        ))
        fig.add_trace(go.Scatter(
            x=[strangle.upper_breakeven],
            y=[0], 
            mode="markers",
            marker=dict(color="green", size=12, symbol="cross", line_width=0),
            name="Breakeven Marker"
        ))

        fig.add_trace(go.Scatter(
            x=[strangle.stock_price],
            y=[0],
            mode="markers",
            marker=dict(color="red", size=12, symbol="circle", line=dict(color="black", width=1)),
            name="Current Price Marker"
        ))

        fig.update_layout(
            showlegend=False,
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                title=(
                    f"({strangle.ticker}) "
                    f"(call: ${strangle.strike_price_call}, {strangle.expiration_date_call}) "
                    f"(put: ${strangle.strike_price_put}, {strangle.expiration_date_put}) "
                    f"(in: ${strangle.total_in:.2f}) "
                    f"(POP: {strangle.probability_of_profit:.0%})"
                    
                ),
                range=[x_min, x_max]
            ),
            yaxis=dict(
                showticklabels=False,
                showgrid=True,
                zeroline=True,
                range=[0, 0],  
                automargin=True
            ),
            height=200,
            plot_bgcolor="rgba(0,0,0,0)",  
            paper_bgcolor="rgba(0,0,0,0)",
            shapes=[
                dict(
                    type="line",
                    x0=x_min,
                    x1=x_max,
                    y0=0,
                    y1=0,
                    line=dict(color="black", width=1),
                    layer="below"
                )
            ]
        )

        display_list.append(
            html.Div([
                dcc.Graph(
                    figure=fig,
                    config={'displayModeBar': False},
                    style={'height': '200px', 'padding': '0', 'margin': '0'}
                )
            ], style={'padding': '0', 'margin': '0'})
        )

# Fetch details for a single strangle and update its fields
async def fetch_and_update_single_strangle(session, strangle):
    call_details = await get_contract_details(session, strangle.ticker, strangle.call_contract_ticker)
    put_details = await get_contract_details(session, strangle.ticker, strangle.put_contract_ticker)

    strangle.stock_price = call_details["stock_price"]

    premium_call = call_details["premium"]
    premium_put = put_details["premium"]
    iv_call = call_details["implied_volatility"]
    iv_put = put_details["implied_volatility"]

    total_premium = premium_call + premium_put
    if total_premium != 0:
        strangle.implied_volatility = (premium_call * iv_call + premium_put * iv_put) / total_premium
    else:
        strangle.implied_volatility = 0

    strangle.calculate_probability_of_profit()

# Run the app
if __name__ == '__main__':
    app.run_server(debug=False)