"""Pure daily-bar calculations. Definitions and units: docs/METRICS.md."""

import math

import pandas as pd


def _validate_period(n: int) -> None:
    if type(n) is not int or n <= 0:
        raise ValueError("N must be a positive integer.")


def _finite(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def _column(data: pd.DataFrame, name: str, *, zero_valid=False) -> pd.Series:
    values = pd.to_numeric(data[name], errors="coerce").astype(float)
    valid = values.map(math.isfinite) & (values >= 0 if zero_valid else values > 0)
    return values.where(valid)


def _close_sequence(data: pd.DataFrame, n: int) -> pd.Series:
    """Use the trailing valid run so recursive metrics never bridge bad rows."""
    _validate_period(n)
    close = _column(data, "Close")
    invalid = [i for i, valid in enumerate(close.notna()) if not valid]
    return close.iloc[invalid[-1] + 1:] if invalid else close


def _returns(data: pd.DataFrame, n: int) -> pd.Series | None:
    _validate_period(n)
    close = _column(data, "Close").iloc[-(n + 1):]
    if len(close) < n + 1 or close.isna().any():
        return None
    return close.pct_change(fill_method=None).iloc[1:] * 100


def latest_price(data: pd.DataFrame) -> float | None:
    close = _column(data, "Close")
    return _finite(close.iloc[-1]) if len(close) else None


def latest_open(data: pd.DataFrame) -> float | None:
    opening = _column(data, "Open")
    return _finite(opening.iloc[-1]) if len(opening) else None


def sma(data: pd.DataFrame, n: int) -> float | None:
    _validate_period(n)
    close = _column(data, "Close").dropna().iloc[-n:]
    return _finite(close.mean()) if len(close) == n else None


def ema(data: pd.DataFrame, n: int) -> float | None:
    close = _close_sequence(data, n)
    if len(close) < n:
        return None
    value = float(close.iloc[:n].mean())
    alpha = 2 / (n + 1)
    for price in close.iloc[n:]:
        value = alpha * price + (1 - alpha) * value
    return _finite(value)


def rsi(data: pd.DataFrame, n: int) -> float | None:
    close = _close_sequence(data, n)
    if len(close) < n + 1:
        return None
    changes = close.diff().iloc[1:]
    gains = changes.clip(lower=0)
    losses = -changes.clip(upper=0)
    gain = float(gains.iloc[:n].mean())
    loss = float(losses.iloc[:n].mean())
    for next_gain, next_loss in zip(gains.iloc[n:], losses.iloc[n:]):
        gain = (gain * (n - 1) + next_gain) / n
        loss = (loss * (n - 1) + next_loss) / n
    if gain == 0 and loss == 0:
        return None
    return _finite(100 * (gain / (gain + loss)))


def cumulative_return(data: pd.DataFrame, n: int) -> float | None:
    _validate_period(n)
    close = _column(data, "Close").iloc[-(n + 1):]
    if len(close) < n + 1 or close.isna().any():
        return None
    return _finite((close.iloc[-1] / close.iloc[0] - 1) * 100)


def average_daily_return(data: pd.DataFrame, n: int) -> float | None:
    returns = _returns(data, n)
    return _finite(returns.mean()) if returns is not None else None


def daily_volatility(data: pd.DataFrame, n: int) -> float | None:
    returns = _returns(data, n)
    if returns is None or n < 2:
        return None
    return _finite(returns.std(ddof=1))


def adr_percent(data: pd.DataFrame, n: int) -> float | None:
    _validate_period(n)
    high, low = _column(data, "High"), _column(data, "Low")
    ranges = (high / low - 1).where(high >= low).dropna().iloc[-n:]
    return _finite(ranges.mean() * 100) if len(ranges) == n else None


def average_dollar_volume(data: pd.DataFrame, n: int) -> float | None:
    _validate_period(n)
    close = _column(data, "Close")
    volume = _column(data, "Volume", zero_valid=True)
    dollars = (close * volume).dropna().iloc[-n:]
    return _finite(dollars.mean() / 1_000_000) if len(dollars) == n else None
