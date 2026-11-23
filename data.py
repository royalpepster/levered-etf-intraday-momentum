import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*inplace keyword.*")

import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.enums import Adjustment, DataFeed

from keys import ALPACA_KEY, ALPACA_SECRET

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


def flatten(df):
    """yfinance sometimes returns two-level column names like ('Close', 'SOXX').
    This keeps just the first level: 'Close'."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def get_hourly(ticker="SOXX"):
    df = yf.download(ticker, period="730d", interval="60m", progress=False)
    df = flatten(df)
    df.index = df.index.tz_convert("America/New_York")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def get_5min_alpaca(ticker="SOXX", start="2016-01-01"):
    client = StockHistoricalDataClient(ALPACA_KEY, ALPACA_SECRET)
    request = StockBarsRequest(
        symbol_or_symbols=ticker,
        timeframe=TimeFrame(5, TimeFrameUnit.Minute),
        start=datetime.fromisoformat(start),
        end=datetime.now() - timedelta(days=1),
        adjustment=Adjustment.ALL,
        feed=DataFeed.SIP,
    )
    df = client.get_stock_bars(request).df
    df = df.reset_index(level=0, drop=True)
    df.index = df.index.tz_convert("America/New_York")
    df = df.between_time("09:30", "15:55")
    df.columns = [c.capitalize() for c in df.columns]
    return df[["Open", "High", "Low", "Close", "Volume"]]


def get_daily(ticker, start="2010-01-01"):
    df = yf.download(ticker, start=start, interval="1d", progress=False)
    df = flatten(df)
    return df[["Close", "Volume"]]


def get_aum(ticker, daily_close):
    """AUM = shares outstanding x price. Returns None if Yahoo has no shares data."""
    shares = yf.Ticker(ticker).get_shares_full(start="2010-01-01")
    if shares is None or len(shares) == 0:
        print(f"  No shares history on Yahoo for {ticker}, skipping AUM.")
        return None
    shares.index = shares.index.tz_localize(None).normalize()
    shares = shares[~shares.index.duplicated(keep="last")]
    shares = shares.reindex(daily_close.index, method="ffill")
    return (shares * daily_close).rename("AUM")


if __name__ == "__main__":
    print("Downloading SOXX hourly...")
    get_hourly("SOXX").to_csv(f"{DATA_DIR}/soxx_hourly.csv")

    print("Downloading SOXX 5-min from Alpaca...")
    get_5min_alpaca("SOXX").to_csv(f"{DATA_DIR}/soxx_5min.csv")

    for t in ["SOXX", "SOXL", "SOXS"]:
        print(f"Downloading {t} daily...")
        daily = get_daily(t)
        daily.to_csv(f"{DATA_DIR}/{t.lower()}_daily.csv")

        if t != "SOXX":
            print(f"Computing {t} AUM...")
            aum = get_aum(t, daily["Close"])
            if aum is not None:
                aum.to_csv(f"{DATA_DIR}/{t.lower()}_aum.csv")

    print("Done. Files in data/:", os.listdir(DATA_DIR))