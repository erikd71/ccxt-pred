# Copilot Instructions — ccxt-pred

## Project Goal
Reimplement a Java/Encog ML-assisted crypto trading bot in Python.
The primary motivation is moving from Encog (limiting) to PyTorch, and learning
modern Python ML/data tooling (PyTorch, Pandas, etc.) through this project.
The current Java bot is live and profitable — this is a rewrite, not a greenfield design.

**First milestone**: a Python/PyTorch implementation that achieves similar backtest results
to the current Java/Encog bot, following the same core trading logic but using Python best
practices throughout. See `specs/project_overview.md` for the full design reference.

## Style & Approach
- **Spec before code.** For any non-trivial feature, agree on a spec first.
  Keep specs brief and practical — this is a hobby project, not a corporate deliverable.
  Organize specs in the appropriate directory: `specs/` for general project specs,
  `specs/scripts/` for script specs, `specs/src/` for source code specs.
- **No over-engineering.** Prefer simple, readable solutions. Avoid abstractions for one-off tasks.
- **Learn-oriented.** When a Python/PyTorch/Pandas idiom differs from a naive approach,
  briefly mention it so the developer can learn the "right" way.
- **One-man-army.** Don't suggest team processes, CI pipelines, or documentation
  overhead that only makes sense for larger teams.

## Stack
- Python 3.14, managed with `uv` (`uv run <script>` to execute)
- Exchange connectivity: `ccxt` (Bitvavo exchange)
- ML: PyTorch (primary), Pandas for data manipulation
- Config: TOML (`bot.toml` at project root, `account.toml` in workspace)

## Project Layout
```
bot.toml                        # root config (exchange, workspace_path)
scripts/                        # runnable scripts (uv run scripts/<name>.py)
specs/                          # spec documents (hierarchical)
  *.md                          # general project specs
  scripts/                      # script-specific specs
  src/                          # source code module specs
src/ccxt_pred/                  # library code (data, features, models, trading)
tests/
```
Workspace data lives outside the repo at the path set in `bot.toml`:
```
<workspace_path>/bitvavo/
  account.toml                  # api_key, api_secret
  data/candlesticks/<PAIR>/     # <PAIR>_<timeframe>.csv  (e.g. BTC-EUR_30m.csv)
```
See `specs/bot.toml.md` for the full workspace layout and CSV format rules.

## Key Conventions
- Candlestick CSVs: semicolon-separated, no header, LF line endings, ascending timestamp order,
  closed candles only (never write a candle whose period hasn't ended yet).
- Config loading: use `tomllib` (stdlib). Support both flat and `[section]`-table formats.
- Error handling strategy differs by component: one-off scripts (data fetching, training) may
  abort on unexpected errors; the live trading bot must never abort silently — it must recover
  or hold position safely, because an unattended crash while invested is dangerous.
- Secrets (api_key, api_secret) come from `account.toml` — never hard-code or log them.
- **No logic duplication between training and live trading.** Feature engineering, normalization,
  and model inference must live in shared library code (`src/ccxt_pred/`) used by both the
  training pipeline and the live bot. This is the primary guard against train/live inconsistency.
