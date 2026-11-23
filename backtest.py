import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

COST_BPS = 0.01              # cost per trade, each way, in basis points (1 bp = 0.01%)
START_DATE = "2016-01-01"   # change to "2023-01-01" to test only recent years
SIGNAL_COL = "signal"       # "signal" for 12-2pm, "signal_1230" for 12:30-2pm
TARGET_COL = "target"       # "target" for 12-2pm, "target_1230" for 12:30-2pm
THRESHOLD = 0.01 # only trade when the morning move is at least 1% either way; 0 = trade every day

def load_table(path="data/daily_table.csv"):
    return pd.read_csv(path, index_col=0, parse_dates=True)


def sharpe(r):
    """Annualized Sharpe ratio: average daily return / daily volatility x sqrt(252)."""
    return np.sqrt(252) * r.mean() / r.std()


def run_backtest(table, cost_bps=COST_BPS):
    
    cost = 2 * cost_bps / 10000              # in and out
    signal = table[SIGNAL_COL]
    position = np.where(signal.abs() >= THRESHOLD, np.sign(signal), 0)   # +1 long, -1 short, 0 no trade  # +1 = long, -1 = short
    r = table[TARGET_COL]                    # return over the trading window

    res = pd.DataFrame(index=table.index)
    res["position"] = position
    res["long_leg"] = np.where(position > 0, r - cost, 0.0)
    res["short_leg"] = np.where(position < 0, -r - cost, 0.0)
    res["strategy"] = res["long_leg"] + res["short_leg"]
    res["always_long"] = r                   # baseline: buy 12:00, sell 14:00 every day
    return res


def summarize(res):
    rows = {}
    for col in ["strategy", "long_leg", "short_leg", "always_long"]:
        r = res[col]
        if col == "always_long":
            traded = r
        elif col == "long_leg":
            traded = r[res["position"] > 0]
        elif col == "short_leg":
            traded = r[res["position"] < 0]
        else:
            traded = r[res["position"] != 0]
        rows[col] = {
            "sharpe": sharpe(r),
            "annual_return_%": r.mean() * 252 * 100,
            "annual_vol_%": r.std() * np.sqrt(252) * 100,
            "n_trades": len(traded),
            "hit_rate_%": (traded > 0).mean() * 100,
            "avg_bps_per_trade": traded.mean() * 10000,
        }

    # Benchmark: simply holding SOXX over the same dates
    soxx = pd.read_csv("data/soxx_daily.csv", index_col=0, parse_dates=True)["Close"]
    soxx_r = soxx.pct_change().reindex(res.index).dropna()
    rows["soxx_buy_hold"] = {
        "sharpe": sharpe(soxx_r),
        "annual_return_%": soxx_r.mean() * 252 * 100,
        "annual_vol_%": soxx_r.std() * np.sqrt(252) * 100,
        "n_trades": len(soxx_r),
        "hit_rate_%": (soxx_r > 0).mean() * 100,
        "avg_bps_per_trade": soxx_r.mean() * 10000,
    }
    return pd.DataFrame(rows).T.round(2)


def sharpe_by_year(res):
    cols = ["strategy", "long_leg", "short_leg", "always_long"]
    return res.groupby(res.index.year)[cols].agg(sharpe).round(2)


def plot_equity(res, path="output/equity_curve.png"):
    os.makedirs("output", exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 5))
    for col in ["strategy", "long_leg", "short_leg", "always_long"]:
        ax.plot(res.index, res[col].cumsum() * 100, label=col)
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_title("12-2pm SOXX momentum: cumulative return")
    ax.set_ylabel("Cumulative return (%)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    print(f"Saved chart to {path}")


if __name__ == "__main__":
    pd.set_option("display.width", 150)
    pd.set_option("display.max_columns", None)

    table = load_table()
    table = table[table.index >= START_DATE]
    print(f"Sample: {table.index[0].date()} to {table.index[-1].date()}, {len(table)} days")

    res = run_backtest(table)
    res.to_csv("data/backtest_results.csv")

    print(f"Window: {SIGNAL_COL} -> {TARGET_COL}   Threshold: {THRESHOLD:.1%}   Cost: {COST_BPS} bp each way\n")
    print(summarize(res))
    print("\nSharpe by year:")
    print(sharpe_by_year(res))
    plot_equity(res)