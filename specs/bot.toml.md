# Spec - bot.toml

## Goal
Define one root config file for bot-level settings, and the workspace directory structure it references.

## Root Config File
- Name: `bot.toml`
- Location: project root
- Format: TOML

### Schema (v1)
```toml
[bot]
workspace_path = "/D/ccxt-pred-workspace"
exchange = "bitvavo"
```

### Rules
1. `[bot]` table is required.
2. `workspace_path` is required and must be a non-empty string.
3. `exchange` is required and must be a non-empty lowercase string.
4. In v1, `exchange` must be `bitvavo`.
5. No other keys under `[bot]` in v1.

## Workspace Directory Structure

The `workspace_path` points to a directory that organizes bot data per exchange.

### Layout (v1)
```
<workspace_path>/
├── <exchange>/
│   ├── account.toml
│   └── data/
│       └── candlesticks/
│           └── <PAIR>/
│               └── <PAIR>_<timeframe>.csv
```

### Example Paths
- Root workspace: `/D/ccxt-pred-workspace`
- Exchange subdir: `/D/ccxt-pred-workspace/bitvavo`
- Account config: `/D/ccxt-pred-workspace/bitvavo/account.toml`
- Candlestick data root: `/D/ccxt-pred-workspace/bitvavo/data/candlesticks`
- Pair directory: `/D/ccxt-pred-workspace/bitvavo/data/candlesticks/BTC-EUR`
- Candlestick file: `/D/ccxt-pred-workspace/bitvavo/data/candlesticks/BTC-EUR/BTC-EUR_30m.csv`

### Directory Purposes
- `<exchange>/account.toml`: Exchange API key/secret and account-specific settings.
- `<exchange>/data/`: Training and runtime data.
- `<exchange>/data/candlesticks/`: OHLCV candlestick files for model training, one subdirectory per market pair.
- `<exchange>/data/candlesticks/<PAIR>/`: All timeframe files for one market pair (e.g. `BTC-EUR`).

## Candlestick File Format

### Naming
- Pattern: `<PAIR>_<timeframe>.csv`
- Example: `BTC-EUR_30m.csv`
- The pair segment uses a hyphen as separator (e.g. `BTC-EUR`).
- The timeframe segment uses the exchange's standard notation (e.g. `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`).

### Structure
- Format: CSV with semicolon (`;`) as field separator.
- No header row.
- One candlestick per line.

### Fields (in order)
| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | `timestamp` | integer | UTC milliseconds since Unix epoch |
| 2 | `open` | decimal | Opening price |
| 3 | `high` | decimal | Highest price |
| 4 | `low` | decimal | Lowest price |
| 5 | `close` | decimal | Closing price |
| 6 | `volume` | decimal | Trade volume |

### Rules
1. Field separator is `;`.
2. Decimal separator is `.` (dot).
3. Line ending is `\n` (LF, Unix format). No `\r\n`.
4. Rows are ordered by `timestamp` ascending (oldest first, newest last).
5. No duplicate timestamps within a file.
6. No header row.

### Example Row
```
1758585600000;4.1112;6.0699;3.8781;4.9371;1900542.37791
```

## Acceptance
1. `bot.toml` exists at project root with schema above.
2. Workspace structure follows layout above.
3. Missing or extra keys in `bot.toml` make config invalid.
4. Each candlestick file follows the naming pattern `<PAIR>_<timeframe>.csv` under `candlesticks/<PAIR>/`.
5. Each candlestick file uses `;` as field separator, `.` as decimal separator, and `\n` line endings.
6. Rows within a file are ordered by timestamp ascending with no duplicates.
