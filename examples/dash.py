import os
import signal
import sys
import time
import threading
import numpy as np

import dash
import uvicorn
from fastapi import FastAPI
from dash import Dash, dcc, html
import plotly.graph_objects as go
from starlette.middleware.wsgi import WSGIMiddleware
from starlette.responses import HTMLResponse

server_host = "0.0.0.0"
server_port = 8080

# Logger
import logging
logger = logging.getLogger(__name__)

class LimitOrderBook:
    def __init__(self):
        self.bids = {}
        self.asks = {}
        self.lock = threading.Lock()
        self.current_price = 500.0  # Initial price
        self.mean = 0.001  # Drift

    def tick_price(self, reqId, tickType, price, attrib=None, quantity=1.0):
        if tickType == 66:  # Bid price
            with self.lock:
                logger.info(f"Bid price: {price}")
                self.bids[round(price, 2)] = self.bids.get(round(price, 2), 0) + quantity
        elif tickType == 67:  # Ask price
            with self.lock:
                logger.info(f"Ask price: {price}")
                self.asks[round(price, 2)] = self.asks.get(round(price, 2), 0) + quantity

    def subscribe_to_market_data(self, symbol, sec_type="STK", exchange="ISLAND", currency="USD"):
        def simulate_market_data():
            np.random.seed(42)  # For reproducibility
            volatility = 0.0008  # Standard deviation of returns
            lambda_quantity = 10  # Rate of exponential distribution for quantity

            while True:
                # Simulate Gaussian Brownian motion for price
                return_ = np.random.normal(self.mean, volatility)
                self.current_price += return_

                # Generate tick prices
                bid_price = max(self.current_price - 0.01, 0)
                ask_price = max(self.current_price + 0.01, 0)

                bid_quantity = np.random.exponential(1 / lambda_quantity)
                ask_quantity = np.random.exponential(1 / lambda_quantity)

                # Mock tick price calls
                self.tick_price(1, 66, bid_price, None, round(bid_quantity, 1))
                self.tick_price(1, 67, ask_price, None, round(ask_quantity, 1))

                time.sleep(1)

                # if lob size > 2000, remove the oldest entry
                if len(self.bids) > 100:
                    self.bids.popitem()
                if len(self.asks) > 100:
                    self.asks.popitem()

        thread = threading.Thread(target=simulate_market_data, daemon=True)
        thread.start()

    def get_order_book_data(self):
        with self.lock:
            # Sort bids descending and asks ascending
            bids = sorted(self.bids.items(), key=lambda x: -x[0])
            asks = sorted(self.asks.items(), key=lambda x: x[0])

            bid_prices, bid_sizes = zip(*bids) if bids else ([], [])
            ask_prices, ask_sizes = zip(*asks) if asks else ([], [])

            return bid_prices, bid_sizes, ask_prices, ask_sizes


# Dash application
lob = LimitOrderBook()

app = Dash(__name__, requests_pathname_prefix="/dash/")


def create_dash_layout():
    return html.Div([
        dcc.Graph(id="order-book-graph", figure=create_plot()),
        dcc.Interval(id="update-interval", interval=1000, n_intervals=0)  # Update every second
    ])


def create_plot():
    fig = go.Figure()

    # Add traces for bids and asks
    fig.add_trace(go.Bar(
        x=[], y=[], orientation="h", name="Bids", marker=dict(color="green")
    ))
    fig.add_trace(go.Bar(
        x=[], y=[], orientation="h", name="Asks", marker=dict(color="red")
    ))

    # Layout
    fig.update_layout(
        title="Real-Time Limit Order Book",
        xaxis=dict(title="Size"),
        yaxis=dict(title="Price", autorange="reversed"),
        barmode="relative",
        height=600,
    )
    return fig


app.layout = create_dash_layout()

@app.callback(
    dash.dependencies.Output("order-book-graph", "figure"),
    [dash.dependencies.Input("update-interval", "n_intervals")]
)
def update_graph(n_intervals):
    bid_prices, bid_sizes, ask_prices, ask_sizes = lob.get_order_book_data()

    fig = create_plot()

    # Update data
    fig.data[0].x = bid_sizes
    fig.data[0].y = bid_prices
    fig.data[1].x = [-size for size in ask_sizes]  # Negative for asks
    fig.data[1].y = ask_prices

    return fig

api = FastAPI()
api.mount("/dash", WSGIMiddleware(app.server))
config = uvicorn.Config(api, host=server_host, port=server_port, log_level="info", loop="asyncio")
server = uvicorn.Server(config=config)

@api.get("/")
def root():
    return HTMLResponse(f"""
        <html>
            <head>
                <title>Dash in FastAPI</title>
            </head>
            <body>
                <h3>Navigate to <a href="/dash/">/dash/</a> for the Dash app</h3>
            </body>
        </html>
        """)


def shutdown_event():
    with open("lob.csv", "w") as f:
        f.write("Price,Type,Size\n")
        for price, size in lob.bids.items():
            f.write(f"{price},BID,{size}\n")
        for price, size in lob.asks.items():
            f.write(f"{price},ASK,{size}\n")
    sys.exit(0)


def load_order_book(lob):
    if os.path.exists("lob.csv"):
        with open("lob.csv", "r") as f:
            f.readline()
            for line in f:
                price, order_type, size = line.strip().split(",")
                if order_type == "BID":
                    lob.bids[float(price)] = float(size)
                else:
                    lob.asks[float(price)] = float(size)


if __name__ == "__main__":
    load_order_book(lob)
    lob.subscribe_to_market_data("AAPL")

    t = threading.Thread(target=server.run)
    t.start()

    def signal_handler(sig, frame):
        shutdown_event()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown_event()
        print("Exiting...")
