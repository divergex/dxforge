from datetime import datetime

from dxlib import History
from dxlib.interfaces import InvestingCom
from dxlib.interfaces.internal.history import HistoryHttpHandler
from dxlib.interfaces.servers.http.fastapi import FastApiServer
from dxlib.storage import Cache


def main():
    server = FastApiServer("localhost", 8000)

    handler = HistoryHttpHandler()

    cache = Cache()

    if not History.cache_exists(cache.cache_dir, "AAPL"):
        api = InvestingCom()
        start = datetime(2020, 1, 1)
        end = datetime(2021, 1, 1)

        history = api.historical("AAPL", start, end)
        history.store(cache.cache_dir, "AAPL")
    else:
        history = History.load(cache.cache_dir, "AAPL")

    handler.register(history, "AAPL")
    server.register_handler(handler)

    server.start()


if __name__ == "__main__":
    main()
