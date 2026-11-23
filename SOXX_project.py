import yfinance as yf
df = yf.download("SOXX", period="730d", interval="60m")
print(df.tail())