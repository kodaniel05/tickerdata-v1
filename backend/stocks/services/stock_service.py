"""Coordinate one fetch for a V1 summary or daily chart history."""

import pandas as pd

from . import metrics
from .market_data import fetch_market_data, normalize_symbol


class StockService:
    def __init__(self, symbol: str):
        self.symbol = normalize_symbol(symbol)

    def summary(self) -> dict:
        data = fetch_market_data(self.symbol)
        return {
            "symbol": self.symbol,
            "as_of": data.index[-1].isoformat(),
            "price": metrics.latest_price(data),
            "open": metrics.latest_open(data),
            "metrics": {
                "sma_20": metrics.sma(data, 20),
                "ema_20": metrics.ema(data, 20),
                "rsi_14": metrics.rsi(data, 14),
                "return_30d": metrics.cumulative_return(data, 30),
                "average_return_30d": metrics.average_daily_return(data, 30),
                "volatility_20d": metrics.daily_volatility(data, 20),
                "adr_20d": metrics.adr_percent(data, 20),
                "average_dollar_volume_20d": metrics.average_dollar_volume(data, 20),
            },
        }

    def history(self, history_range: str = "3m") -> dict:
        if history_range not in ("1m", "3m", "6m", "1y"):
            raise ValueError("Invalid history range.")
        data = fetch_market_data(self.symbol)
        latest = data.index[-1]
        if history_range != "1y":
            months = {"1m": 1, "3m": 3, "6m": 6}[history_range]
            # Include the cutoff session, anchored to the latest available bar.
            data = data.loc[data.index >= latest - pd.DateOffset(months=months)]
        return {
            "symbol": self.symbol,
            "range": history_range,
            "as_of": latest.isoformat(),
            "data": [
                {
                    "date": row.Index.date().isoformat(),
                    "open": float(row.Open),
                    "high": float(row.High),
                    "low": float(row.Low),
                    "close": float(row.Close),
                    "volume": float(row.Volume),
                }
                for row in data.itertuples()
            ],
        }
