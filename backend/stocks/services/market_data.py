"""One bounded Yahoo request and a validated, dated OHLCV frame."""

import math
import re

import pandas as pd
import yfinance as yf

OHLCV = ("Open", "High", "Low", "Close", "Volume")


class InvalidTicker(ValueError):
    """Ticker syntax is invalid; no provider request should be made."""


class NoMarketData(ValueError):
    """The provider returned no observations; listing existence is unknown."""


def normalize_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise InvalidTicker("Ticker must be a string.")
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,4})?", symbol):
        raise InvalidTicker("Invalid equity ticker.")
    return symbol


def normalize_ohlcv(data: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Select one ticker, keep last duplicate, and reject unusable bars."""
    symbol = normalize_symbol(symbol)
    if data is None or (isinstance(data, pd.DataFrame) and len(data.index) == 0):
        raise NoMarketData("No market data returned.")
    if not isinstance(data, pd.DataFrame):
        raise ValueError("Market data must be a DataFrame.")
    if not isinstance(data.index, pd.DatetimeIndex) or data.index.hasnans:
        raise ValueError("Market data requires valid datetime timestamps.")

    if isinstance(data.columns, pd.MultiIndex):
        if data.columns.nlevels != 2:
            raise ValueError("Expected two-level market data columns.")
        ticker_levels = [
            level for level in range(2)
            if symbol in data.columns.get_level_values(level)
        ]
        if len(ticker_levels) != 1:
            raise ValueError("Missing or ambiguous ticker columns.")
        data = data.xs(symbol, axis=1, level=ticker_levels[0])

    if not data.columns.is_unique or not set(OHLCV).issubset(data.columns):
        raise ValueError("Market data requires unique Open, High, Low, Close, Volume fields.")
    data = data.loc[~data.index.duplicated(keep="last"), list(OHLCV)].copy()
    data = data.sort_index()
    data = data.apply(pd.to_numeric, errors="coerce")
    if any(pd.api.types.is_complex_dtype(dtype) for dtype in data.dtypes):
        raise ValueError("OHLCV values must be real numbers.")
    data = data.astype(float)
    if not data.map(math.isfinite).all().all():
        raise ValueError("OHLCV values must be finite numbers.")
    if (data[list(OHLCV[:4])] <= 0).any().any() or (data.Volume < 0).any():
        raise ValueError("Prices must be positive and volume nonnegative.")
    if ((data.High < data[["Open", "Low", "Close"]].max(axis=1)) |
            (data.Low > data[["Open", "High", "Close"]].min(axis=1))).any():
        raise ValueError("Inconsistent OHLC price range.")
    return data


def fetch_market_data(symbol: str) -> pd.DataFrame:
    symbol = normalize_symbol(symbol)
    try:
        data = yf.download(
            symbol, period="1y", interval="1d", auto_adjust=False,
            progress=False, threads=False, multi_level_index=False, timeout=10,
        )
    except Exception as exc:
        raise RuntimeError(f"Market data request failed for {symbol}.") from exc
    try:
        return normalize_ohlcv(data, symbol)
    except NoMarketData:
        raise
    except ValueError as exc:
        raise RuntimeError(f"Invalid market data returned for {symbol}.") from exc


def search_symbols(query: str) -> list[dict]:
    """Return a small set of equities supported by the existing ticker path."""
    query = query.strip()
    if len(query) > 80:
        raise ValueError("Search query is too long.")
    if not query:
        return []
    try:
        quotes = yf.Search(
            query, max_results=8, news_count=0, lists_count=0,
            include_cb=False, recommended=0, timeout=10,
        ).quotes
    except Exception as exc:
        raise RuntimeError("Market search failed.") from exc
    if not isinstance(quotes, list):
        raise RuntimeError("Invalid search response.")
    results = []
    seen = set()
    for quote in quotes:
        if not isinstance(quote, dict) or quote.get("quoteType") != "EQUITY":
            continue
        try:
            symbol = normalize_symbol(quote.get("symbol"))
        except InvalidTicker:
            continue
        name = quote.get("longname") or quote.get("shortname")
        if symbol in seen or not isinstance(name, str) or not name.strip():
            continue
        results.append({"symbol": symbol, "name": name.strip()})
        seen.add(symbol)
        if len(results) == 8:
            break
    return results
