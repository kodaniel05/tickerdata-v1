"""Deterministic engine tests; no network, database, or extra test dependency."""

import json
import math
from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import patch

import pandas as pd
from django.test import SimpleTestCase

from .services import market_data, metrics
from .services.stock_service import StockService


def bars(closes):
    """Build internally consistent OHLCV with dated, floating-point prices."""
    close = pd.Series(closes, dtype=float).to_numpy()
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1,
         "Close": close, "Volume": 1_000_000.0},
        index=pd.date_range("2025-01-01", periods=len(close), freq="B", tz="UTC"),
    )


WINDOW_METRICS = (
    metrics.sma, metrics.ema, metrics.rsi, metrics.cumulative_return,
    metrics.average_daily_return, metrics.daily_volatility,
    metrics.adr_percent, metrics.average_dollar_volume,
)


class MetricTests(TestCase):
    def test_latest_values_use_same_final_bar(self):
        data = bars([100, 110])
        data.loc[data.index[-1], "Open"] = 105.0
        self.assertEqual(metrics.latest_price(data), 110.0)
        self.assertEqual(metrics.latest_open(data), 105.0)

    def test_latest_invalid_does_not_fall_back_to_previous_session(self):
        data = bars([100, float("nan")])
        self.assertIsNone(metrics.latest_price(data))
        self.assertIsNone(metrics.latest_open(data))

    def test_sma_known_sequence(self):
        self.assertEqual(metrics.sma(bars([10, 20, 30, 40]), 3), 30.0)

    def test_sma_selects_latest_valid_observations(self):
        self.assertEqual(metrics.sma(bars([10, 20, float("nan"), 40]), 2), 30.0)

    def test_ema_sma_seed_and_recursion(self):
        self.assertEqual(metrics.ema(bars([10, 20, 40]), 3), 70 / 3)
        # Seed=70/3, then alpha=0.5: 110/3, then 145/3.
        self.assertAlmostEqual(metrics.ema(bars([10, 20, 40, 50, 60]), 3), 145 / 3)

    def test_rsi_rising_zero_loss(self):
        self.assertEqual(metrics.rsi(bars([10, 11, 12, 14, 17]), 3), 100.0)

    def test_rsi_falling(self):
        self.assertEqual(metrics.rsi(bars([17, 14, 12, 11, 10]), 3), 0.0)

    def test_rsi_mixed_wilder_seed_and_recursion(self):
        # Changes +2,-1,+2 seed gain=4/3, loss=1/3 -> RSI=80.
        self.assertAlmostEqual(metrics.rsi(bars([10, 12, 11, 13]), 3), 80.0)
        # Next -1 -> gain=8/9, loss=5/9 -> RSI=800/13.
        self.assertAlmostEqual(metrics.rsi(bars([10, 12, 11, 13, 12]), 3), 800 / 13)

    def test_rsi_flat_is_unavailable(self):
        self.assertIsNone(metrics.rsi(bars([100] * 20), 14))

    def test_cumulative_return_exact_horizon(self):
        self.assertAlmostEqual(metrics.cumulative_return(bars([50, 100, 110]), 1), 10.0)
        self.assertIsNone(metrics.cumulative_return(bars([100, 110]), 2))
        self.assertAlmostEqual(metrics.cumulative_return(bars([100, 110, 121]), 2), 21.0)

    def test_average_return_is_arithmetic_not_cumulative_divided_by_n(self):
        data = bars([100, 110, 100])
        self.assertAlmostEqual(metrics.average_daily_return(data, 2), 0.45454545454545)
        self.assertAlmostEqual(metrics.cumulative_return(data, 2), 0.0)

    def test_volatility_uses_percentage_returns_and_sample_ddof(self):
        # Returns +10%, -10%; sample stdev=sqrt(200), not price stdev.
        self.assertAlmostEqual(metrics.daily_volatility(bars([100, 110, 99]), 2), math.sqrt(200))
        self.assertIsNone(metrics.daily_volatility(bars([100, 110]), 1))

    def test_adr_percent(self):
        data = bars([105, 220])
        data["High"], data["Low"] = [110.0, 240.0], [100.0, 200.0]
        self.assertAlmostEqual(metrics.adr_percent(data, 2), 15.0)

    def test_average_dollar_volume_uses_raw_close_and_includes_latest(self):
        data = bars([100, 200])
        data["Volume"] = [1_000_000.0, 2_000_000.0]
        data["Adj Close"] = [1.0, 2.0]
        self.assertEqual(metrics.average_dollar_volume(data, 2), 250.0)

    def test_zero_volume_is_valid(self):
        data = bars([100, 200])
        data["Volume"] = 0.0
        self.assertEqual(metrics.average_dollar_volume(data, 2), 0.0)

    def test_invalid_periods(self):
        for function in WINDOW_METRICS:
            for n in [0, -1, True, 2.5, "2", None]:
                with self.subTest(metric=function.__name__, n=n):
                    with self.assertRaisesRegex(ValueError, "positive integer"):
                        function(bars([100, 110]), n)

    def test_insufficient_history(self):
        for function in WINDOW_METRICS:
            with self.subTest(metric=function.__name__):
                self.assertIsNone(function(bars([100, 110]), 3))

    def test_empty_data_is_unavailable(self):
        data = bars([])
        self.assertIsNone(metrics.latest_price(data))
        self.assertIsNone(metrics.latest_open(data))
        for function in WINDOW_METRICS:
            with self.subTest(metric=function.__name__):
                self.assertIsNone(function(data, 2))

    def test_return_windows_do_not_bridge_invalid_prices(self):
        for bad in [0, -10, float("nan"), float("inf")]:
            data = bars([100, bad, 110])
            for function in [metrics.cumulative_return, metrics.average_daily_return,
                             metrics.daily_volatility]:
                with self.subTest(metric=function.__name__, bad=bad):
                    self.assertIsNone(function(data, 2))

    def test_recursive_metrics_restart_after_invalid_row(self):
        data = bars([100, 110, float("nan"), 10, 12, 11, 13])
        self.assertEqual(metrics.ema(data, 3), metrics.ema(bars([10, 12, 11, 13]), 3))
        self.assertEqual(metrics.rsi(data, 3), metrics.rsi(bars([10, 12, 11, 13]), 3))
        self.assertIsNone(metrics.rsi(data, 4))

    def test_n_one_is_supported_where_defined(self):
        data = bars([100, 110])
        self.assertEqual(metrics.sma(data, 1), 110.0)
        self.assertEqual(metrics.ema(data, 1), 110.0)
        self.assertEqual(metrics.rsi(data, 1), 100.0)

    def test_metrics_are_pure_finite_python_scalars(self):
        data = bars(range(100, 150))
        original = data.copy(deep=True)
        for function in WINDOW_METRICS:
            value = function(data, 14)
            self.assertIs(type(value), float)
            self.assertTrue(math.isfinite(value))
        for function in [metrics.latest_price, metrics.latest_open]:
            self.assertIs(type(function(data)), float)
        pd.testing.assert_frame_equal(data, original)

    def test_nonfinite_outputs_are_unavailable(self):
        data = bars([1e308, 1e308])
        self.assertIsNone(metrics.average_dollar_volume(data, 2))

    def test_average_return_excludes_older_returns(self):
        # Exclude +900%; the requested returns are +10% and -100/11%.
        data = bars([10, 100, 110, 100])
        self.assertAlmostEqual(metrics.average_daily_return(data, 2), 5 / 11)

    def test_volatility_excludes_older_returns(self):
        # Exclude +100%; sample stdev of +10%, -10% is sqrt(200).
        data = bars([50, 100, 110, 99])
        self.assertAlmostEqual(metrics.daily_volatility(data, 2), math.sqrt(200))

    def test_adr_excludes_older_ranges(self):
        data = bars([10, 105, 220])
        data["High"], data["Low"] = [100.0, 110.0, 240.0], [1.0, 100.0, 200.0]
        # Exclude 9900%; the final two ranges are 10% and 20%.
        self.assertAlmostEqual(metrics.adr_percent(data, 2), 15.0)

    def test_dollar_volume_excludes_older_observations(self):
        data = bars([1000, 100, 200])
        data["Volume"] = [1_000_000_000.0, 1_000_000.0, 2_000_000.0]
        # Exclude the old trillion-dollar bar; mean of $100m and $400m.
        self.assertEqual(metrics.average_dollar_volume(data, 2), 250.0)


class MarketDataTests(TestCase):
    def test_symbol_normalization(self):
        for symbol, expected in [(" aapl ", "AAPL"), ("brk-b", "BRK-B"), ("BRK.B", "BRK.B")]:
            self.assertEqual(market_data.normalize_symbol(symbol), expected)

    def test_invalid_symbols_rejected_before_fetch(self):
        with patch.object(market_data.yf, "download") as download:
            for symbol in ["", " ", "../AAPL", "AAPL MSFT", "AAPL,MSFT", "AAPL/", "A$", None, 123]:
                with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                    market_data.fetch_market_data(symbol)
            download.assert_not_called()

    def test_flat_columns_and_explicit_fetch_arguments(self):
        data = bars([100, 110])
        with patch.object(market_data.yf, "download", return_value=data) as download:
            result = market_data.fetch_market_data(" aapl ")
        download.assert_called_once_with(
            "AAPL", period="1y", interval="1d", auto_adjust=False,
            progress=False, threads=False, multi_level_index=False, timeout=10,
        )
        pd.testing.assert_frame_equal(result, data)

    def test_multiindex_both_orientations_and_requested_ticker(self):
        data = bars([100, 110])
        multi = pd.concat({"OTHER": bars([200, 210]), "AAPL": data}, axis=1)
        for response in [multi, multi.swaplevel(axis=1)]:
            with self.subTest(columns=response.columns):
                with patch.object(market_data.yf, "download", return_value=response):
                    pd.testing.assert_frame_equal(market_data.fetch_market_data("AAPL"), data)

    def test_sort_duplicates_preserve_timezone_and_do_not_mutate(self):
        data = bars([100, 110, 120])
        data = data.iloc[[2, 0, 1, 0]].copy()
        data.iloc[-1, data.columns.get_loc("Volume")] = 9.0
        original = data.copy(deep=True)
        result = market_data.normalize_ohlcv(data, "AAPL")
        self.assertTrue(result.index.is_monotonic_increasing)
        self.assertTrue(result.index.is_unique)
        self.assertEqual(str(result.index.tz), "UTC")
        self.assertEqual(result.iloc[0].Volume, 9.0)
        self.assertEqual(len(result), 3)
        pd.testing.assert_frame_equal(data, original)

    def test_numeric_strings_and_extra_columns(self):
        data = bars([100, 110])
        strings = data.astype(str)
        strings["Adj Close"] = [1, 2]
        pd.testing.assert_frame_equal(market_data.normalize_ohlcv(strings, "AAPL"), data)

    def test_missing_or_duplicate_required_fields(self):
        data = bars([100])
        for response in [data.drop(columns="Volume"), pd.concat([data, data[["Close"]]], axis=1)]:
            with self.assertRaisesRegex(ValueError, "unique Open"):
                market_data.normalize_ohlcv(response, "AAPL")

    def test_empty_provider_results(self):
        for response in [None, pd.DataFrame()]:
            with patch.object(market_data.yf, "download", return_value=response):
                with self.assertRaisesRegex(ValueError, "No market data"):
                    market_data.fetch_market_data("AAPL")

    def test_invalid_timestamps(self):
        for index in [pd.RangeIndex(2), pd.DatetimeIndex(["2025-01-01", None])]:
            data = bars([100, 110])
            data.index = index
            with self.assertRaisesRegex(ValueError, "datetime"):
                market_data.normalize_ohlcv(data, "AAPL")

    def test_malformed_numeric_data(self):
        for field, value in [("Close", "bad"), ("Open", float("nan")),
                             ("High", float("inf")), ("Low", 0),
                             ("Volume", -1), ("High", 50), ("Low", 150)]:
            data = bars([100]).astype(object)
            data.loc[data.index[0], field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                market_data.normalize_ohlcv(data, "AAPL")

    def test_unexpected_multiindex_rejected(self):
        data = bars([100])
        for response in [pd.concat({"OTHER": data}, axis=1),
                         pd.concat({"extra": pd.concat({"AAPL": data}, axis=1)}, axis=1)]:
            with self.assertRaises(ValueError):
                market_data.normalize_ohlcv(response, "AAPL")

    def test_provider_exception_has_context_and_cause(self):
        error = TimeoutError("provider timeout")
        with patch.object(market_data.yf, "download", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "AAPL") as caught:
                market_data.fetch_market_data("AAPL")
        self.assertIs(caught.exception.__cause__, error)


class StockServiceTests(TestCase):
    def test_summary_fetches_once_and_shares_same_dataframe(self):
        data = bars(range(100, 150))
        with ExitStack() as stack:
            fetch = stack.enter_context(patch(
                "stocks.services.stock_service.fetch_market_data", return_value=data,
            ))
            spies = [stack.enter_context(patch.object(metrics, function.__name__, wraps=function))
                     for function in (*WINDOW_METRICS, metrics.latest_price, metrics.latest_open)]
            result = StockService(" aapl ").summary()
            fetch.assert_called_once_with("AAPL")
            for spy in spies:
                self.assertEqual(spy.call_count, 1)
                self.assertIs(spy.call_args.args[0], data)
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["as_of"], data.index[-1].isoformat())
        self.assertEqual(result["price"], 149.0)
        self.assertEqual(len(result["metrics"]), 8)
        json.dumps(result, allow_nan=False)

    def test_summary_integration_one_yfinance_download(self):
        with patch.object(market_data.yf, "download", return_value=bars(range(100, 150))) as download:
            StockService("AAPL").summary()
            self.assertEqual(download.call_count, 1)

    def test_short_history_returns_null_metrics_in_strict_json(self):
        with patch("stocks.services.stock_service.fetch_market_data", return_value=bars([100])):
            result = StockService("AAPL").summary()
        self.assertTrue(all(value is None for value in result["metrics"].values()))
        json.dumps(result, allow_nan=False)

    def test_service_does_not_hide_fetch_failure(self):
        with patch("stocks.services.stock_service.fetch_market_data", side_effect=ValueError("No market data")):
            with self.assertRaisesRegex(ValueError, "No market data"):
                StockService("AAPL").summary()


class StockSummaryAPITests(SimpleTestCase):
    def test_success_returns_service_json_and_calls_summary_once(self):
        expected = {
            "symbol": "AAPL", "as_of": "2026-09-18T00:00:00",
            "price": 100.0, "open": 99.0, "metrics": {"sma_20": None},
        }
        with patch("stocks.views.StockService") as service:
            service.return_value.summary.return_value = expected
            response = self.client.get("/api/stocks/AAPL/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), expected)
        json.loads(response.content, parse_constant=lambda value: self.fail(value))
        service.assert_called_once_with("AAPL")
        service.return_value.summary.assert_called_once_with()

    def test_lowercase_uses_real_service_and_one_download(self):
        with patch.object(market_data.yf, "download", return_value=bars(range(100, 150))) as download:
            with patch("stocks.services.stock_service.fetch_market_data", wraps=market_data.fetch_market_data) as fetch:
                response = self.client.get("/api/stocks/aapl/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["symbol"], "AAPL")
        fetch.assert_called_once_with("AAPL")
        self.assertEqual(download.call_count, 1)
        self.assertEqual(download.call_args.args, ("AAPL",))

    def test_malformed_ticker_returns_400_without_fetching(self):
        with patch.object(market_data.yf, "download") as download:
            response = self.client.get("/api/stocks/A$PL/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Invalid ticker symbol."})
        download.assert_not_called()

    def test_empty_provider_response_returns_404(self):
        for empty in [None, pd.DataFrame()]:
            with self.subTest(response=empty):
                with patch.object(market_data.yf, "download", return_value=empty):
                    response = self.client.get("/api/stocks/UNKNOWN/")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"error": "No market data available."})

    def test_provider_exception_returns_502_without_internal_details(self):
        with patch.object(market_data.yf, "download", side_effect=TimeoutError("private provider details")):
            response = self.client.get("/api/stocks/AAPL/")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "Market data provider failed."})

    def test_malformed_provider_response_returns_502_not_400_or_404(self):
        for malformed in [{"Close": [100]}, bars([100]).drop(columns="Volume")]:
            with self.subTest(response=type(malformed).__name__):
                with patch.object(market_data.yf, "download", return_value=malformed):
                    response = self.client.get("/api/stocks/AAPL/")
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json(), {"error": "Market data provider failed."})

    def test_post_is_rejected_without_analysis(self):
        with patch("stocks.views.StockService") as service:
            response = self.client.post("/api/stocks/AAPL/")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")
        service.assert_not_called()

    def test_error_types_distinguish_invalid_ticker_and_missing_data(self):
        with self.assertRaises(market_data.InvalidTicker):
            market_data.normalize_symbol("A$PL")
        with self.assertRaises(market_data.NoMarketData):
            market_data.normalize_ohlcv(pd.DataFrame(), "AAPL")

    def test_malformed_provider_data_preserves_normalization_error_cause(self):
        with patch.object(market_data.yf, "download", return_value=bars([100]).drop(columns="Volume")):
            with self.assertRaisesRegex(RuntimeError, "Invalid market data") as caught:
                market_data.fetch_market_data("AAPL")
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_dated_rows_without_columns_are_provider_failure(self):
        malformed = bars([100]).iloc[:, :0]
        with patch.object(market_data.yf, "download", return_value=malformed):
            response = self.client.get("/api/stocks/AAPL/")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "Market data provider failed."})

    def test_hyphenated_ticker_reaches_real_service(self):
        with patch.object(market_data.yf, "download", return_value=bars(range(100, 150))) as download:
            response = self.client.get("/api/stocks/BRK-B/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["symbol"], "BRK-B")
        self.assertEqual(download.call_count, 1)
        self.assertEqual(download.call_args.args, ("BRK-B",))


class StockHistoryTests(SimpleTestCase):
    def setUp(self):
        self.data = bars(range(100, 108))
        # An older sentinel proves 1y preserves the full supplied dataset.
        self.data.index = pd.to_datetime([
            "2025-09-17", "2026-03-17", "2026-03-18", "2026-06-17",
            "2026-06-18", "2026-08-17", "2026-08-18", "2026-09-18",
        ]).tz_localize("America/New_York")

    def test_exact_payload_all_ranges_and_one_download_each(self):
        for history_range, start in [(None, 4), ("1m", 6), ("3m", 4), ("6m", 2), ("1y", 0)]:
            with self.subTest(history_range=history_range):
                expected = {
                    "symbol": "BRK-B", "range": history_range or "3m",
                    "as_of": "2026-09-18T00:00:00-04:00",
                    "data": [
                        {"date": self.data.index[i].date().isoformat(),
                         "open": float(100 + i), "high": float(101 + i),
                         "low": float(99 + i), "close": float(100 + i),
                         "volume": 1_000_000.0}
                        for i in range(start, 8)
                    ],
                }
                with patch.object(market_data.yf, "download", return_value=self.data.iloc[::-1]) as download:
                    with patch("stocks.services.stock_service.fetch_market_data", wraps=market_data.fetch_market_data) as fetch:
                        response = self.client.get(
                            "/api/stocks/brk-b/history/",
                            {} if history_range is None else {"range": history_range},
                        )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/json")
                self.assertEqual(response.json(), expected)
                json.loads(response.content, parse_constant=lambda value: self.fail(value))
                fetch.assert_called_once_with("BRK-B")
                self.assertEqual(download.call_count, 1)
                self.assertEqual(download.call_args.args, ("BRK-B",))

    def test_calendar_month_end_includes_leap_day_cutoff(self):
        data = bars([100, 101, 102])
        data.index = pd.to_datetime(["2024-02-28", "2024-02-29", "2024-03-31"])
        with patch("stocks.services.stock_service.fetch_market_data", return_value=data):
            result = StockService("AAPL").history("1m")
        self.assertEqual([row["date"] for row in result["data"]], ["2024-02-29", "2024-03-31"])

    def test_service_returns_builtin_scalars_without_mutating_frame(self):
        original = self.data.copy(deep=True)
        with patch("stocks.services.stock_service.fetch_market_data", return_value=self.data) as fetch:
            result = StockService(" aapl ").history()
        self.assertEqual(result["symbol"], "AAPL")
        for value in (result["symbol"], result["range"], result["as_of"]):
            self.assertIs(type(value), str)
        for row in result["data"]:
            self.assertIs(type(row["date"]), str)
            for key in ("open", "high", "low", "close", "volume"):
                self.assertIs(type(row[key]), float)
                self.assertTrue(math.isfinite(row[key]))
        json.dumps(result, allow_nan=False)
        pd.testing.assert_frame_equal(self.data, original)
        fetch.assert_called_once_with("AAPL")

    def test_invalid_range_rejected_before_retrieval(self):
        for history_range in ("", "2m", "1d", "1M", "max"):
            with self.subTest(history_range=history_range):
                with patch("stocks.services.stock_service.fetch_market_data") as fetch:
                    with patch.object(market_data.yf, "download") as download:
                        response = self.client.get("/api/stocks/AAPL/history/", {"range": history_range})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"error": "Invalid history range."})
                fetch.assert_not_called()
                download.assert_not_called()

    def test_invalid_ticker_rejected_before_download(self):
        with patch.object(market_data.yf, "download") as download:
            response = self.client.get("/api/stocks/A$PL/history/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Invalid ticker symbol."})
        download.assert_not_called()

    def test_no_data_returns_404(self):
        for empty in (None, pd.DataFrame()):
            with self.subTest(empty=type(empty).__name__):
                with patch.object(market_data.yf, "download", return_value=empty):
                    response = self.client.get("/api/stocks/AAPL/history/")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"error": "No market data available."})

    def test_provider_and_schema_failures_return_fixed_502(self):
        for failure in (TimeoutError("private details"), self.data.drop(columns="Volume")):
            with self.subTest(failure=type(failure).__name__):
                with patch.object(market_data.yf, "download", side_effect=[failure]):
                    response = self.client.get("/api/stocks/AAPL/history/")
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json(), {"error": "Market data provider failed."})

    def test_nonfinite_provider_values_never_reach_json(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                malformed = self.data.copy()
                malformed.iloc[-1, malformed.columns.get_loc("Close")] = value
                with patch.object(market_data.yf, "download", return_value=malformed):
                    response = self.client.get("/api/stocks/AAPL/history/")
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json(), {"error": "Market data provider failed."})

    def test_post_returns_405_without_constructing_service(self):
        with patch("stocks.views.StockService") as service:
            response = self.client.post("/api/stocks/AAPL/history/")
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")
        service.assert_not_called()


class StockComparisonTests(SimpleTestCase):
    def test_two_and_three_exact_summaries_order_and_call_counts(self):
        for requested, symbols in [(" brk-b , aapl ", ["BRK-B", "AAPL"]),
                                   (" nvda, brk-b ,aapl", ["NVDA", "BRK-B", "AAPL"])]:
            with self.subTest(requested=requested):
                # One bar makes all eight window metrics unavailable; summary
                # prices identify each input's result independently of ordering.
                expected = [
                    {"symbol": symbol, "as_of": "2025-01-01T00:00:00+00:00",
                     "price": float(100 + i), "open": float(100 + i),
                     "metrics": {key: None for key in (
                         "sma_20", "ema_20", "rsi_14", "return_30d", "average_return_30d",
                         "volatility_20d", "adr_20d", "average_dollar_volume_20d",
                     )}}
                    for i, symbol in enumerate(symbols)
                ]
                with patch.object(market_data.yf, "download", side_effect=[bars([100 + i]) for i in range(len(symbols))]) as download:
                    with patch("stocks.services.stock_service.fetch_market_data", wraps=market_data.fetch_market_data) as fetch:
                        with patch.object(StockService, "summary", autospec=True, side_effect=StockService.summary) as summary:
                            response = self.client.get("/api/compare/", {"symbols": requested})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"symbols": symbols, "results": expected})
                json.loads(response.content, parse_constant=lambda value: self.fail(value))
                self.assertEqual([call.args[0].symbol for call in summary.call_args_list], symbols)
                self.assertEqual([call.args[0] for call in fetch.call_args_list], symbols)
                self.assertEqual([call.args[0] for call in download.call_args_list], symbols)

    def test_all_invalid_inputs_rejected_before_summary_or_network(self):
        for requested in (None, "", "AAPL", "AAPL,NVDA,MSFT,QCOM", "AAPL,AAPL",
                          "aapl, AAPL", "AAPL,NVDA,A$PL", "AAPL,", ",AAPL", "AAPL,,NVDA"):
            with self.subTest(requested=requested):
                with patch.object(StockService, "summary") as summary:
                    with patch.object(market_data.yf, "download") as download:
                        response = self.client.get("/api/compare/", {} if requested is None else {"symbols": requested})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(set(response.json()), {"error"})
                summary.assert_not_called()
                download.assert_not_called()

    def test_failure_of_second_symbol_is_atomic_and_stops_further_fetches(self):
        for failure, status, error in (
            (None, 404, "No market data available."),
            (pd.DataFrame(), 404, "No market data available."),
            (TimeoutError("private details"), 502, "Market data provider failed."),
            (bars([100]).drop(columns="Volume"), 502, "Market data provider failed."),
        ):
            with self.subTest(failure=type(failure).__name__):
                with patch.object(market_data.yf, "download", side_effect=[bars([100]), failure]) as download:
                    response = self.client.get("/api/compare/", {"symbols": "AAPL,NVDA,QCOM"})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), {"error": error})
                self.assertEqual([call.args[0] for call in download.call_args_list], ["AAPL", "NVDA"])

    def test_post_returns_405_without_constructing_service(self):
        with patch("stocks.views.StockService") as service:
            response = self.client.post("/api/compare/", {"symbols": "AAPL,NVDA"})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")
        service.assert_not_called()
