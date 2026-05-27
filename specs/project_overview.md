# Spec - Project Overview

## First Milestone
Produce a Python/PyTorch trading bot that achieves **similar backtest results** to the
current Java/Encog bot. The goal is a clean reimplementation following Python best
practices — not a line-for-line translation. Once milestone 1 is reached, the Python bot
can be iterated on independently.

---

## End-to-End Workflow

1. **Update candlestick data** — run `scripts/update_candlesticks.py` to pull the latest
   OHLCV data from Bitvavo into local CSV files. *(Done)*

2. **Run the training program** — a script (with optional GUI) that:
   - Loads local candlestick data
   - Labels the data (BUY / SELL / IDLE targets)
   - Splits data into training set (older) and validation set (most recent)
   - Trains the neural network, logging training error and validation error per epoch
   - Periodically runs a backtest and reports PnL on the validation set
   - Exposes controls to: run a manual backtest with the current best model,
     adjust decision thresholds, and "promote" a model to production

3. **Promote a model** — copy the trained weights + config to the `models/` directory
   so the live bot picks them up on next restart.

4. **Commit and push** — version-control the promoted model config.

5. **Deploy** — on the live machine, pull the repo and restart the bot.

---

## Core Design Principles

- **No duplication between training and live.** Feature engineering, normalization, and
  model inference are implemented once in `src/ccxt_pred/` and used identically in both
  the training pipeline and the live trading bot. This is the primary correctness guarantee.
- **Long-only trading.** No short positions, no leverage, no margin. Simple buy/hold/sell.
- **Decision at each candle close.** The bot acts once per timeframe: fetch the latest
  closed candle, compute features, run inference, apply thresholds, execute trade if warranted.
- **Configurable, not hard-coded.** Market list, timeframe, model hyperparameters, and
  decision thresholds are all stored in config files, not baked into code.

---

## ML Model

### Architecture
- Fully connected feed-forward neural network (MLP).
- Single regression output in the range `[-1, +1]`.
- Activation and depth: TBD in model spec.

### Output Semantics
| Value | Meaning |
|-------|---------|
| close to `+1` | Strong BUY signal |
| near `0` | IDLE — do nothing |
| close to `-1` | Strong SELL signal |

The model never reaches the extremes in practice; trading decisions are made by applying
configurable thresholds (e.g. output > 0.3 → consider buying).

### Input Features
All features are normalized to approximately `[-1, +1]` relative to the most recent
closing price (see **Normalization** below). The feature vector is built from:

1. **Raw candles** — the `n` most recent closed candles (currently `n = 5`).
   Fields per candle: open, high, low, close, volume.

2. **TA indicators** (multiple timeframes):
   - VWAP — Volume-Weighted Average Price
   - EMA — Exponential Moving Average
   - ATR — Average True Range

3. **Custom indicators** (multiple timeframes):
   - `MIN(k)` — lowest price seen in the last `k` candles
   - `MAX(k)` — highest price seen in the last `k` candles
   - `STL(k)` — closing price `k` candles ago ("Simple Trend Line")

### Normalization
Price-based features are mapped to `[-1, +1]` relative to the most recent close price `p`:

```
normalized = 2 * (value / p) / (1 + value / p) - 1
```

Concretely: `0` means the value equals `p`; approaching `+1` means value → ∞;
approaching `-1` means value → 0. Volume features: normalization TBD.

### Labeling Strategy
Details to be defined in `specs/labeling.md`. The label assigned to each historical
candle determines what the model is trained to output at that point in time. Getting
the labeling strategy right is critical — it defines what "a good trade" means to the model.

---

## Key Open Questions (before milestone 1)
- [ ] Labeling strategy — how is each historical candle labeled BUY / SELL / IDLE?
- [ ] Exact network architecture (layers, activations, dropout)
- [ ] Training hyperparameters (learning rate, batch size, optimizer)
- [ ] Backtest engine design (PnL calculation, fees, slippage assumptions)
- [ ] GUI scope — full interactive trainer, or minimal CLI output for milestone 1?
