"""
update_candlesticks.py — Fetch OHLCV candlestick data from Bitvavo and write to local .csv files.

For each market in MARKETS the script either:
  - Creates a new .csv file with the complete available history, or
  - Appends only the new closed candles to an existing file.

Run from the project root:
  uv run scripts/update_candlesticks.py
"""

import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

import ccxt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Each entry is either a full pair ("BTC-EUR") or a base asset ("BTC").
# Entries without a quote currency default to EUR.
MARKETS: list[str] = [
    "BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "TRX", "ADA", "HYPE", "LINK",
    "SUI", "AVAX", "XLM", "BCH", "HBAR", "LTC", "CRO", "SHIB", "TON", "DOT",
]

TIMEFRAME: str = "30m"

# Maximum candles per fetch_ohlcv request (Bitvavo limit).
_FETCH_LIMIT: int = 1440

# Earliest timestamp to try when fetching full history (2018-01-01 UTC).
# Bitvavo only retains ~4 years of history; the pagination loop skips ahead
# over any empty windows before the actual start of available data.
_HISTORY_START_MS: int = 1514764800000

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_bot_config(project_root: Path) -> dict:
    with open(project_root / "bot.toml", "rb") as f:
        return tomllib.load(f)


def _load_account_config(workspace_path: str, exchange_id: str) -> dict:
    account_path = Path(workspace_path) / exchange_id / "account.toml"
    with open(account_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("account", data)


# ---------------------------------------------------------------------------
# Market / path helpers
# ---------------------------------------------------------------------------

def _resolve_pair(entry: str) -> str:
    """Return a normalised pair string like 'BTC-EUR'."""
    return entry if "-" in entry else f"{entry}-EUR"


def _ccxt_symbol(pair: str) -> str:
    """Convert 'BTC-EUR' → 'BTC/EUR' for CCXT."""
    return pair.replace("-", "/")


def _csv_path(candlesticks_root: Path, pair: str, timeframe: str) -> Path:
    return candlesticks_root / pair / f"{pair}_{timeframe}.csv"


# ---------------------------------------------------------------------------
# Reading the last timestamp from an existing file
# ---------------------------------------------------------------------------

def _read_last_timestamp(csv_path: Path) -> int:
    """Return the timestamp (ms) of the last candle in the file."""
    with open(csv_path, "rb") as f:
        # Seek backwards to find the last non-empty line efficiently.
        f.seek(0, 2)  # end of file
        size = f.tell()
        if size == 0:
            raise ValueError(f"{csv_path} exists but is empty")
        pos = size - 1
        # Skip trailing newline if present.
        f.seek(pos)
        if f.read(1) == b"\n":
            pos -= 1
        # Walk back to the start of the last line.
        while pos > 0:
            f.seek(pos)
            if f.read(1) == b"\n":
                break
            pos -= 1
        last_line = f.read().decode().strip()
    return int(last_line.split(";")[0])


# ---------------------------------------------------------------------------
# Pagination / fetching
# ---------------------------------------------------------------------------

def _fetch_all_candles(
    exchange: ccxt.Exchange,
    symbol: str,
    timeframe: str,
    since_ms: int,
    timeframe_ms: int,
    now_ms: int,
) -> list[list]:
    """Fetch all closed candles for *symbol* starting at *since_ms*.

    Pages through multiple fetch_ohlcv calls until no more data is returned.
    Filters out any incomplete (open) candles before returning.

    When the exchange returns an empty batch before any data has been found
    (e.g. because the requested `since` pre-dates the exchange's retention
    window), the function skips ahead by one full fetch-window and retries
    rather than giving up immediately.
    """
    all_candles: list[list] = []
    current_since = since_ms
    found_data = False

    while True:
        batch: list[list] = exchange.fetch_ohlcv(
            symbol, timeframe, since=current_since, limit=_FETCH_LIMIT
        )

        if not batch:
            if not found_data:
                # Still searching for the start of available data — skip ahead
                # by one full window and retry.
                current_since += _FETCH_LIMIT * timeframe_ms
                if current_since > now_ms:
                    break  # Nothing available at all
                continue
            # Past the end of available data.
            break

        found_data = True

        # Filter incomplete candles from this batch.
        closed = [c for c in batch if c[0] + timeframe_ms <= now_ms]
        all_candles.extend(closed)

        # Advance past the last candle in the batch (whether closed or not).
        # NOTE: do NOT stop on len(batch) < _FETCH_LIMIT — Bitvavo returns
        # candles within a fixed [since, since + limit*timeframe] window, so
        # the first batch is always partial when data starts mid-window.
        # An empty response is the only reliable end-of-data signal.
        current_since = batch[-1][0] + timeframe_ms

    return all_candles


# ---------------------------------------------------------------------------
# Formatting a single candle as a CSV row
# ---------------------------------------------------------------------------

def _format_row(candle: list) -> str:
    """Return a semicolon-separated row string without a trailing newline."""
    ts, open_, high, low, close, volume = candle
    return f"{int(ts)};{open_};{high};{low};{close};{volume}"


# ---------------------------------------------------------------------------
# Per-market processing
# ---------------------------------------------------------------------------

def _process_market(
    exchange: ccxt.Exchange,
    pair: str,
    timeframe: str,
    timeframe_ms: int,
    candlesticks_root: Path,
    now_ms: int,
) -> None:
    symbol = _ccxt_symbol(pair)
    csv = _csv_path(candlesticks_root, pair, timeframe)

    if not csv.exists():
        # ── Case 1: new file ────────────────────────────────────────────────
        csv.parent.mkdir(parents=True, exist_ok=True)
        candles = _fetch_all_candles(
            exchange, symbol, timeframe, since_ms=_HISTORY_START_MS,
            timeframe_ms=timeframe_ms, now_ms=now_ms,
        )
        if not candles:
            print(f"[{pair}] created  → no closed candles available yet")
            return
        with open(csv, "w", newline="\n", encoding="utf-8") as f:
            f.write("\n".join(_format_row(c) for c in candles) + "\n")
        first_dt = _ms_to_utc_str(candles[0][0])
        last_dt  = _ms_to_utc_str(candles[-1][0])
        print(
            f"[{pair}] created  → {len(candles):,} candles written"
            f"  ({first_dt} → {last_dt} UTC)"
        )
    else:
        # ── Case 2: append ──────────────────────────────────────────────────
        last_ts = _read_last_timestamp(csv)
        since_ms = last_ts + timeframe_ms
        candles = _fetch_all_candles(
            exchange, symbol, timeframe, since_ms=since_ms,
            timeframe_ms=timeframe_ms, now_ms=now_ms,
        )
        if not candles:
            print(f"[{pair}] ok       → already up to date")
            return
        with open(csv, "a", newline="\n", encoding="utf-8") as f:
            f.write("\n".join(_format_row(c) for c in candles) + "\n")
        last_dt = _ms_to_utc_str(candles[-1][0])
        print(
            f"[{pair}] appended → {len(candles):,} candles added"
            f"       (last: {last_dt} UTC)"
        )


def _ms_to_utc_str(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    project_root = Path(__file__).resolve().parent.parent

    try:
        bot_cfg     = _load_bot_config(project_root)["bot"]
        workspace   = bot_cfg["workspace_path"]
        exchange_id = bot_cfg["exchange"]
        account_cfg = _load_account_config(workspace, exchange_id)
    except Exception as exc:
        print(f"ERROR: failed to load configuration — {exc}", file=sys.stderr)
        sys.exit(1)

    candlesticks_root = Path(workspace) / exchange_id / "data" / "candlesticks"

    try:
        exchange: ccxt.Exchange = getattr(ccxt, exchange_id)(
            {
                "apiKey":          account_cfg["api_key"],
                "secret":          account_cfg["api_secret"],
                "enableRateLimit": True,
            }
        )
        timeframe_ms: int = exchange.parse_timeframe(TIMEFRAME) * 1000
    except Exception as exc:
        print(f"ERROR: failed to initialise exchange — {exc}", file=sys.stderr)
        sys.exit(1)

    # Capture now once; reused for every open-candle filter check.
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    print(f"Exchange  : {exchange.name}")
    print(f"Timeframe : {TIMEFRAME}  ({timeframe_ms // 1000}s per candle)")
    print(f"Markets   : {len(MARKETS)}")
    print()

    for entry in MARKETS:
        pair = _resolve_pair(entry)
        try:
            _process_market(
                exchange, pair, TIMEFRAME, timeframe_ms,
                candlesticks_root, now_ms,
            )
        except Exception as exc:
            print(
                f"ERROR: [{pair}] {exc}",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
