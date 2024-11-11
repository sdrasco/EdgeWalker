import os
import json
import logging
import dash
import asyncio
import websockets
import threading
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from models import Strangle

# Initialize Dash app
app = dash.Dash(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Store strangles in a dictionary for quick lookup
strangle_dict = {strangle.ticker: strangle for strangle in strangles}

# Dash layout
app.layout = html.Div([
    html.Div(id='strangle-display')
])

@app.callback(
    Output('strangle-display', 'children'),
    Input('strangle-display', 'children')
)
def update_strangles(_):
    display_list = []
    logger.info("Updating Dash display with latest prices...")
    for strangle in strangles:
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
            name="Breakeven Marker"
        ))
        fig.add_trace(go.Scatter(
            x=[strangle.upper_breakeven],
            y=[0], 
            mode="markers",
            marker=dict(color="green", size=12, symbol="cross", line_width=0),
            name="Breakeven Marker"
        ))
        if strangle.stock_price > 0:
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

        display_list.append(html.Div([
            dcc.Graph(
                figure=fig,
                config={'displayModeBar': False},
                style={'height': '200px', 'padding': '0', 'margin': '0'}
            )
        ], style={'padding': '0', 'margin': '0'}))

    return display_list

async def websocket_listener():
    while True:
        try:
            logger.info("Attempting to connect to WebSocket...")
            async with websockets.connect(WS_URL) as websocket:
                logger.info("WebSocket connection established.")

                # Step 2: Authenticate
                await websocket.send(json.dumps({"action": "auth", "params": API_KEY}))
                
                # Wait for multiple responses if needed
                while True:
                    auth_response = await websocket.recv()
                    logger.info(f"Auth Response: {auth_response}")
                    
                    response_data = json.loads(auth_response)
                    # Check if any response in the list includes an "authenticated" status
                    if any(event.get("status") == "auth_success" for event in response_data):
                        logger.info("Authentication successful.")
                        break
                    elif any(event.get("status") == "connected" for event in response_data):
                        logger.info("Connection established but not authenticated.")
                    else:
                        logger.error(f"Unexpected auth response: {auth_response}")
                        await asyncio.sleep(5)
                        continue

                # Step 3: Subscribe to tickers
                tickers_str = ",".join([f"A.{ticker}" for ticker in strangle_dict.keys()])
                await websocket.send(json.dumps({"action": "subscribe", "params": tickers_str}))
                logger.info(f"Subscribed to per-second trade updates for tickers: {tickers_str}")

                # Loop to receive data
                logger.info("Listening for incoming messages...")
                while True:
                    message = await websocket.recv()
                    logger.info(f"Raw message received: {message}")
                    data = json.loads(message)

                    for event in data:
                        if event.get("ev") == "T":
                            ticker = event["sym"]
                            price = event["p"]
                            logger.info(f"Trade update received for {ticker}: {price}")

                            if ticker in strangle_dict:
                                strangle = strangle_dict[ticker]
                                strangle.stock_price = price
                                logger.info(f"Updated {ticker} stock price to {price}")
                                # Trigger the Dash update
                                asyncio.run_coroutine_threadsafe(push_update(), asyncio.get_event_loop())
                        else:
                            logger.warning(f"Unhandled event type: {event}")
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"WebSocket connection closed: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error in websocket_listener: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

async def push_update():
    """Trigger a callback update for Dash."""
    logger.info("Triggering Dash callback update")
    context = dash.callback_context
    context.triggered = [{"prop_id": "strangle-display.children"}]
    app.callback_map["strangle-display.children"]["callback"](*[None])

def run_websocket_listener():
    asyncio.run(websocket_listener())

def main():
    # Start the WebSocket listener in a separate thread
    threading.Thread(target=run_websocket_listener, daemon=True).start()

    # Start the Dash server
    app.run_server(debug=False)

if __name__ == '__main__':
    main()