import os

import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt

START_DATE = "2016-01-01"   # change to "2023-01-01" to test only recent years
NW_LAGS = 5                 # Newey-West lags: makes t-stats robust to clustered volatility

# (signal column, return column, label)
WINDOWS = [
    ("signal",      "target",       "12:00-14:00"),
    ("signal_1230", "target_1230",  "12:30-14:00"),
    ("signal",      "r_1400_close", "14:00-close"),
    ("signal",      "r_1530_close", "15:30-close"),
]


def load_table(path="data/daily_table.csv"):
    return pd.read_csv(path, index_col=0, parse_dates=True)


def regress(table, x, y):
    """window_return = a + beta * signal + error"""
    X = sm.add_constant(table[x])
    model = sm.OLS(table[y], X).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS})
    return {
        "beta": model.params[x],
        "t_stat": model.tvalues[x],
        "p_value": model.pvalues[x],
        "r_squared": model.rsquared,
        "n_days": int(model.nobs),
    }


def quintiles(table, x="signal", y="target", q=5):
    """Sort days into q groups by the signal; average the window return in each."""
    labels = [f"Q{i}" for i in range(1, q + 1)]
    groups = pd.qcut(table[x], q, labels=labels)
    out = table.groupby(groups, observed=True).agg(
        avg_signal=(x, "mean"),
        avg_return=(y, "mean"),
        std=(y, "std"),
        n=(y, "size"),
    )
    out["se"] = out["std"] / np.sqrt(out["n"])          # standard error of the average
    out["t_stat"] = out["avg_return"] / out["se"]
    return out


def plot_quintiles(q, title, path):
    os.makedirs("output", exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    x = range(len(q))
    colors = ["tab:red" if v < 0 else "tab:green" for v in q["avg_return"]]
    ax.bar(x, q["avg_return"] * 10000, color=colors, alpha=0.8)
    ax.errorbar(x, q["avg_return"] * 10000, yerr=q["se"] * 10000,
                fmt="none", ecolor="black", capsize=6)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{name}\n({s*100:+.2f}%)" for name, s in zip(q.index, q["avg_signal"])])
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_xlabel("Quintile of morning move (average morning return)")
    ax.set_ylabel("Average window return (bps), +/- 1 standard error")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path)
    print(f"Saved chart to {path}")


if __name__ == "__main__":
    pd.set_option("display.width", 150)
    pd.set_option("display.max_columns", None)

    table = load_table()
    table = table[table.index >= START_DATE]
    print(f"Sample: {table.index[0].date()} to {table.index[-1].date()}, {len(table)} days\n")

    # 1. Regressions for every window
    results = pd.DataFrame(
        {label: regress(table, x, y) for x, y, label in WINDOWS}
    ).T
    print("Regression: window return ~ morning move (Newey-West t-stats)")
    print(results.round(4))
    results.to_csv("output/regressions.csv")

    # 2. Quintiles for the main 12-2pm window and the last 30 minutes
    for x, y, label in [WINDOWS[0], WINDOWS[3]]:
        q = quintiles(table, x, y)
        print(f"\nQuintiles, {label}:")
        print(q.round(5))
        name = label.replace(":", "").replace("-", "_")
        plot_quintiles(q, f"SOXX {label} return by morning-move quintile",
                       f"output/quintiles_{name}.png")