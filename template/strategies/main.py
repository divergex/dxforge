import os
import signal

import dxlib as dx
import requests


def signal_handler(sig, _):
    print(f"Received signal {sig}. Shutting down gracefully...")
    exit(0)


def main():
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "localhost")

    strategy = dx.strategies.RsiStrategy()
    interface = dx.interfaces.internal.StrategyInterface(strategy)

    logger = dx.InfoLogger()
    server = dx.servers.HTTPServer(host=host, port=port, logger=logger)
    server.add_interface(interface)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    response = requests.get("http://host.docker.internal:8000/nodes/Node1/service")

    print(requests.get(f"http://feed1:5000/").json())


if __name__ == "__main__":
    main()
