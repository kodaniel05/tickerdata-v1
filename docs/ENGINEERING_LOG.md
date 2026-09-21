# Engineering log

## Phase 1 — Core Market Data and Metric Engine

### Date

2026-09-20

### Goal

Build a small, reusable and verifiable daily-stock engine with one historical
fetch per summary. Establish financial definitions before calculations, retain
timestamps, validate provider data, and replace duplicated calculation behavior
in the new service without modifying the historical scripts.

### Files changed

Ranges below refer to CURRENT post-change files, checked with numbered source
output and Python AST locations. All service files and both documents are new;
only the existing empty `backend/stocks/tests.py` was modified.

`backend/stocks/services/__init__.py`
- Line 1 — package description; allows reusable imports without Django setup.

`backend/stocks/services/market_data.py`
- Lines 1–9 — imports and required OHLCV fields; one explicit provider boundary.
- Lines 12–18 — `normalize_symbol()` strips/uppercases and validates equity-style
  syntax before requests, preventing malformed and multi-symbol input.
- Lines 21–55 — `normalize_ohlcv()` selects the requested ticker from flat or
  hierarchical columns, preserves/sorts dates, keeps the last duplicate, coerces
  numbers and rejects invalid bars; avoids fabricated or ambiguous observations.
- Lines 58–67 — `fetch_market_data()` performs one bounded, nonthreaded daily
  download with explicit adjustment/timeout options and contextual exceptions.

`backend/stocks/services/metrics.py`
- Lines 1–5 — pure calculation module imports; no provider dependency.
- Lines 8–10 — `_validate_period()` rejects noninteger/nonpositive periods.
- Lines 13–15 — `_finite()` enforces finite Python float or None output.
- Lines 18–21 — `_column()` coerces numeric input and masks invalid observations.
- Lines 24–29 — `_close_sequence()` prevents recursive metrics bridging bad rows.
- Lines 32–37 — `_returns()` requires N+1 closes and disables implicit filling.
- Lines 40–42 — `latest_price()` uses the final bar's Close without another fetch.
- Lines 45–47 — `latest_open()` uses the same final bar's Open.
- Lines 50–53 — `sma()` averages the latest N valid closes.
- Lines 56–64 — `ema()` uses an explicit arithmetic seed and recursive weighting.
- Lines 67–81 — `rsi()` uses Wilder's arithmetic seed/smoothing and flat-data None.
- Lines 84–89 — `cumulative_return()` measures N returns using N+1 observations.
- Lines 92–94 — `average_daily_return()` averages individual percentage returns.
- Lines 97–101 — `daily_volatility()` uses sample return stdev, not price stdev.
- Lines 104–108 — `adr_percent()` implements the documented percentage range.
- Lines 111–116 — `average_dollar_volume()` uses raw Close times Volume in millions.
  These pure functions provide one implementation with explicit units, history
  requirements and unavailable results, replacing the old inconsistent behavior
  for callers of the new engine. They never modify the supplied DataFrame.

`backend/stocks/services/stock_service.py`
- Lines 1–4 — imports the market-data boundary and pure metrics.
- Lines 7–28 — `StockService`, comprising `__init__()` (8–9) and `summary()`
  (11–28), normalizes the symbol and passes one fetched frame to every metric.
  Returns a plain dictionary with an ISO session timestamp for future JSON use.

`backend/stocks/tests.py`
- Lines 1–12 — standard-library unittest/mock and existing pandas imports.
- Lines 15–22 — `bars()` builds deterministic, dated OHLCV fixtures.
- Lines 25–29 — shared metric list for consistent boundary and purity checks.
- Lines 32–176 — `MetricTests`: known-answer SMA/EMA/RSI/returns/volatility/ADR/ADV,
  latest-bar selection, invalid N, missing/short history, scalar types, no mutation,
  gap handling, zero volume, length one and nonfinite output rejection.
- Lines 179–268 — `MarketDataTests`: symbol validation, exact download arguments,
  flat/MultiIndex schemas, dates/duplicates, numeric conversion, missing fields,
  empty/malformed data and upstream exceptions. All provider calls are mocked.
- Lines 271–305 — `StockServiceTests`: one retrieval, identical shared frame for
  all metrics, one end-to-end mocked download, strict JSON and error propagation.
  Tests establish financial correctness and performance without a live provider
  or database. The Django runner discovers these unittest.TestCase classes.

`docs/METRICS.md`
- Lines 1–29 — raw-price, timestamp, validation and availability contract.
- Lines 31–53 — exact formulas, units, seeds, boundaries and worked examples.
- Lines 55–65 — summary schema, single-fetch behavior and failure policy.
  Created before implementation so behavior can be reviewed independently.

`docs/ENGINEERING_LOG.md`
- Lines 1–203 — this document records scope, changed functions, verified ranges,
  behavioral differences, validation evidence and limitations for human review.

### Behavioral changes

- Latest Open and Close come from the same dated historical response; no separate
  quote requests or artificial current-day row. Positional access uses iloc.
- All metrics share normalized flat OHLCV; no MultiIndex/flat concat mismatch.
- Cumulative return is percentage return over N trading periods (N+1 prices).
- Average return is the arithmetic daily-return mean; 100 → 110 → 100 gives
  approximately 0.454545%, not zero.
- Volatility is sample daily-return standard deviation in percentage points,
  unannualized. ADR% is explicitly percentage-based, not ATR.
- EMA and RSI use the specified arithmetic seeds; flat RSI is unavailable.
- Invalid periods raise ValueError; insufficient history yields None. Successful
  scalar results are finite Python floats and serialize with allow_nan=False.
- Legacy scripts remain unchanged and are not redirected to this service yet.

### Dependencies

Added: none. Removed: none.
Unchanged: Django==6.1.1, pandas==3.0.2, yfinance==1.7.0 and existing transitives.
No runtime dependencies were added. No package installations/upgrades were run.
No pandas-ta, DRF, CORS package, pytest, Redis or application cache was added.

### Validation and command record

Commands ran from the repository root unless a backend working directory is
specified. Long diagnostic heredocs are described by their executed contents.

- `pwd`; `git branch --show-current`; `git status`; `git diff` — PASS: correct
  repository, v1-foundation, clean initial tree; no unrelated changes to preserve.
- Initial `python --version`; `which python`; `python -m pip check` — FAILED:
  the tool shell had not activated the repository environment (command not found).
- `ls -ld .venv .venv/bin/python`; `source .venv/bin/activate`; `python --version`;
  `which python`; `python -m pip check` — PASS: repository-local Python 3.13.7,
  no broken requirements. Activation was per shell; no shell config was edited.
- `rg --files --hidden` with dependency/cache exclusions and `cat` of requirements,
  ignore rules and existing Django files — inspected current tracked scaffold.
- Python heredoc: `inspect.signature(yfinance.download)` and installed package
  metadata — PASS; verified support for chosen interval, adjustment, threading,
  progress, timeout and multi_level_index arguments in installed yfinance 1.7.0.
- Backend: `source ../.venv/bin/activate`; `python manage.py check` — PASS, zero
  issues. `python manage.py test stocks` — PASS, 39 deterministic tests.
- Root, activated environment: `python -m pip check` — PASS after implementation.
- Backend live Python heredoc: wrap the real service fetch and yf.download with
  mock spies, capture the real frame, call `StockService('QCOM').summary()`, assert
  schema, ordering, unique DatetimeIndex, timestamp correspondence, float/None
  results and `json.dumps(..., allow_nan=False)` — PASS. 251 OHLCV rows;
  as_of 2026-09-18T00:00:00; one service fetch and one yf.download call. No market
  price assertions. No KeyError or MultiIndex/concat error. Eight summary metrics.
- `git diff --check` — PASS. `git diff --stat`; `git diff` (including targeted
  tests diff); `git diff --name-only`; `git status --short` — reviewed scope.
  Untracked files were reviewed directly and with `git diff --no-index --check /dev/null <file>`.
- `nl -ba` on final source/documents and Python AST line-range inspection — checked
  actual post-change locations; no guessed function ranges.
- Initial untracked-file check wrapper incorrectly required exit 0: FAILED.
  Corrected it to accept exit 1 for new-file differences and no diagnostics: PASS.

### Performance

Old successful-path SMA+EMA+RSI: the earlier read-only audit's mocked probe counted
3 historical downloads plus 3 Open and 3 Close helpers (each invokes history),
or 9 high-level fetch/history calls. This describes the intended successful path;
the unmodified legacy implementation still fails under current dependencies.

New full summary: deterministic tests confirm 1 market-data retrieval, 1 top-level
download through the real normalization path, and the same DataFrame object at all
10 metric functions. Live QCOM independently confirmed 1 top-level download.
These are library call counts, not underlying HTTP request counts or latency claims.
No caching layer was introduced. Calling summary again intentionally fetches again.

### Known limitations and scope review

- Raw prices are not split/dividend adjusted; returns are not total returns.
- Latest daily bar may be partial/stale. No exchange-calendar completeness check.
- One-year EMA/RSI warm-up is bounded; newly listed equities may yield None.
- A malformed retained OHLCV row rejects the response rather than silently
  dropping or filling it. A missing session absent from Yahoo cannot be detected
  without a trading calendar; returns are between supplied observations.
- Dollar-volume naming assumes USD equities; no currency lookup/conversion. Other
  accepted listings return millions of their quote currency, as documented.
- Yahoo can suppress an error and return empty data; this produces a data
  ValueError, without reliably distinguishing invalid listings from an outage.
- Syntax validation is intentionally equity-focused, not all Yahoo symbol types.
- The only class is the requested small service coordinator; helpers centralize
  repeated validation/calculation work. No speculative abstractions or settings.
- No API, frontend, models, auth, jobs, migrations or Django registration changes.
- Git branch/remotes and legacy files unchanged. No staging, commit or push.

## Phase 1 — Acceptance Review (2026-09-20)

Result: ACCEPT WITH FIXES to tests only; production engine and metric contract
remain unchanged. Review read the actual diff and every untracked Phase 1 file.
Formulas, observation counts, seeds, units, normalization and failure behavior
match METRICS.md. Dependencies and architecture remain minimal.

Defect: the original 39 tests accepted deliberately incorrect all-history windows
for average return, volatility, ADR% and dollar volume. In-memory mutation probes
demonstrated the gap; no incorrect production implementation was written to disk.

Additional changes in `backend/stocks/tests.py` (verified post-change lines):
- 156–159 — `test_average_return_excludes_older_returns()`: excludes +900%; expects 5/11%.
- 161–164 — `test_volatility_excludes_older_returns()`: excludes +100%; expects sqrt(200).
- 166–170 — `test_adr_excludes_older_ranges()`: excludes 9900%; expects 15%.
- 172–176 — `test_dollar_volume_excludes_older_observations()`: excludes $1tn; expects $250m.
These four manual-answer regressions protect the requested trailing windows.
This log updates affected class ranges above and records the acceptance results.

Revalidation: repository-local `python -m pip check` PASS; backend
`python manage.py check` PASS; `python manage.py test stocks` PASS (43 tests).
The three deliberate in-memory mutants are now caught by those four new tests.
`git diff --check` and untracked-file whitespace checks PASS. `nl -ba` plus AST
inspection verified source locations; requirements and excluded areas have no diff.

Mock trace: one service fetch, one yf.download, zero direct Ticker/Tickers calls;
all ten metric functions receive the identical normalized DataFrame. Independent
live QCOM rerun PASS: 251 rows, as_of 2026-09-18T00:00:00, one download, finite/null
Python scalars and strict JSON. This does not count yfinance's internal HTTP calls.
No dependencies, runtime source, API or frontend changes; no commit or push.
