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
