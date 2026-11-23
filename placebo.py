import os

import pandas as pd
import statsmodels.api as sm

from data import get_5min_alpaca
from features import build_daily_table

TICKERS = ["SOXX", "XLU"]       # XLU = utilities, little leveraged ETF money
SPLIT_DATE = "2023-07-01"       # roughly where SOXX's high-demand period began
NW_LAGS = 5
WINDOWS = [
    ("signal", "target",       "12:00-14:00"),
    ("signal", "r_1400_close", "14:00-close"),
    ("signal", "r_1530_close", "15:30-close"),
]


def get_table(ticker):
    """Daily table for one ticker. Downloads 5-min bars from Alpaca the first time only."""
    if ticker == "SOXX":
        return pd.read_csv("data/daily_table.csv", index_col=0, parse_dates=True)
    path = f"data/{ticker.lower()}_daily_table.csv"
    if not os.path.exists(path):
        print(f"Downloading {ticker} 5-min bars from Alpaca (one time only)...")
        bars = get_5min_alpaca(ticker)
        build_daily_table(bars).dropna().to_csv(path)
    return pd.read_csv(path, index_col=0, parse_dates=True)


def change_test(table, x, y):
    """y = a + b1*signal + b2*signal*after + b3*after
    b1 = beta before the split; b1 + b2 = beta after; b2 = the change."""
    after = (table.index >= SPLIT_DATE).astype(float)
    X = sm.add_constant(pd.DataFrame({
        "signal": table[x],
        "signal_x_after": table[x] * after,
        "after": after,
    }, index=table.index))
    m = sm.OLS(table[y], X).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
    return {
        "beta_before": m.params["signal"],
        "t_before": m.tvalues["signal"],
        "beta_after": m.params["signal"] + m.params["signal_x_after"],
        "change": m.params["signal_x_after"],
        "t_change": m.tvalues["signal_x_after"],
    }


if __name__ == "__main__":
    pd.set_option("display.width", 150)
    pd.set_option("display.max_columns", None)

    rows = []
    for ticker in TICKERS:
        table = get_table(ticker)
        table = table[table.index >= "2019-10-31"]      # same sample as Phase 5
        for x, y, label in WINDOWS:
            rows.append({"ticker": ticker, "window": label, **change_test(table, x, y)})

    results = pd.DataFrame(rows).set_index(["window", "ticker"]).sort_index().round(4)
    print(f"Momentum beta before vs after {SPLIT_DATE}  (Newey-West t-stats)\n")
    print(results)
    results.to_csv("output/placebo_results.csv")