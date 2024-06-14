import signal
import os

import dxlib as dx
from dxlib.interfaces.external.yfinance import YFinanceAPI


def signal_handler(sig, _):
    print(f"Received signal {sig}. Shutting down gracefully...")
    exit(0)


def main():
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "localhost")

    feed = YFinanceAPI()

    logger = dx.InfoLogger()
    interface = dx.interfaces.internal.MarketInterface(market_api=feed, host="localhost")

    server = dx.servers.HTTPServer(host=host, port=port, logger=logger)

    server.add_interface(interface)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    server.start(threaded=False)


if __name__ == "__main__":
    main()
