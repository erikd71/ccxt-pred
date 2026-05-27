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
Fully connected feed-forward neural network (MLP):

| Layer | Size | Notes |
|-------|------|-------|
| Input | 43 | one node per feature |
| Hidden 1 | 30 | |
| Hidden 2 | 10 | |
| Hidden 3 | 5 | |
| Output | 1 | regression, range `(-1, +1)` |

**Activation — Elliott Symmetric** (all hidden layers and output):
```
f(x) = x / (1 + |x|)
```
This is Encog's `ActivationElliotSymmetric`. It maps ℝ → (-1, 1), similar shape to
`tanh` but cheaper to compute. PyTorch has no built-in equivalent; implement as a
custom `nn.Module`. `tanh` is a close substitute if a clean separation from Encog
behaviour is acceptable.

**Dropout**: rate `0.4`, applied after each hidden layer during training.

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

### Training Hyperparameters

**Optimizer — RPROP (Resilient Backpropagation)**
Encog's `ResilientPropagation`. PyTorch equivalent: `torch.optim.Rprop`.

| Encog parameter | Value | PyTorch mapping |
|-----------------|-------|-----------------|
| `RPROP_INITIAL_UPDATE` | `0.001` | `lr=0.001` (initial step size) |
| `RPROP_MAX_STEP` | `0.5` | `step_sizes=(1e-6, 0.5)` |

**Regularization**
- L2 weight decay: `0.001` → `weight_decay=0.001` on the optimizer
- Dropout: `0.4` (see Architecture above)

Batch size and epoch count: TBD (RPROP is a full-batch algorithm in Encog;
batch behaviour in PyTorch's `Rprop` may differ — to be validated during training).

### Labeling Strategy
See `specs/labeling.md`.

---

## Backtest Engine

The backtest simulates the live bot's trading loop on historical candlestick data using
an artificial account. It is the primary quality signal during training — the **best
model is the one with the highest backtest PnL**, not the lowest training/validation loss.

### Data split
- **Training set**: older portion of the candlestick data — used for weight updates only.
- **Validation set**: most recent portion — used for the backtest. The model never trains
  on this data, so the PnL figure is an honest out-of-sample estimate.

### Decision thresholds
| Signal | Condition | Action |
|--------|-----------|--------|
| BUY | model output `>= 0.2` | increase position by **5% of account value** (backtest) / **25%** (live) |
| SELL | model output `<= -0.1` | sell **100%** of the position in that market |
| IDLE | otherwise | do nothing |

A BUY signal accumulates into an existing position — the bot can and often will buy the
same market multiple times before selling. A SELL signal always fully exits the position.

### Simulation rules
| Parameter | Value |
|-----------|-------|
| Starting capital | 100 EUR (artificial) |
| BUY trade size | 5% of current account value per signal |
| Trading fee | 0.25% per trade (Bitvavo taker fee), applied on both buy and sell |
| Trade direction | Long only — buy then sell |

### Reporting
- PnL is expressed as a **percentage return** on the 100 EUR starting capital.
- Backtest is run every `n` epochs during training (configurable).
- The checkpoint with the **highest cumulative PnL** is retained as the best model.

### GUI / output — milestone 1 scope
No interactive GUI for milestone 1. The training script prints per-epoch loss and
flags each new PnL high-water mark to stdout. A simple PnL-vs-epoch log is sufficient
to evaluate training progress. A richer GUI can be added in a later iteration.

---

## Key Open Questions (before milestone 1)
- [x] Labeling strategy — see `specs/labeling.md`
- [x] Network architecture — 43 → [30, 10, 5] → 1, Elliott Symmetric activation, dropout 0.4
- [x] Training hyperparameters — RPROP (`lr=0.001`, max step `0.5`), L2 `0.001`
- [x] Backtest engine — simulation on validation set, 100 EUR account, 0.25% fee, PnL = best-model criterion; BUY ≥ 0.2 (+5% account), SELL ≤ −0.1 (exit 100%)
- [x] GUI scope — out of scope for milestone 1; CLI output only
