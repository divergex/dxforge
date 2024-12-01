# 1. Setup LOB connection (use mock or real doesn't matter)
# 2. Make LOB printable
# 3. Make LOB interactive (send orders)
# 4. Setup LOB internal interface
from dxlib.interfaces.external.ibkr.ibkr import Ibkr


def main():
    api = Ibkr()
    market_api = api.market_interface

    host ="127.0.0.1"
    port = 4002
    client_id = 1

    market_api.record()
    lob = market_api.get_book("AAPL")



if __name__ == "__main__":
    main()
