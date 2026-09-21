"""Coordinate one fetch with a fixed, small V1 metric summary."""

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
