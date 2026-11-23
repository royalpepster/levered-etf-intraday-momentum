import os

import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt

NW_LAGS = 5
WINDOWS = [
    ("signal", "target",       "12:00-14:00"),
    ("signal", "r_1400_close", "14:00-close"),
    ("signal", "r_1530_close", "15:30-close"),
]


def load_aum():
    """Quarterly AUM from SEC filings, plus close rebalancing demand per 1% move."""
    soxl = pd.read_csv("data/soxl_aum_sec.csv", index_col=0, parse_dates=True)["aum"]
    soxs = pd.read_csv("data/soxs_aum_sec.csv", index_col=0, parse_dates=True)["aum"]
    aum = pd.DataFrame({"soxl": soxl, "soxs": soxs})
    # L(L-1) = 6 for SOXL (3x) and 12 for SOXS (-3x)
    aum["demand_per_1pct"] = (6 * aum["soxl"] + 12 * aum["soxs"]) * 0.01
    return aum


def attach_aum(table, aum):
    """Give each trading day the most recent quarter-end AUM (no look-ahead)."""
    all_dates = table.index.union(aum.index)
    daily = aum.reindex(all_dates).ffill().reindex(table.index)
    return table.join(daily).dropna(subset=["demand_per_1pct"])


def fit(df, x, y):
    X = sm.add_constant(df[x])
    return sm.OLS(df[y], X).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})


def split_test(df, x, y):
    """Momentum beta when demand was below vs above its median."""
    median = df["demand_per_1pct"].median()
    rows = {}
    for name, part in [("low demand", df[df["demand_per_1pct"] <= median]),
                       ("high demand", df[df["demand_per_1pct"] > median])]:
        m = fit(part, x, y)
        rows[name] = {
            "period": f"{part.index[0].date()} to {part.index[-1].date()}",
            "avg_demand_$bn": round(part["demand_per_1pct"].mean() / 1e9, 2),
            "beta": round(m.params[x], 4),
            "t_stat": round(m.tvalues[x], 2),
            "n_days": int(m.nobs),
        }
    return pd.DataFrame(rows).T


def interaction(df, x, y):
    """window_return = a + b1*signal + b2*signal*demand + b3*demand
    demand = log rebalancing demand, standardized. b2 > 0 means momentum grows with demand."""
    z = np.log(df["demand_per_1pct"])
    z = (z - z.mean()) / z.std()
    X = sm.add_constant(pd.DataFrame({
        "signal": df[x],
        "signal_x_demand": df[x] * z,
        "demand": z,
    }))
    return sm.OLS(df[y], X).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})


def rolling_beta(df, x, y, window=252):
    return df[x].rolling(window).cov(df[y]) / df[x].rolling(window).var()


def plot_aum(aum, path="output/levered_etf_aum.png"):
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(aum.index, aum["soxl"] / 1e9, marker="o", label="SOXL (3x bull)")
    axes[0].plot(aum.index, aum["soxs"] / 1e9, marker="o", label="SOXS (3x bear)")
    axes[0].set_ylabel("AUM ($ billions)")
    axes[0].set_title("Leveraged semiconductor ETF AUM (SEC N-PORT, quarterly)")
    axes[0].legend()
    axes[1].plot(aum.index, aum["demand_per_1pct"] / 1e9, marker="o", color="black")
    axes[1].set_ylabel("$ billions")
    axes[1].set_title("Close rebalancing demand per 1% move in semis")
    fig.tight_layout()
    fig.savefig(path)
    print(f"Saved chart to {path}")


def plot_rolling(df, x, y, label, path):
    beta = rolling_beta(df, x, y)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(beta.index, beta, color="black", label=f"Rolling 1-year beta ({label})")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_ylabel("Momentum beta")
    ax2 = ax.twinx()
    ax2.plot(df.index, df["demand_per_1pct"] / 1e9, color="tab:blue", alpha=0.6,
             label="Rebalancing demand per 1% ($bn)")
    ax2.set_ylabel("$ billions", color="tab:blue")
    ax.set_title(f"Does momentum ({label}) rise with leveraged ETF demand?")
    lines = ax.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    ax.legend(lines, labels, loc="upper left")
    fig.tight_layout()
    fig.savefig(path)
    print(f"Saved chart to {path}")


if __name__ == "__main__":
    pd.set_option("display.width", 150)
    pd.set_option("display.max_columns", None)
    os.makedirs("output", exist_ok=True)

    table = pd.read_csv("data/daily_table.csv", index_col=0, parse_dates=True)
    aum = load_aum()
    df = attach_aum(table, aum)
    #df = df[df.index >= "2021-01-01"]   # robustness: exclude 2020
    print(f"Sample with AUM data: {df.index[0].date()} to {df.index[-1].date()}, {len(df)} days\n")

    for x, y, label in WINDOWS:
        print("=" * 70)
        print(f"WINDOW {label}")
        print("\nTest 1: momentum beta, low vs high rebalancing demand")
        print(split_test(df, x, y))

        m = interaction(df, x, y)
        print("\nTest 2: interaction regression")
        print(pd.DataFrame({"coef": m.params, "t_stat": m.tvalues, "p_value": m.pvalues}).round(4))
        print()

        name = label.replace(":", "").replace("-", "_")
        plot_rolling(df, x, y, label, f"output/rolling_beta_{name}.png")

    plot_aum(aum)