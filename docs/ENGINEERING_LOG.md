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
- Lines 20–26 — `normalize_symbol()` strips/uppercases and validates equity-style
  syntax before requests, preventing malformed and multi-symbol input.
- Lines 29–65 — `normalize_ohlcv()` selects the requested ticker from flat or
  hierarchical columns, preserves/sorts dates, keeps the last duplicate, coerces
  numbers and rejects invalid bars; avoids fabricated or ambiguous observations.
- Lines 68–82 — `fetch_market_data()` performs one bounded, nonthreaded daily
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
- Lines 1–6 — imports pandas, the market-data boundary and pure metrics.
- Lines 9–56 — `StockService`, including `__init__()` (10–11) and `summary()`
  (13–30), normalizes the symbol and passes one fetched frame to every metric.
  Returns a plain dictionary with an ISO session timestamp for future JSON use.

`backend/stocks/tests.py`
- Lines 1–13 — standard-library unittest/mock, pandas and Django test imports.
- Lines 16–23 — `bars()` builds deterministic, dated OHLCV fixtures.
- Lines 26–30 — shared metric list for consistent boundary and purity checks.
- Lines 33–177 — `MetricTests`: known-answer SMA/EMA/RSI/returns/volatility/ADR/ADV,
  latest-bar selection, invalid N, missing/short history, scalar types, no mutation,
  gap handling, zero volume, length one and nonfinite output rejection.
- Lines 180–269 — `MarketDataTests`: symbol validation, exact download arguments,
  flat/MultiIndex schemas, dates/duplicates, numeric conversion, missing fields,
  empty/malformed data and upstream exceptions. All provider calls are mocked.
- Lines 272–306 — `StockServiceTests`: one retrieval, identical shared frame for
  all metrics, one end-to-end mocked download, strict JSON and error propagation.
  Tests establish financial correctness and performance without a live provider
  or database. The Django runner discovers these unittest.TestCase classes.

`docs/METRICS.md`
- Lines 1–29 — raw-price, timestamp, validation and availability contract.
- Lines 31–53 — exact formulas, units, seeds, boundaries and worked examples.
- Lines 55–67 — summary schema, single-fetch behavior and failure policy.
  Created before implementation so behavior can be reviewed independently.

`docs/ENGINEERING_LOG.md`
- Lines 1–430 — this document records scope, changed functions, verified ranges,
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
- 157–160 — `test_average_return_excludes_older_returns()`: excludes +900%; expects 5/11%.
- 162–165 — `test_volatility_excludes_older_returns()`: excludes +100%; expects sqrt(200).
- 167–171 — `test_adr_excludes_older_ranges()`: excludes 9900%; expects 15%.
- 173–177 — `test_dollar_volume_excludes_older_observations()`: excludes $1tn; expects $250m.
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

## Phase 2A — Minimal Django Stock Summary API

Date: 2026-09-20.

### Goal

Expose the validated summary through one Django JSON endpoint, preserving the
one-fetch contract and existing calculations. No API framework or database work.

### Files changed (current post-change ranges)

- `backend/config/settings.py`, line 40 — `INSTALLED_APPS`: registers StocksConfig
  so Django recognizes the existing application; unrelated defaults unchanged.
- `backend/config/urls.py`, lines 18 and 22 — imports `include` and mounts the stock
  URL configuration (now at `api/` after Phase 2B); existing admin route retained.
- `backend/stocks/urls.py`, lines 1–9 — `urlpatterns`, with the summary route at
  line 6, named `stock-summary`; still provides `/api/stocks/<ticker>/`.
- `backend/stocks/views.py`, lines 1–18 — imports and `stock_summary()` (decorator
  at 8, function 9–18): calls StockService once, returns its dictionary directly,
  maps known failures, and uses require_GET and strict JSON serialization.
- `backend/stocks/services/market_data.py`, lines 12–17 — `InvalidTicker` and
  `NoMarketData`: two small ValueError subclasses distinguish client/data failures.
  `normalize_symbol()` (20–26) now raises InvalidTicker; `normalize_ohlcv()`
  (29–65, changed empty/schema checks 32–35) distinguishes empty data from malformed
  non-DataFrames. `fetch_market_data()` (68–82, added 77–82) preserves NoMarketData
  and wraps malformed downloaded data as RuntimeError, preserving the cause.
- `backend/stocks/tests.py`, line 10 and lines 309–396 — SimpleTestCase import and
  `StockSummaryAPITests`: eleven tests cover JSON success/nulls, normalization, call
  counts, 400/404/502, malformed provider data, POST rejection and error types/causes.
  Existing Phase 1 tests are unchanged apart from the added import shifting lines.
- `docs/METRICS.md`, lines 61–67 — updates exception contract and HTTP mapping;
  no formula, successful-response or observation-window changes.
- `docs/ENGINEERING_LOG.md`, lines 205–282 — adds this phase's record; references
  in lines 27–84 and 186–189 are updated to the current source locations.

### Behavioral changes and limitations

GET `/api/stocks/<ticker>/` returns the service dictionary as HTTP 200 JSON.
InvalidTicker maps to 400 `{"error":"Invalid ticker symbol."}`; NoMarketData maps
to 404 `{"error":"No market data available."}`; RuntimeError maps to 502
`{"error":"Market data provider failed."}`. No exception text is exposed.
Other methods reaching the view receive Django's normal 405 with Allow: GET;
standard middleware, including CSRF handling, is unchanged.

Phase 1 previously used ValueError for multiple failure categories. The two
subclasses preserve existing ValueError callers; malformed fetched data now raises
RuntimeError so a provider schema failure is not blamed on ticker input. Direct
normalization still raises ValueError for malformed data. The existing broad catch
is confined to the third-party download boundary; no broad catch was added in the
view. Suppressed Yahoo errors can still become empty responses and therefore 404;
that means data unavailable, not confirmed nonexistent listing. Development-only
Django settings remain unchanged; this phase does not claim deployment readiness.

### Dependencies and complexity

No runtime dependencies were added. Existing requirements are unchanged. One view,
one URL entry, two error types; no serializers, caches, models or helper frameworks.
No frontend, metric-calculation or StockService changes. No migrations were run.

### Validation and performance

Safety checks confirmed a clean v1-foundation tree, repository-local Python 3.13.7,
and healthy dependencies before editing. After implementation:
- `python -m pip check` — PASS.
- Backend `python manage.py check` — PASS, zero issues.
- Backend `python manage.py test stocks` — PASS, 52 tests (43 Phase 1 + 9 new).
- `git diff --check` — PASS; full diff and untracked URL file inspected.
- `nl -ba` and AST inspection — verified the current source ranges above.
- Live local Django Client GET `/api/stocks/QCOM/` through middleware and routing,
  with real Yahoo data — PASS, HTTP 200, strict JSON, symbol/as_of/eight metrics,
  finite Python numbers or None, as_of 2026-09-18T00:00:00. Spies measured exactly
  one summary call, one market-data service call and one top-level yf.download.
- GET `/api/stocks/A$PL/` — PASS, HTTP 400 JSON and zero downloads.

No listening development server was needed or left running. These smoke checks
used the real Django request stack in-process; they do not test a network listener.
Counts describe application calls, not internal Yahoo HTTP requests. No commit,
push, remote changes, dependency installation or staging occurred.

## Phase 2A — Acceptance Review (2026-09-21)

ACCEPT WITH FIXES. `normalize_ohlcv()` in
`backend/stocks/services/market_data.py`, line 32, now checks for zero rows rather
than DataFrame.empty. A frame with dated rows but no columns was incorrectly 404;
it now follows schema validation and returns 502. None/zero-row responses remain
404. No view, routing, metric, dependency or frontend changes were needed.

`backend/stocks/tests.py`, lines 383–388 adds
`test_dated_rows_without_columns_are_provider_failure()`; verified failing before
the fix (404 != 502), then passing. Lines 390–396 adds
`test_hyphenated_ticker_reaches_real_service()` for the missing BRK-B endpoint case.
This log updates the current test-class range and records this acceptance pass.

Validation: pip check PASS; manage.py check PASS; manage.py test stocks PASS
(54 tests); git diff --check PASS; untracked stocks/urls.py whitespace PASS.
AST comparison confirmed all Phase 1 test/helper bodies retain their meaning.
Routing probes passed AAPL/aapl/BRK-B, malformed input, the normal missing-slash
301 redirect, unrelated-path 404 and unchanged admin resolution. Unsupported
methods reaching the view return 405 without constructing the service. Standard
CSRF enforcement rejects a tokenless POST earlier with 403 and no analysis.

Independent mock and post-fix live QCOM request traces passed: view=1, summary=1,
market-data retrieval=1, yf.download=1; no additional application-level Yahoo calls
in the mock trace. HTTP 200 JSON has the exact summary keys, finite floats/null,
string as_of (2026-09-18T00:00:00 live), and eight metrics. Malformed ticker returns
400 with zero downloads. Programming TypeError propagates to Django; handled
service errors contain only fixed public messages. Development DEBUG remains a
deployment limitation. No server was left running; nothing staged, committed or pushed.

## Phase 2B — History and Comparison API

Date: 2026-09-21.

### Goal and changed files (current post-change ranges)

Add daily chart history and 2–3-stock comparison using the existing data path.
Preserve summary calculations and stop backend feature work at this scope.
Ranges below were checked with `nl -ba` after implementation.

- `backend/config/urls.py`, line 22 — `urlpatterns` mounts stocks at `api/`,
  allowing comparison alongside stock routes without another URL module.
- `backend/stocks/urls.py`, lines 3–9 — view imports and `urlpatterns` preserve
  summary at line 6 and add history at 7 and comparison at 8.
- `backend/stocks/services/stock_service.py`, lines 1–6 — description/imports;
  reuses existing pandas dependency for calendar offsets. `StockService` (9–56)
  adds `history()` (32–56): validate range before retrieval, slice one normalized
  frame locally, serialize six chart fields into built-in strings/floats.
  Existing `__init__()` (10–11) and `summary()` (13–30) bodies are unchanged.
- `backend/stocks/views.py`, lines 21–33 — `stock_history()` (22–33, decorator 21)
  maps request range and known failures to strict JSON. Lines 36–56 —
  `stock_compare()` (37–56, decorator 36) validates all symbols before network
  access, preserves order, rejects duplicates, then composes existing summaries.
  `stock_summary()` (8–18 including decorator) is unchanged.
- `backend/stocks/tests.py`, lines 399–508 — `StockHistoryTests`: nine tests for
  exact payloads, all/default ranges, inclusive boundaries, leap-month cutoff,
  Python types, frame purity, one fetch/download, input/data/provider errors,
  nonfinite rejection and POST. Lines 511–569 — `StockComparisonTests`: four
  tests for exact 2/3-summary payloads, order/normalization, counts, invalid-input
  rejection before network, atomic failures and POST. Existing 54 tests unchanged.
- `docs/ENGINEERING_LOG.md`, lines 57–59, 84 and 219–221 — refresh prior current
  references; lines 314–390 — this phase's contracts, evidence and limitations.
  No metric/data calculation contract changed, so `docs/METRICS.md` is unchanged.

### Endpoint contracts and errors

GET `/api/stocks/<ticker>/history/?range=3m` supports only `1m`, `3m`, `6m`, `1y`;
omission defaults to `3m`. Month ranges include timestamps at/after the latest
available bar minus 1/3/6 calendar months, including the cutoff; month ends clamp
to the last valid day. `1y` returns the full fetched year. Result keys are
`symbol`, `range`, `as_of`, `data`; chronological rows contain only `date` (ISO
YYYY-MM-DD), `open`, `high`, `low`, `close`, `volume` (finite Python floats).
`as_of` is the latest dataset timestamp in ISO format, retaining any timezone.
GET `/api/compare/?symbols=AAPL,NVDA` requires 2–3 unique normalized symbols;
whitespace/case use existing validation. Returns `symbols` and `results` in input
order, with unmodified summary dictionaries. No ranking or additional metrics.
Both return 200 on success, 400 for invalid input, 404 for unavailable data, 502
for provider/schema failure, and normal require_GET 405 when reached. Fixed
messages: `Invalid ticker symbol.`, `Invalid history range.`,
`Provide 2 or 3 unique ticker symbols.`, `No market data available.`, and
`Market data provider failed.` Comparison failure is atomic with no partial data;
processing stops at the first fetch failure. All input validates before fetching.

### Validation, performance, dependencies and limitations

Baseline: clean `v1-foundation`, Phase 2A committed as `ac2e5c0`, local .venv
Python 3.13.7, healthy dependencies, Django check PASS and 54 tests PASS.
Final: pip check PASS; Django check PASS; 67 tests PASS (54 existing + 13 new);
git diff --check PASS. Full diff/status inspected; no new untracked files.
AST comparison confirmed existing service/view/test function bodies unchanged.
Deterministic spies verified history = 1 retrieval/1 download for every range;
comparison N=2 and N=3 = N summary calls/N retrievals/N downloads in input order.
Live in-process Django Client (localhost), real Yahoo: QCOM history 1m HTTP 200,
strict JSON, 23 ascending rows from 2026-08-18 through as_of 2026-09-18T00:00:00;
1 retrieval/1 download. QCOM,AAPL comparison HTTP 200, correct order, strict JSON,
2 summaries/2 retrievals/2 downloads, 0.749 seconds wall clock (diagnostic only).
Invalid QCOM,A$PL comparison: 400, zero downloads. Source inspection confirms
the only application-level yfinance data call is yf.download; counts exclude
provider-internal HTTP requests. No listening server was needed or left running.
No runtime dependencies were added; requirements.txt is unchanged. Runtime diff:
72 added/4 removed lines (net +68, including whitespace), three new functions/
methods, zero new classes/files. No duplicate metric/data path, extra frame copy,
cache, concurrency or speculative helpers; fixed HTTP error mapping repeats the
small existing view pattern. Limits: daily only, at most the fetched one-year
history, atomic sequential comparisons, no cache; Yahoo availability and existing
development-only settings remain limitations. No frontend changes, staging,
commits, pushes, remote changes or dependency installations.

## Phase 2B — Acceptance Review (2026-09-21)

ACCEPT WITH FIXES to test data only; no runtime defect found. All requested
source/documents and the current diff were reviewed before editing. The existing
1y fixture could not distinguish full-dataset passthrough from a new yearly
cutoff. A deliberate in-memory re-cut implementation passed the original tests.
`backend/stocks/tests.py`, `StockHistoryTests.setUp()` (400–406), now includes
an older sentinel (comment 402, date 404); the existing exact-payload test
(408–434) now rejects that implementation. No new test method or runtime change.
Current class ranges are history 399–508 and comparison 511–569.

Mutation checks with a passing original-code control also rejected fixed
30/90/180-day windows, exclusive cutoffs, all-history windows, dropped latest
rows, reversed order and duplicate retrievals. Temporary harness setup errors
were corrected before using these results; no mutants were written to disk.
Independent month-end probes confirmed 2026-03-31 minus 1 month and 2026-05-31
minus 3 months both include 2026-02-28 and exclude 2026-02-27. Leap-year behavior
remains covered. Strict JSON probes confirmed six row fields, distinct Open/Close
values, finite numbers, ascending dates and no extra provider columns.

Independent mock traces: history = 0 summaries/1 retrieval/1 normalization/
1 download; two/three-stock comparisons = 2/3 of each. Additional direct
Ticker/Tickers calls = 0. AAPL,BAD/SYMBOL = 400 with zero summaries/retrievals/
downloads. Later valid-symbol no-data/provider/schema failures = 404/502 with
no partial payload or third fetch; earlier successful fetches can already have
occurred. Input validation, unlike provider failures, completes before any fetch.
All three routes, admin resolution, unrelated 404, slash redirect, GET-only 405
and standard middleware CSRF 403 were verified. Views and dependencies stay small.

Revalidation: pip check PASS; Django check PASS; all 67 tests PASS (0.246s),
including the preexisting 54; git diff --check PASS. Live rerun after deterministic
validation: QCOM history 1m HTTP 200, strict JSON, 21 ascending rows from 2026-08-21
through as_of 2026-09-21T00:00:00, 1 retrieval/1 download. QCOM,AAPL comparison
HTTP 200, correct order, strict JSON, 2 summaries/2 retrievals/2 downloads;
0.635 seconds wall clock, diagnostic only. Counts exclude provider-internal HTTP.
Requirements and METRICS.md remain unchanged; daily/year-bounded, sequential,
atomic, no-cache and development-settings limitations remain accurately recorded.
This section and current references were checked with nl -ba. No frontend work,
dependencies, staging, commits, pushes, remote changes or server left running.
