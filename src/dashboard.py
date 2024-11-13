import os
import json
import logging
import argparse
import asyncio
import threading
from threading import Lock
from datetime import datetime
from collections import defaultdict

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import websockets

from models import Strangle

# Initialize Dash app
app = dash.Dash(__name__)

# Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(message)s',
#     datefmt='%Y-%m-%d %H:%M:%S',
#     force=True
# )
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    force=True
)
logger = logging.getLogger(__name__)

# Set the werkzeug logger level to WARNING to suppress INFO logs
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Create a lock for thread safety
data_lock = Lock()

# Polygon WebSocket URL and API Key
WS_URL = "wss://socket.polygon.io/stocks"
API_KEY = os.getenv("POLYGONIO_API_KEY")

# Load strangles from holdings.json
with open('holdings.json', 'r') as f:
    strangles_data = json.load(f)

# Initialize Strangle objects with additional calculations
strangles = []
for data in strangles_data:
    premium_call = data.get("premium_call", 0)
    premium_put = data.get("premium_put", 0)
    strike_price_call = data.get("strike_price_call", 0)
    strike_price_put = data.get("strike_price_put", 0)
    
    cost_call = 100 * premium_call
    cost_put = 100 * premium_put
    fees = 1 * (0.53 + 0.55)
    total_in = cost_call + cost_put + fees
    total_in_per_share = premium_call + premium_put + (fees / 100.0)
    upper_breakeven = strike_price_call + total_in_per_share
    lower_breakeven = strike_price_put - total_in_per_share
    breakeven_difference = upper_breakeven - lower_breakeven
    average_strike = 0.5 * (strike_price_call + strike_price_put)

    data.update({
        "cost_call": cost_call,
        "cost_put": cost_put,
        "upper_breakeven": upper_breakeven,
        "lower_breakeven": lower_breakeven,
        "breakeven_difference": breakeven_difference,
        "normalized_difference": breakeven_difference / average_strike if average_strike != 0 else 0,
        "num_strangles_considered": 1,
        "total_in": total_in
    })
    strangles.append(Strangle(**data))

# Initialize a dictionary of lists to handle multiple holdings for each ticker
strangle_dict = defaultdict(list)
for strangle in strangles:
    strangle_dict[strangle.ticker].append(strangle)

# Dash layout
app.layout = html.Div([
    html.Div(id='strangle-display'),
    dcc.Interval(
        id='interval-component',
        interval=1000,  # in milliseconds
        n_intervals=0
    )
])

@app.callback(
    Output('strangle-display', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_strangles(n_intervals):
    display_list = []
    logger.debug("Updating Dash display with latest prices...")
    with data_lock:
        for ticker, strangle_list in strangle_dict.items():
            for strangle in strangle_list:
                x_min = strangle.lower_breakeven - (strangle.breakeven_difference * 0.25)
                x_max = strangle.upper_breakeven + (strangle.breakeven_difference * 0.25)

                if strangle.stock_price > 0:
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
                    name="Lower Breakeven"
                ))
                fig.add_trace(go.Scatter(
                    x=[strangle.upper_breakeven],
                    y=[0], 
                    mode="markers",
                    marker=dict(color="green", size=12, symbol="cross", line_width=0),
                    name="Upper Breakeven"
                ))
                if strangle.stock_price > 0:
                    fig.add_trace(go.Scatter(
                        x=[strangle.stock_price],
                        y=[0],
                        mode="markers",
                        marker=dict(color="red", size=12, symbol="circle", line=dict(color="black", width=1)),
                        name="Current Price"
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
                            f"(in: ${strangle.total_in:.2f})"
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
                    paper_bgcolor="rgba(0,0,0,0)"
                )

                # Append a display component for each strangle individually
                display_list.append(html.Div([
                    dcc.Graph(
                        figure=fig,
                        config={'displayModeBar': False},
                        style={'height': '200px', 'padding': '0', 'margin': '0'}
                    )
                ], style={'padding': '0', 'margin': '0'}))

    return display_list

async def websocket_listener(subscription_type):
    while True:
        try:
            async with websockets.connect(WS_URL) as websocket:
                logger.info("WebSocket connection established.")

                # Step 2: Authenticate
                await websocket.send(json.dumps({"action": "auth", "params": API_KEY}))
                
                # Wait for authentication response
                while True:
                    auth_response = await websocket.recv()
                    logger.info(f"Auth Response: {auth_response}")
                    
                    response_data = json.loads(auth_response)
                    if isinstance(response_data, list) and any(event.get("status") == "auth_success" for event in response_data):
                        logger.info("Authentication successful.")
                        break
                    elif isinstance(response_data, list) and any(event.get("status") == "connected" for event in response_data):
                        logger.info("Connection established but not authenticated.")
                    else:
                        logger.error(f"Unexpected auth response: {auth_response}")
                        await asyncio.sleep(5)
                        continue

                # Step 3: Subscribe to tickers based on subscription_type
                if subscription_type == 'per_minute':
                    prefix = 'AM.'
                elif subscription_type == 'per_second':
                    prefix = 'A.'
                elif subscription_type == 'trades':
                    prefix = 'T.'
                else:
                    logger.error(f"Invalid subscription type: {subscription_type}")
                    return

                tickers_str = ",".join([f"{prefix}{ticker}" for ticker in strangle_dict.keys()])
                await websocket.send(json.dumps({"action": "subscribe", "params": tickers_str}))
                logger.info(f"Subscribed to {subscription_type} updates for tickers: {tickers_str}")

                # Loop to receive data
                logger.info("Listening for incoming messages...")
                while True:
                    message = await websocket.recv()
                    logger.debug(f"Raw message received: {message}")
                    data = json.loads(message)

                    # Handle the case where data is a list of events
                    if isinstance(data, list):
                        for event in data:
                            await process_event(event, subscription_type)
                    # Handle the case where data is a single event (unlikely based on API, but just in case)
                    elif isinstance(data, dict):
                        await process_event(data, subscription_type)
                    else:
                        logger.warning(f"Unexpected message format: {data}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"WebSocket connection closed: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error in websocket_listener: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

async def process_event(event, subscription_type):
    ev_type = event.get("ev")
    ticker = event.get("sym")

    if ev_type == "status":
        logger.debug(f"Status event received: {event}")
        return

    if not ticker or ticker not in strangle_dict:
        logger.debug(f"Event for untracked ticker or missing ticker: {event}")
        return

    price = None
    if ev_type == "AM" and subscription_type == 'per_minute':
        price = event.get("c")
    elif ev_type == "A" and subscription_type == 'per_second':
        price = event.get("c")
    elif ev_type == "T" and subscription_type == 'trades':
        price = event.get("p")
    else:
        logger.debug(f"Unhandled event type or mismatched subscription: {event}")
        return

    if price is not None:
        with data_lock:
            # Update stock price for all holdings of this ticker
            for strangle in strangle_dict[ticker]:
                strangle.stock_price = price
        if ev_type == "T":
            Nshares = event.get("s")
            realtime_ms = event.get("t")
            
            # Convert SIP timestamp to human-readable format
            realtime_human = datetime.fromtimestamp(realtime_ms / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            logger.info(f"{realtime_human}\t{ticker}\t${price:.2f}\t{Nshares:,} shares")
        else:
            logger.info(f"{ticker}\t${price:.2f}")

    else:
        logger.warning(f"Price not found in event: {event}")

def run_websocket_listener(subscription_type):
    asyncio.run(websocket_listener(subscription_type))

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Strangle Dashboard')
    parser.add_argument('--subscription', choices=['per_minute', 'per_second', 'trades'], default='per_minute',
                        help='Subscription type for websocket (default: per_minute)')
    args = parser.parse_args()

    # Start the WebSocket listener in a separate thread
    threading.Thread(target=run_websocket_listener, args=(args.subscription,), daemon=True).start()

    # Start the Dash server
    app.run_server(debug=False)

if __name__ == '__main__':
    main()