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
```

### Example Paths
- Root workspace: `/D/ccxt-pred-workspace`
- Exchange subdir: `/D/ccxt-pred-workspace/bitvavo`
- Account config: `/D/ccxt-pred-workspace/bitvavo/account.toml`
- Candlestick data root: `/D/ccxt-pred-workspace/bitvavo/data/candlesticks`

### Directory Purposes
- `<exchange>/account.toml`: Exchange API key/secret and account-specific settings.
- `<exchange>/data/`: Training and runtime data.
- `<exchange>/data/candlesticks/`: OHLCV candlestick files for model training.

## Acceptance
1. `bot.toml` exists at project root with schema above.
2. Workspace structure follows layout above.
3. Missing or extra keys in `bot.toml` make config invalid.
