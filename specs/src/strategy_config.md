# Spec - Strategy Config (Train/Live Shared)

## Goal
Define one strategy configuration object used by both training and live trading,
serialized as JSON.

The file has two responsibilities:
1. Runtime parity: same feature/label/trading behavior in train, backtest, and live modes.
2. Experiment provenance: preserve how a promoted model was designed and trained.

This is the Python equivalent of Java `StrategyConfig3`, expanded to include model and
training settings in one artifact.

---

## File and Lifecycle

- Produced by: training workflow (when a model is promoted)
- Consumed by: live bot and backtest runner
- Format: JSON
- Suggested location: alongside model weights in model artifact directory

A promoted model artifact includes:
1. model weights
2. strategy config JSON (this spec)

Both are versioned together.

---

## Schema (v1)

```json
{
  "schema_version": 1,
  "metadata": {
    "created_utc": "2026-05-29T12:00:00Z",
    "git_commit": "ef57584",
    "dataset": {
      "exchange": "bitvavo",
      "timeframe": "30m",
      "symbols": ["BTC-EUR", "ETH-EUR"],
      "from_utc": "2019-03-08T10:30:00Z",
      "to_utc": "2026-05-25T16:30:00Z"
    },
    "notes": "optional free-form comment"
  },
  "general": {
    "timeframe": "30m",
    "symbols": ["BTC-EUR", "ETH-EUR"],
    "history_candles": 1400
  },
  "labeling": {
    "window_size": 6,
    "min_profit": 1.02,
    "max_loss": 0.997,
    "sell_max_profit": 1.0,
    "sell_min_loss": 1.0
  },
  "model": {
    "hidden_layers": [30, 10, 5],
    "activation": "elliot_symmetric",
    "dropout_rate": 0.4,
    "output_dim": 1
  },
  "hyper_parameters": {
    "train_validation_split": 0.7,
    "optimizer": {
      "name": "rprop",
      "rprop_initial_update": 0.001,
      "rprop_max_step": 0.5
    },
    "regularization": {
      "l2": 0.001
    }
  },
  "input_features": {
    "recent_candles": {
      "count": 5,
      "fields": ["open", "high", "low"]
    },
    "indicators": {
      "mins": [5, 13, 34, 89, 360, 1400],
      "maxs": [5, 13, 34, 89, 360, 1400],
      "stls": [13, 34, 89, 360, 1400],
      "vwaps": [5, 13, 34, 89],
      "emas": [5, 13, 34, 89],
      "atrs": [5, 13, 34]
    }
  },
  "trading": {
    "buy_threshold": 0.2,
    "sell_threshold": -0.1,
    "position_add_fraction_backtest": 0.05,
    "position_add_fraction_live": 0.25,
    "sell_all_on_signal": true,
    "fee_rate": 0.0025
  }
}
```

---

## Group Semantics

### `schema_version`
- Integer schema version for forward compatibility.
- v1 value is exactly `1`.

### `metadata`
Training/provenance metadata. Useful for auditability and reproducibility.

- `created_utc`: RFC3339 UTC timestamp when artifact was produced.
- `git_commit`: source commit used for training/promotion.
- `dataset`: summary of training/backtest source range.
  - `exchange`
  - `timeframe`
  - `symbols`
  - `from_utc`
  - `to_utc`
- `notes`: optional free-form training notes.

Live runtime does not require this to trade, but it is part of the artifact contract.

### `general`
Core dataset and market scope.

- `timeframe`: candle timeframe string (current parity: `"30m"`)
- `symbols`: market list in `BASE-QUOTE` format
- `history_candles`: number of candles required to compute full feature set

### `labeling`
Label generator settings from `specs/labeling.md`.

- `window_size`
- `min_profit`
- `max_loss`
- `sell_max_profit`
- `sell_min_loss`

### `model`
Neural-network structure settings.

- `hidden_layers`: e.g. `[30, 10, 5]`
- `activation`: v1 allowed: `"elliot_symmetric"`
- `dropout_rate`: e.g. `0.4`
- `output_dim`: v1 fixed `1`

### `hyper_parameters`
Training-process settings.

- `train_validation_split`: e.g. `0.7`
- `optimizer`
  - `name`: v1 allowed: `"rprop"`
  - `rprop_initial_update`: e.g. `0.001`
  - `rprop_max_step`: e.g. `0.5`
- `regularization`
  - `l2`: e.g. `0.001`

### `input_features`
Feature-engineering settings.

- `recent_candles`
  - `count`: number of recent completed candles
  - `fields`: ordered subset of `open|high|low|close`
- `indicators`
  - `mins`
  - `maxs`
  - `stls`
  - `vwaps`
  - `emas`
  - `atrs`

### `trading`
Signal-to-order behavior for backtest/live.

- `buy_threshold`: BUY when model output >= value
- `sell_threshold`: SELL when model output <= value
- `position_add_fraction_backtest`: account fraction added per BUY in backtest
- `position_add_fraction_live`: account fraction added per BUY in live
- `sell_all_on_signal`: if true, SELL exits full market position
- `fee_rate`: per-trade fee (Bitvavo 0.25% -> `0.0025`)

---

## Required Defaults (Current Java Parity)

- `general.timeframe = "30m"`
- `general.history_candles = 1400`
- `labeling = {window_size: 6, min_profit: 1.02, max_loss: 0.997, sell_max_profit: 1.0, sell_min_loss: 1.0}`
- `model.hidden_layers = [30, 10, 5]`
- `model.activation = "elliot_symmetric"`
- `model.dropout_rate = 0.4`
- `model.output_dim = 1`
- `hyper_parameters.train_validation_split = 0.7`
- `hyper_parameters.optimizer = {name: "rprop", rprop_initial_update: 0.001, rprop_max_step: 0.5}`
- `hyper_parameters.regularization.l2 = 0.001`
- `input_features.recent_candles = {count: 5, fields: ["open", "high", "low"]}`
- `input_features.indicators.mins = [5, 13, 34, 89, 360, 1400]`
- `input_features.indicators.maxs = [5, 13, 34, 89, 360, 1400]`
- `input_features.indicators.stls = [13, 34, 89, 360, 1400]`
- `input_features.indicators.vwaps = [5, 13, 34, 89]`
- `input_features.indicators.emas = [5, 13, 34, 89]`
- `input_features.indicators.atrs = [5, 13, 34]`
- `trading.buy_threshold = 0.2`
- `trading.sell_threshold = -0.1`
- `trading.position_add_fraction_backtest = 0.05`
- `trading.position_add_fraction_live = 0.25`
- `trading.sell_all_on_signal = true`
- `trading.fee_rate = 0.0025`

---

## Validation Rules (v1)

1. `schema_version` must equal `1`.
2. `general.timeframe` must be non-empty and supported by exchange/data pipeline.
3. `general.symbols` must be a non-empty array of uppercase `BASE-QUOTE` strings.
4. `general.history_candles` must be integer >= 1.
5. `general.history_candles` must be >= max(all indicator windows).
6. `labeling.window_size` must be integer >= 1.
7. `model.hidden_layers` must be non-empty array of positive integers.
8. `model.activation` allowed values (v1): `elliot_symmetric`.
9. `model.dropout_rate` must be in [0, 1).
10. `model.output_dim` must equal `1`.
11. `hyper_parameters.train_validation_split` must be in (0, 1).
12. `hyper_parameters.optimizer.name` allowed values (v1): `rprop`.
13. `rprop_initial_update` and `rprop_max_step` must be > 0.
14. `hyper_parameters.regularization.l2` must be >= 0.
15. `input_features.recent_candles.count` must be integer >= 1.
16. `input_features.recent_candles.fields` must be non-empty; allowed: `open|high|low|close`.
17. All indicator window arrays must contain positive integers.
18. `trading.buy_threshold` and `trading.sell_threshold` must be in [-1, 1].
19. `trading.sell_threshold < trading.buy_threshold`.
20. `position_add_fraction_backtest` and `position_add_fraction_live` must be in (0, 1].
21. `fee_rate` must be in [0, 1).
22. `metadata.created_utc`, `metadata.dataset.from_utc`, `metadata.dataset.to_utc` must be valid RFC3339 UTC timestamps when present.

Validation failure is a hard error for training and live startup.

---

## Train/Live Consistency Contract

These groups must be identical between training and live runtime:

- `general.timeframe`
- `input_features`
- `model` (input expectations and activation behavior)
- normalization behavior (defined in code/specs)
- `trading` thresholds and order-sizing rules

A live bot must refuse to start if model metadata and config are incompatible.

---

## Python Shape (Suggested)

Implement as typed dataclasses or Pydantic models under `src/ccxt_pred/`:

- `StrategyConfig`
- `MetadataConfig`
- `GeneralConfig`
- `LabelingConfig`
- `ModelConfig`
- `HyperParametersConfig`
- `InputFeaturesConfig`
- `TradingConfig`

Provide:
- `from_json(path) -> StrategyConfig` (with validation)
- `to_json(path)`
- deterministic output field ordering for stable diffs

---

## Acceptance

1. A single v1 JSON file can represent current Java strategy, model, and training settings.
2. The training pipeline uses `general`, `labeling`, `model`, `hyper_parameters`, and `input_features` from this config.
3. The live bot uses `general`, `input_features`, `model`, and `trading` from the same file.
4. `metadata` is written at promotion time and preserved with model artifacts.
5. Invalid configs fail fast with clear error messages.
6. Promoting a model stores weights + strategy config together.
