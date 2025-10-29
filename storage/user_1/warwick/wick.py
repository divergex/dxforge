import datetime

from dxlib import Executor, History, Portfolio, Instrument, OrderGenerator
from dxlib.data import Storage
from dxlib.interfaces import BacktestInterface
from dxlib.interfaces.external.yfinance import yfinance
from dxlib.strategy.signal import SignalStrategy

from dxlib.strategy.signal.custom.wick_reversal import WickReversal
from dxlib.strategy.views import SecuritySignalView


def zero(date):
    return date.replace(hour=0, minute=0, second=0, microsecond=0)


def main():
    api = yfinance.YFinance()
    api.start()

    symbols = ["AAPL"]
    end = datetime.datetime(2025, 3, 1)
    start = datetime.datetime(2025, 1, 1)
    storage = Storage()
    store = "yfinance"

    def run_backtest(range_multiplier, close_multiplier):
        history = storage.cached(store, History, api.historical, symbols, start, end)
        history_view = SecuritySignalView(time_index="datetime")

        strat = SignalStrategy(WickReversal(range_multiplier=range_multiplier, close_multiplier=close_multiplier), OrderGenerator())
        portfolio = Portfolio({Instrument("USD"): 1000})
        interface = BacktestInterface(history, history_view, portfolio)
        executor = Executor(strat, interface)
        orders, portfolio = executor.run(history_view, interface.iter())
        value = portfolio.value(interface.market.price_history.data)
        final_value = value.data.iloc[-1].item()
        return final_value

    print(
        run_backtest(0.7, 0.3)
    )

if __name__ == "__main__":
    main()
