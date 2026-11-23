import re
import time

import pandas as pd
import requests

# The SEC requires every program to identify itself with a name and email.
# Put your own here, e.g. "Pedro Ribas pedro@example.com"
USER_AGENT = "Your Name your.email@example.com"

CIK = "1424958"                       # Direxion Shares ETF Trust
SERIES = {"SOXL": "S000027920",       # Direxion Daily Semiconductor Bull 3X
          "SOXS": "S000027921"}       # Direxion Daily Semiconductor Bear 3X
HEADERS = {"User-Agent": USER_AGENT}


def list_filings(series_id):
    """Accession numbers of every N-PORT filing for one fund, newest first."""
    url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
           f"&CIK={series_id}&type=NPORT-P&dateb=&owner=include&count=100&output=atom")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return re.findall(r"<accession-number>([\d-]+)</accession-number>", r.text)


def read_net_assets(accession):
    """Open one filing and pull out the report date and net assets."""
    folder = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{folder}/primary_doc.xml"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    date = re.search(r"<(?:\w+:)?repPdDate>([^<]+)<", r.text).group(1)
    net_assets = float(re.search(r"<(?:\w+:)?netAssets>([^<]+)<", r.text).group(1))
    return date, net_assets


def get_aum(ticker):
    accessions = list_filings(SERIES[ticker])
    print(f"{ticker}: found {len(accessions)} filings")
    rows = []
    for acc in accessions:
        try:
            date, na = read_net_assets(acc)
            rows.append({"date": date, "aum": na})
        except Exception as e:
            print(f"  skipped {acc}: {e}")
        time.sleep(0.2)     # stay well under the SEC's limit of 10 requests per second

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    # Amended filings repeat a date; filings come newest first, so keep the first copy
    df = df.drop_duplicates("date", keep="first").sort_values("date").set_index("date")
    return df["aum"]


if __name__ == "__main__":
    for ticker in SERIES:
        aum = get_aum(ticker)
        aum.to_csv(f"data/{ticker.lower()}_aum_sec.csv")
        print(f"\n{ticker} AUM ($ billions):")
        print((aum / 1e9).round(2).to_string())
        print()