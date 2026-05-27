# Spec - Candle Labeling (BUY / SELL / IDLE)

## Purpose
Assign a training label to each historical candle. The label represents what the model
should have predicted at that point in time, based on what actually happened next.
This is the ground truth used to train the regression output described in
`specs/project_overview.md`.

---

## Algorithm

For each candle at index `i`, look at the **closing prices** of the next `window_size`
candles (indices `i+1` through `i+window_size` inclusive) and compute:

```
max_close = max(close[i+1 .. i+window_size])
min_close = min(close[i+1 .. i+window_size])
ref       = close[i]   # the current candle's closing price
```

Then assign:

```
if max_close >= ref * min_profit  AND  min_close >= ref * max_loss:
    label = BUY  (+1)

elif max_close <= ref * sell_max_profit  AND  min_close <= ref * sell_min_loss:
    label = SELL  (-1)

else:
    label = IDLE  (0)
```

The last `window_size` candles of the dataset cannot be labeled (no look-ahead available)
and are excluded from training.

---

## Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `window_size` | int | Number of future candles to look ahead |
| `min_profit` | float | BUY: price must reach **at least** this ratio at some point in the window |
| `max_loss` | float | BUY: price must **never** fall below this ratio anywhere in the window |
| `sell_max_profit` | float | SELL: price must **never** rise above this ratio in the window |
| `sell_min_loss` | float | SELL: price must fall **at least** to this ratio at some point in the window |

All ratios are relative to `close[i]` (e.g. `1.02` means 2% above current close,
`0.997` means 0.3% below).

### Symmetry shortcut
When only `min_profit` and `max_loss` are supplied, the SELL parameters are derived
symmetrically:

```
sell_max_profit = 2.0 - min_profit   # e.g. 1.02 → 0.98
sell_min_loss   = 2.0 - max_loss     # e.g. 0.997 → 1.003
```

---

## Current Default Settings

```toml
window_size      = 6
min_profit       = 1.02    # price must reach +2% somewhere in the window
max_loss         = 0.997   # price must never drop more than -0.3%
sell_max_profit  = 1.0     # price never exceeds current close
sell_min_loss    = 1.0     # price falls below current close at least once
```

### BUY interpretation
Within the next 6 candles: the price must reach at least +2% AND must never drop more
than -0.3%. This is intentionally a "sniper" setup — labels only high-confidence
entry opportunities where the upside is clear and the downside is tightly bounded.

### SELL interpretation
With `sell_max_profit = sell_min_loss = 1.0`: all future closes in the window are
at or below the current close. The market is going sideways or down — a good moment
to exit a long position.

### IDLE interpretation
Everything else: the risk/reward profile doesn't meet the BUY criteria, and the price
isn't clearly declining either.

---

## Label Distribution
Expect a heavily imbalanced dataset: BUY and SELL labels are intentionally rare (the
"sniper" thresholds filter aggressively). Most candles will be IDLE. The training
pipeline must account for this (e.g. via loss weighting or oversampling). Details TBD
in the training spec.

---

## Notes
- Labels are based solely on **closing prices**, not intra-candle highs/lows.
- The labeler is a pure data-transformation step with no model dependency.
- It must live in shared library code (`src/ccxt_pred/`) so training and any future
  simulation use identical logic.
- Settings should be loaded from the model config file, not hard-coded.
