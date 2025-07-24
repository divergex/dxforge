from datetime import datetime, timedelta
from itertools import combinations
from typing import cast, Tuple
import matplotlib.pyplot as plt

import dxlib as dx
import numpy as np
import pandas as pd

from statsmodels.tsa.stattools import coint, adfuller
from sklearn.linear_model import LinearRegression
from dxlib.interfaces.external import yfinance

def get_historical(symbols) -> Tuple[dx.History, dx.InstrumentStore]:
    api = yfinance.YFinance()
    api.start()

    end = datetime.now()
    start = end - timedelta(days=90)

    storage = dx.data.Storage()
    store = "yfinance"

    asset_store = dx.InstrumentStore.from_symbols(symbols)
    historical = storage.cached(
        store, dx.History, api.historical, symbols, start, end, interval="1h", store=asset_store
    )

    return historical, asset_store


def z_scores(prices_x: pd.Series, prices_y: pd.Series):
    log_x = np.log(prices_x)
    log_y = np.log(prices_y)

    score, pvalue, _ = coint(log_x, log_y)
    if pvalue > 0.05:
        raise ValueError("Pairs are not cointegrated")

    model = cast(LinearRegression, LinearRegression().fit(log_x.values.reshape(-1, 1), log_y.values))
    beta = model.coef_[0]
    alpha = model.intercept_

    spread = log_y - (alpha + beta * log_x)

    spread_mean = spread.mean()
    spread_std = spread.std()
    zscore = (spread - spread_mean) / spread_std
    return zscore, alpha, beta


def strategy(zscore):
    positions = []
    position = 0

    for z in zscore:
        if position == 0:
            if z > 2:
                position = -1  # short spread: short SOL, long LTC
            elif z < -2:
                position = 1  # long spread: long SOL, short LTC
        elif position == 1 and z > -0.5:
            position = 0  # exit
        elif position == -1 and z < 0.5:
            position = 0  # exit
        positions.append(position)

    return positions


def evaluate(positions, log_x, log_y, beta):
    returns_x = log_x.diff()
    returns_y = log_x.diff()

    portfolio_rets = []

    for i, pos in enumerate(positions):
        if pos == 1:
            portfolio_rets.append(returns_x[i] - beta * returns_y[i])
        elif pos == -1:
            portfolio_rets.append(-returns_x[i] + beta * returns_y[i])
        else:
            portfolio_rets.append(0)

    return portfolio_rets

def main():
    symbols = ["LTC-USD", "ETH-USD", "BTC-USD", "BCH-USD", "ADA-USD", "SOL-USD"]
    history, asset_store = get_historical(symbols)
    dates = history.index("date").unique()

    def get_price(instrument):
        return history.get(index={"instruments": [instrument]}).dropna().data.reset_index()["close"]

    for sym in symbols:
        log_price = np.log(get_price(asset_store[sym]))
        adf_stat, pval, *_ = adfuller(log_price)
        print(f"{sym} ADF p-value: {pval}")

    scores = None
    returns = None
    positions = None
    pair = (None, None)
    portfolio = None
    for pair in combinations(asset_store.values(), 2):
        prices_x, prices_y = (get_price(i) for i in pair)

        try:
            scores, alpha, beta = z_scores(prices_x, prices_y)
        except ValueError as e:
            # print(f"Pairs {pair[0]} and {pair[1]} not correlated")
            continue

        positions = strategy(scores)
        returns = evaluate(positions, prices_x, prices_y, beta)
        print(f"PnL for {pair[0]} and {pair[1]} returns {np.cumsum(returns)[-1]}")

        portfolio = build_portfolio(
            positions,
            (pair[0].symbol, pair[1].symbol),
            beta,
            prices_x.values,
            prices_y.values,
            capital=1_000_000,
        )[-1]

        break
    #
    # df = pd.DataFrame({
    #     "zscore": scores,
    #     "position": positions,
    #     "returns": returns
    # }, index=dates[-len(scores):])

    # results(df, pair)
    return portfolio


def build_portfolio(positions, pair, beta, prices_x, prices_y, capital=1_000_000):
    portfolio_quantities = []
    sym_x, sym_y = pair

    for pos, px, py in zip(positions, prices_x, prices_y):
        if pos == 1:
            w_x = -1 / (1 + abs(beta))
            w_y = beta / (1 + abs(beta))
        elif pos == -1:
            w_x = 1 / (1 + abs(beta))
            w_y = -beta / (1 + abs(beta))
        else:
            w_x = 0
            w_y = 0

        qx = w_x * capital / px if px != 0 else 0
        qy = w_y * capital / py if py != 0 else 0

        portfolio_quantities.append({sym_x: qx, sym_y: qy})

    return portfolio_quantities


def results(df, pair):
    cum_returns = np.cumsum(df["returns"])

    # Metrics
    mean_return = np.mean(df["returns"])
    volatility = np.std(df["returns"])
    sharpe_ratio = mean_return / volatility * np.sqrt(24 * 365)  # hourly to annualized
    max_drawdown = np.max(np.maximum.accumulate(cum_returns) - cum_returns)
    total_return = cum_returns.iloc[-1]

    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Volatility (hourly): {volatility:.4f}")
    print(f"Total Return: {total_return:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2f}")

    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(df.index, cum_returns, label="Strategy PnL")
    plt.xlabel("Time")
    plt.ylabel("Cumulative Return")
    plt.title(f"StatArb PnL: {pair[0].symbol} vs {pair[1].symbol}")
    plt.axhline(0, linestyle="--", color="gray")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    print(main())
