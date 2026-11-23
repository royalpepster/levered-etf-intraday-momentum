import os

import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt

OUT = "output/final"
COST_BPS = 1.0      # cost per trade, each way, in basis points
NW_LAGS = 5

plt.rcParams.update({
    "figure.dpi": 130,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.titleweight": "bold",
    "axes.titlesize": 12,
})


def save(fig, name):
    fig.tight_layout()
    path = f"{OUT}/{name}"
    fig.savefig(path)
    plt.close(fig)
    print("Saved", path)


def sharpe(r):
    return np.sqrt(252) * r.mean() / r.std()


def load():
    table = pd.read_csv("data/daily_table.csv", index_col=0, parse_dates=True)
    soxx = pd.read_csv("data/soxx_daily.csv", index_col=0, parse_dates=True)["Close"]
    soxl = pd.read_csv("data/soxl_aum_sec.csv", index_col=0, parse_dates=True)["aum"]
    soxs = pd.read_csv("data/soxs_aum_sec.csv", index_col=0, parse_dates=True)["aum"]
    aum = pd.DataFrame({"soxl": soxl, "soxs": soxs})
    aum["demand"] = (6 * aum["soxl"] + 12 * aum["soxs"]) * 0.01   # $ traded per 1% move
    return table, soxx, aum


# ---------------------------------------------------------------- chart 1
def chart_aum(aum):
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(aum.index, aum["soxl"] / 1e9, marker="o", label="SOXL (3x bull)")
    axes[0].plot(aum.index, aum["soxs"] / 1e9, marker="o", label="SOXS (3x bear)")
    axes[0].set_ylabel("AUM ($ billions)")
    axes[0].set_title("Leveraged semiconductor ETF AUM (SEC N-PORT, quarterly)")
    axes[0].legend()
    axes[1].plot(aum.index, aum["demand"] / 1e9, marker="o", color="black")
    axes[1].set_ylabel("$ billions")
    axes[1].set_title("Close rebalancing demand per 1% move  [6 x SOXL + 12 x SOXS]")
    save(fig, "1_levered_etf_aum.png")


# ---------------------------------------------------------------- chart 2
def chart_soxx(soxx):
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(soxx.index, soxx, color="tab:blue")
    ax.set_yscale("log")
    ax.set_ylabel("Price ($, log scale)")
    ax.set_title("SOXX (iShares Semiconductor ETF), adjusted price")
    save(fig, "2_soxx_price.png")


# ---------------------------------------------------------------- chart 3
def chart_strategy(table, start=None, name="3_strategy_equity.png"):
    if start:
        table = table[table.index >= start]
    cost = 2 * COST_BPS / 10000
    pos = np.sign(table["signal"])
    r = table["target"]
    legs = pd.DataFrame({
        "Strategy (long + short)": np.where(pos > 0, r - cost, 0) + np.where(pos < 0, -r - cost, 0),
        "Long leg": np.where(pos > 0, r - cost, 0),
        "Short leg": np.where(pos < 0, -r - cost, 0),
        "Always long 12-2pm": r - cost,
    }, index=table.index)

    fig, ax = plt.subplots(figsize=(10, 5))
    styles = {"Strategy (long + short)": ("black", "-", 2),
              "Long leg": ("tab:green", "-", 1.2),
              "Short leg": ("tab:red", "-", 1.2),
              "Always long 12-2pm": ("gray", "--", 1.2)}
    for col, (color, ls, lw) in styles.items():
        ax.plot(legs.index, legs[col].cumsum() * 100, color=color, ls=ls, lw=lw,
                label=f"{col}  (Sharpe {sharpe(legs[col]):.2f})")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_ylabel("Cumulative return (%)")
    period = f"{table.index[0].date()} to {table.index[-1].date()}"
    ax.set_title(f"12-2pm momentum strategy, {period}, after {COST_BPS:.0f} bp costs each way")
    ax.legend()
    save(fig, name)

# ---------------------------------------------------------------- chart 4
def chart_quintiles(table):
    groups = pd.qcut(table["signal"], 5, labels=["Q1", "Q2", "Q3", "Q4", "Q5"])
    q = table.groupby(groups, observed=True).agg(
        avg_signal=("signal", "mean"), avg=("target", "mean"),
        std=("target", "std"), n=("target", "size"))
    q["se"] = q["std"] / np.sqrt(q["n"])

    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(5)
    colors = ["tab:red" if v < 0 else "tab:green" for v in q["avg"]]
    ax.bar(x, q["avg"] * 10000, color=colors, alpha=0.8)
    ax.errorbar(x, q["avg"] * 10000, yerr=q["se"] * 10000, fmt="none", ecolor="black", capsize=6)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{n}\n({s*100:+.2f}%)" for n, s in zip(q.index, q["avg_signal"])])
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_xlabel("Quintile of prev close -> 12pm return (average shown)")
    ax.set_ylabel("Average 12-2pm return (bps), +/- 1 SE")
    ax.set_title("12-2pm return by morning-move quintile")
    save(fig, "4_quintiles.png")


# ---------------------------------------------------------------- chart 5
def chart_scatter(table):
    X = sm.add_constant(table["signal"])
    m = sm.OLS(table["target"], X).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
    beta, t = m.params["signal"], m.tvalues["signal"]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(table["signal"] * 100, table["target"] * 100, s=6, alpha=0.3, color="tab:blue")
    xs = np.linspace(table["signal"].min(), table["signal"].max(), 100)
    ax.plot(xs * 100, (m.params["const"] + beta * xs) * 100, color="tab:orange", lw=2.5,
            label=f"beta = {beta:.3f}   (Newey-West t = {t:.2f})")
    ax.axhline(0, color="gray", lw=0.8)
    ax.axvline(0, color="gray", lw=0.8)
    ax.set_xlabel("Prev close -> 12pm return (%)")
    ax.set_ylabel("12pm -> 2pm return (%)")
    ax.set_title("Does the morning predict 12-2pm?")
    ax.legend()
    save(fig, "5_regression_scatter.png")


# ---------------------------------------------------------------- chart 6
def chart_rolling(table, aum, window=252):
    demand = aum["demand"].reindex(table.index.union(aum.index)).ffill().reindex(table.index)

    fig, ax = plt.subplots(figsize=(10, 5))
    for col, label, color in [("target", "12-2pm", "black"),
                              ("r_1400_close", "2pm-close", "tab:purple")]:
        beta = table["signal"].rolling(window).cov(table[col]) / table["signal"].rolling(window).var()
        ax.plot(beta.index, beta, color=color, label=f"Rolling 1-year beta, {label}")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_ylabel("Momentum beta")

    ax2 = ax.twinx()
    ax2.plot(demand.index, demand / 1e9, color="tab:blue", alpha=0.5,
             label="Rebalancing demand per 1% ($bn)")
    ax2.set_ylabel("$ billions", color="tab:blue")
    ax2.grid(False)

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left")
    ax.set_title("Momentum beta over time vs leveraged ETF demand")
    save(fig, "6_rolling_beta_vs_demand.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    table, soxx, aum = load()
    chart_aum(aum)
    chart_soxx(soxx)
    chart_strategy(table)
    chart_strategy(table, start="2026-01-01", name="3b_strategy_equity_2026.png")
    chart_quintiles(table)
    chart_scatter(table)
    chart_rolling(table, aum)
    print("\nAll charts are in", OUT)