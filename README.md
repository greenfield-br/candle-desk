# Candle Desk

Daily, locally stored market history. Download/update with cron; use the app only for plotting.

## Commands

From this directory, with your Python environment active:

```bash
python -m pip install -r requirements.txt
python update.py
python app.py
```

Plotting address: http://127.0.0.1:8765

The initial update downloads full histories. Later updates refresh a 30-day overlap. A full history refresh runs on the first day of each month to capture historical revisions. `python update.py --full` forces it. Each symbol is independent: failures preserve its local history and do not stop other symbols.

```bash
python update.py --only BTCUSDT ETHUSDT SOLUSDT LINKUSDT ZECUSDT XMRUSDT
python update.py --only SPY QQQ NVDA SPCX
python update.py --only BOVA11 DOLA11 PETR4 VALE3 RECV3 BEEF3
python update.py --only DXY US10Y MOVE 'CL1!' 'GC1!' 'SI1!' WREPO
python update.py --only USDT_MCAP USDC_MCAP OUSD_MCAP
```

`logs/symbol_status.json` keeps the latest status across partial runs. `logs/latest_update.json` records status, stored date range, last observation, failures and fallbacks for each symbol. Each run also has a timestamped report. Exit codes: 0 = no failed/stale/unavailable symbols; 1 = failed, stale or unavailable symbols; retired history is labelled but is not a failed job; 75 = another update holds the lock.

## Cron

```bash
python cron_entry.py
crontab -e
```

`cron_entry.py` prints the exact line for this installation's path and current Python interpreter. Add that line to your crontab. The configured schedule is 04:15 daily in the cron host's timezone. Change the JSON schedule and regenerate the line if needed. No cron job is installed by this package.

## Configuration

- `update_symbols.json`: exactly your requested instruments, source mappings, chart types, maximum acceptable lag and source limitations. Includes USDT, USDC and Open USD market caps.
- `update_settings.json`: overlap, monthly refresh day, per-symbol timeouts, cron hour/minute.
- `ccxt_settings.json`: environment-proxy handling; CCXT supplies its standard Binance API URLs.
- `stablecoin_config.json`: verified asset identities and the default stablecoin-sum selection.

The updater reads its configuration on each run. Reload the app after changing stablecoin selection defaults.

## Sources and limits

| Requested instruments | Route | Limitation |
|---|---|---|
| BTCUSDT, ETHUSDT, SOLUSDT, LINKUSDT, ZECUSDT | Binance spot via CCXT | Downloaded Binance histories are included. Updates use the standard CCXT Binance exchange; no endpoint override or alternate exchange. |
| XMRUSDT | KuCoin spot via CCXT | Configured for daily candles and volume. This environment returned no usable KuCoin market definitions; live download remains unverified. Separate from the old Binance archive. |
| SPY, QQQ, NVDA, SPCX | yfinance | Source listing metadata determines the exchange; no substitute ticker used. |
| BOVA11, DOLA11, PETR4, VALE3, RECV3, BEEF3 | yfinance with B3 suffix | Source OHLC quality checks apply; real closes retained when candle ranges are inconsistent. |
| DXY | Direct yfinance; labelled Fed FX reconstruction if necessary | Reconstruction uses FRED fixing observations, not the official ICE feed. |
| US10Y | FRED | Daily constant-maturity yield in percent; not a bond price or exact TradingView feed. |
| MOVE | yfinance | Must identify ICE bond volatility; unrelated metadata is rejected. |
| CL1!, GC1!, SI1! | yfinance nearby futures | Provider rollover/back-adjustment may differ from TradingView continuous contracts. |
| WREPO | FRED | Weekly ending Wednesday, millions USD. Daily updater checks releases; no fabricated daily observations. |
| USDT, USDC, OUSD market caps | DefiLlama | Daily USD-valued snapshots; OUSD is Open USD with identity verification. |

Only your requested instruments and stablecoin sum appear in the plotting picker. DXY FX inputs remain internal dependencies. Existing unrelated database rows are not offered by the app.

## Stablecoin synthetic

Select the stablecoin sum in the picker. Its default is **USDT + USDC + OUSD (Open USD)**. Toggle its checkboxes to change the selected components. The app sums already stored values; it never downloads data.

Only dates with observations for every selected coin are included. Missing observations are not zero-filled or carried forward. With Open USD selected, the history starts when Open USD observations start. Market cap is a line: daily snapshots do not supply OHLC or trading volume. The default sum is also rebuilt and stored by the updater after stablecoin updates.

## Plotting

Daily view; drag/arrow keys to slide, wheel to zoom. Autocomplete searches local symbols. Pin favourites. Volume is plotted when present. Close-only macro/market-cap series use a line. Price series use candles; an invalid OHLC date is a gap, never a line replacing a price candle. OBS view fits a 9:16 chart area; Esc returns to controls. The plotting server is read-only and has no download endpoint.

## Local data

`history.sqlite3` holds normalized observations; `raw/` keeps source downloads, provider snapshots and source-quality notes. Failed updates do not delete stored history. Source identity and price basis are kept separate. Yahoo prices use `auto_adjust=False` and may still reflect provider split conventions; this is why monthly full refreshes are included.

For inconsistent Yahoo OHLC ranges, only the actual close and available volume are retained for that date. Candle extrema are never invented. Exact issues are written to `raw/*.quality.json`.

Back up this directory. When upgrading an existing installation, replace the code/config as intended but **keep your own `history.sqlite3` and `raw/`** instead of overwriting them with the bundled downloaded histories. Favourites/price levels live in browser local storage.

The source is MIT-licensed. Source data retains its provider's usage terms, including any restrictions on broadcasting. Actual browser/OBS visual verification remains pending; data, HTTP and chart logic are checked separately.

## Alternative sources checked

The Swiss bank is Dukascopy. Its historical-export service is a possible provider for FX/CFD histories, but those are not automatically interchangeable with your requested exchange futures. The current requested price histories were downloaded from Yahoo/Binance, so no Dukascopy CFD is substituted.

Google documents that historical GOOGLEFINANCE data cannot be exported through the Sheets API or Apps Script. It is not used as the cron download backend.

MOVE remains unresolved: Yahoo metadata identifies an unrelated index for its candidate ticker. The identity check rejects it. The public historical MOVE page checked at Investing.com returned HTTP 403 to the downloader. No incorrect replacement is plotted.

CCXT uses its standard exchange ID `binance`; no custom API URL is configured. `trust_environment_proxy` controls whether requests honor host proxy settings. Cached Binance history remains usable if the host cannot reach the standard exchange API.

## Latest available observations

The updater requests through the current source-session date (the provider end argument is exclusive). All symbols use their latest available observation. A new daily/session date appends a row; another download with the same date updates that row, including its close and volume, without duplication. A retrieval timestamp is never treated as a new daily candle. Crypto includes the current daily OHLCV candle with the latest available price as its provisional close. Stablecoin snapshots and published macro observations follow the same date-based rule. Weekly series remain weekly and no missing observation is fabricated.

Re-run `python update.py`, then reload the app to clear its in-memory chart cache. The cron command is unchanged.


### Incremental candle updates
Daily runs read the latest stored observation and every pending provisional date.
One overlapping provider request covers finalization, missing history and the latest
available daily candle. Each returned date updates the existing row or appends a
new date. Empty responses preserve both history and pending states; they are retried
on the next run. No ticker quote is fabricated into an OHLC candle.

SQLite automatically adds a `bar_state` table; existing history is preserved.
US equities and B3 use exchange calendars (holidays and early closes included).
Crypto days close at UTC midnight. Nearby futures and DXY conservatively remain
provisional until the next UTC day and are then refetched; this does not certify
an official exchange settlement price. A job may override its calendar with the
`calendar` field in update_symbols.json. FRED and stablecoin values retain source
observation dates, with publication/fetch time never used to invent daily rows.
Monthly full refresh and explicit --full still revisit historical revisions.

Install the new calendar dependency with `venv/bin/python -m pip install -r requirements.txt`.
Run `venv/bin/python update.py`. Existing cron entries remain valid.
