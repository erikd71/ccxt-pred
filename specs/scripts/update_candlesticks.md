# Spec - update_candlesticks.py

## Goal
Fetch OHLCV candlestick data from the configured exchange and write it to local `.csv` files
following the format defined in `bot.toml.md`. Each run either creates a new file with the
complete available history, or appends only the new closed candles to an existing file.

## Location
`scripts/update_candlesticks.py`

## Configuration

### Constants (defined at the top of the script)

#### `MARKETS`
A list of market symbols to update. Each entry is either a full pair (`BTC-EUR`) or a base
asset only (`BTC`). If no quote currency is given, `EUR` is assumed.

Default list:
```
BTC, ETH, XRP, BNB, SOL, DOGE, TRX, ADA, HYPE, LINK,
SUI, AVAX, XLM, BCH, HBAR, LTC, CRO, SHIB, TON, DOT
```
All resolve to `<base>-EUR` (e.g. `BTC` → `BTC-EUR`).

#### `TIMEFRAME`
The candlestick interval to fetch, using the exchange's standard notation.

Default: `"30m"`

### Runtime Configuration
The script reads `bot.toml` (project root) and the exchange's `account.toml` using the same
paths defined in `bot.toml.md`. No command-line arguments are required.

## Algorithm

### Overview
```
for each market in MARKETS:
    resolve full pair (add -EUR if needed)
    determine target .csv file path
    if file does not exist:
        fetch full history → write new file
    else:
        read last timestamp from file
        fetch candles after last timestamp → append to file
```

### Resolving the Market Pair
- If the entry contains `-`, use it as-is (e.g. `BTC-EUR`).
- Otherwise, append `-EUR` (e.g. `BTC` → `BTC-EUR`).
- The CCXT symbol is the pair with `/` instead of `-` (e.g. `BTC/EUR`).

### Target File Path
Derived from `bot.toml` as specified in `bot.toml.md`:
```
<workspace_path>/<exchange>/data/candlesticks/<PAIR>/<PAIR>_<TIMEFRAME>.csv
```
Example: `/D/ccxt-pred-workspace/bitvavo/data/candlesticks/BTC-EUR/BTC-EUR_30m.csv`

---

### Case 1: File Does Not Exist

1. Create the pair directory if it does not already exist.
2. Fetch the complete available history using paginated requests (see **Pagination** below),
   starting from the earliest timestamp the exchange provides.
3. Filter out any incomplete (open) candles (see **Open Candle Filtering** below).
4. Write all remaining candles to the new `.csv` file, ordered ascending by timestamp.

### Case 2: File Already Exists

1. Read the last line of the existing `.csv` file and parse its timestamp (`field[0]`).
2. Fetch candles with `since = last_timestamp + timeframe_duration_ms` using paginated
   requests (see **Pagination** below).
3. Filter out any incomplete (open) candles (see **Open Candle Filtering** below).
4. Append the remaining candles to the existing file in ascending timestamp order.
5. If no new closed candles are available, do nothing (log that the file is already up to date).

---

## Pagination

Bitvavo returns at most 1440 candles per `fetch_ohlcv` request. The script must page through
multiple requests to retrieve a full history or a large update.

### Strategy
1. Set `since` to the desired start timestamp (`_HISTORY_START_MS` for full history, or
   `last_timestamp + timeframe_ms` for an append).
2. Call `exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1440)`.
3. If the response is empty, stop — no more data is available.
4. Record the last candle's timestamp from the response.
5. Set `since = last_candle_timestamp + timeframe_duration_ms` and repeat from step 2.

**Important**: do NOT stop when the response contains fewer candles than `limit`. Bitvavo
returns candles within a fixed `[since, since + limit*timeframe]` window. The first batch
is always partial when historical data starts mid-window. An **empty response** is the only
reliable end-of-data signal.

### Finding the Start of Available Data
Bitvavo only retains approximately 4–5 years of history. Requests with a `since` timestamp
that pre-dates the retention window return an empty response. To handle this, the full-history
fetch starts from `_HISTORY_START_MS` (2018-01-01 UTC) and skips ahead by one full fetch-
window (`_FETCH_LIMIT * timeframe_ms`) for each empty response, until data is found or
`since` exceeds the current time.

### Timeframe Duration
The duration in milliseconds for a given timeframe string must be computed before pagination
starts, using CCXT's `exchange.parse_timeframe(timeframe) * 1000`.

---

## Open Candle Filtering

A candle with timestamp `t` covers the interval `[t, t + timeframe_duration_ms)`. It is
**closed** only when that interval has fully elapsed, i.e.:

```
t + timeframe_duration_ms <= now_utc_ms
```

Any candle where `t + timeframe_duration_ms > now_utc_ms` is **incomplete** and must be
**discarded**. This check is applied to every batch of candles returned by the exchange
before they are written or appended to the file.

`now_utc_ms` is captured once at the start of the script run and reused throughout.

---

## Rate Limiting

CCXT's built-in rate limiter is enabled (`enableRateLimit=True`). No custom counter is
implemented. CCXT will automatically insert delays between requests to stay within the
exchange's published limits.

---

## Error Handling

- Any error (network failure, API error, invalid market, file I/O error) causes the script
  to **abort immediately** with a clear error message printed to `stderr`.
- No partial results are silently swallowed.
- The error message must include: the market being processed at the time of failure, the
  nature of the error, and enough context to diagnose the problem.

---

## Output

### Console (stdout)
The script prints one status line per market after processing it:

```
[BTC-EUR] created  → 34560 candles written  (2026-01-01 00:00 → 2026-05-25 10:00 UTC)
[ETH-EUR] appended → 48 candles added       (last: 2026-05-25 10:30 UTC)
[XRP-EUR] ok       → already up to date
```

### File
Candlestick files follow the format defined in `bot.toml.md` exactly:
- Semicolon-separated fields, no header row.
- Dot as decimal separator.
- LF (`\n`) line endings.
- Rows ordered ascending by timestamp, no duplicates.

---

## Acceptance

1. Running the script with empty `candlesticks/` creates one `.csv` per market with the full
   available history, containing only closed candles.
2. Running the script again immediately after makes no changes to any file (all up to date).
3. Running the script after time has passed appends only the new closed candles.
4. The most recent candle in any file always has `timestamp + timeframe_duration_ms <= time_of_run`.
5. No candle timestamp appears more than once in a file.
6. All files conform to the format rules in `bot.toml.md`.
7. Any API or I/O error causes the script to abort with a descriptive message; no file is
   left in a corrupt state.
