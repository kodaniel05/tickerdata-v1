# TickerData metric contract

Phase 1 uses one year of Yahoo daily OHLCV, fetched once per summary with
`interval="1d"` and `auto_adjust=False`. All calculations use raw prices;
splits and dividends are not adjusted out of returns. No synthetic bar is added.
The latest bar may be unfinished or from a previous trading session. Prices are
not guaranteed real-time. `as_of` is that bar's preserved timestamp in ISO format,
not the retrieval time or a guarantee that the session has closed.

## Data and availability

- Symbols are stripped and uppercased. Accept an ASCII letter followed by up to
  nine letters/digits, optionally one `.` or `-` and one to four letters/digits
  (e.g. `AAPL`, `BRK-B`, `BRK.B`). This validates syntax, not listing existence.
- Accept flat columns or either single-ticker MultiIndex orientation. Select
  the requested ticker; reject ambiguous/missing fields. Preserve a valid
  DatetimeIndex, sort ascending, and keep the last original row at duplicate
  timestamps. Require Open, High, Low, Close and Volume.
- Coerce numeric strings; reject empty responses, invalid timestamps, missing or
  nonfinite numbers, nonpositive prices, negative volume, and inconsistent OHLC
  ranges. Zero volume is valid. Do not fill or invent observations.
- N must be a positive Python integer (not a boolean); otherwise raise ValueError.
  Successful metric scalars are finite Python floats. Unavailable results are
  None, including insufficient history and undefined sample volatility at N=1.
- Pure metrics do not mutate inputs. SMA/ADR/ADV select the latest N valid
  observations. Return windows require N+1 consecutive supplied valid closes;
  they do not bridge invalid rows. EMA/RSI use the trailing uninterrupted valid
  close sequence, seed once, and process its entire remainder. No calendar rows
  are synthesized: N counts observed trading periods, not calendar days.

## Definitions

| Metric | Definition | Required observations / units |
| --- | --- | --- |
| Latest price | Close of the last bar | One bar; quote currency |
| Latest open | Open of that same last bar | One bar; quote currency |
| SMA(N) | Mean of the latest N valid closes | N prices; quote currency |
| EMA(N) | Seed with mean of first N usable closes; then `E = alpha*C + (1-alpha)*E`, `alpha=2/(N+1)` | N prices; quote currency |
| RSI(N) | Seed mean gains/losses from first N changes, then Wilder smoothing `(previous*(N-1)+current)/N`; `100*gain/(gain+loss)` | N+1 prices; 0–100 oscillator |
| Cumulative return(N) | `(latest / close_N_periods_ago - 1) * 100` | N+1 prices; percentage points |
| Average daily return(N) | Mean of the latest N individual `(close/previous_close - 1)*100` returns | N+1 prices; percentage points |
| Daily volatility(N) | Sample standard deviation (`ddof=1`) of those N daily returns | N+1 prices and N>=2; percentage points; not annualized |
| ADR%(N) | `mean(High/Low - 1)*100` over latest N valid ranges | N bars; percentage points; not ATR |
| Average dollar volume(N) | `mean(raw Close * Volume)/1_000_000` over latest N valid pairs | N bars; millions of quote currency (dollars for USD equities) |

RSI is 100 when smoothed loss is zero and gain is positive, 0 for only losses,
and None when both are zero. No fabricated neutral value is used for flat data.
EMA/RSI depend on the beginning of the fetched sequence; one year is bounded
warm-up, not an assertion of equivalence to an unlimited-history provider.

Examples: 100 to 110 over one return is 10.0 percentage points. For
100 → 110 → 100, average daily return over two returns is approximately
0.454545 percentage points, despite zero cumulative return.

## Summary

`StockService(symbol).summary()` fetches once per call and passes the same frame
to all metrics. It returns symbol, as_of, price, open, and a metrics dictionary:
SMA/EMA 20, RSI 14, cumulative/average return 30, volatility/ADR%/dollar volume 20.
Keys ending in `d` denote trading periods. Results support strict JSON encoding.
Invalid symbols raise InvalidTicker; empty responses raise NoMarketData (both
ValueError subclasses). Raised provider exceptions and malformed fetched OHLCV
become RuntimeError. Direct normalization still uses ValueError for malformed data.
Suppressed Yahoo errors may appear as unavailable data, not proof of an unknown
listing. No persistent application cache, currency conversion or separate quote
request is part of the engine. The Django endpoint maps these errors to 400, 404
and 502 respectively; metric definitions and the successful summary are unchanged.
