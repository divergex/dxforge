import datetime

from dxlib import Executor, History
from dxlib.interfaces.external.yfinance import YFinance
from dxlib.strategy.signal.custom.wick_reversal import WickReversal
from dxlib.strategy.views import SecuritySignalView
from dxlib.strategy.signal import SignalStrategy
from dxlib.data import Storage


def zero(date):
    return date.replace(hour=0, minute=0, second=0, microsecond=0)


def main():
    api = YFinance()
    api.start()

    symbols = ["BTC=F"]
    end = zero((datetime.datetime.now() - datetime.timedelta(days=7)))
    start = zero(end - datetime.timedelta(days=7))
    storage = Storage()
    store = "yfinance"

    history = storage.cached(store, api.historical, History, symbols, start, end)

    strat = SignalStrategy(WickReversal())
    executor = Executor(strat)
    res = executor.run(history, SecuritySignalView())
    print(res)

if __name__ == "__main__":
    main()
