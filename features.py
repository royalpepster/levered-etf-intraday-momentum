import pandas as pd


def load_bars(path="data/soxx_5min.csv"):
    """Read the 5-min CSV from Phase 1 and turn the timestamps back into New York time."""
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert("America/New_York")
    return df


def build_daily_table(bars):
    """One row per day: the morning signal and the returns after it."""
    bars = bars.copy()
    bars["date"] = bars.index.date
    bars["time"] = bars.index.strftime("%H:%M")

    # Grid: one row per day, one column per bar start time, filled with Open prices
    opens = bars.pivot_table(index="date", columns="time", values="Open")

    # Closing price each day = Close of that day's last bar
    close = bars.groupby("date")["Close"].last()
    prev_close = close.shift(1)

    table = pd.DataFrame({
        "signal":       opens["12:00"] / prev_close - 1,      # prev close -> 12:00
        "target":       opens["14:00"] / opens["12:00"] - 1,  # 12:00 -> 14:00
        "signal_1230":  opens["12:30"] / prev_close - 1,      # prev close -> 12:30
        "target_1230":  opens["14:00"] / opens["12:30"] - 1,  # 12:30 -> 14:00
        "r_1400_close": close / opens["14:00"] - 1,           # 14:00 -> close
        "r_1530_close": close / opens["15:30"] - 1,           # last 30 min
    })
    return table


if __name__ == "__main__":
    bars = load_bars()
    table = build_daily_table(bars)

    n_before = len(table)
    table = table.dropna()
    print(f"Dropped {n_before - len(table)} days with a missing price (half days, first day)")

    table.to_csv("data/daily_table.csv")

    print(table.head(10))
    print(f"\n{len(table)} days, from {table.index[0]} to {table.index[-1]}")
    print("\nAverage returns (%):")
    print((table.mean() * 100).round(3))