"""Strategy configuration dataclasses and validation.

This module provides StrategyConfig, a unified JSON-serializable configuration object
used identically by training, backtesting, and live trading. It serves as:
1. Runtime parity contract: same settings across all modes
2. Experiment provenance: captures how a model was trained and promoted
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List


class ConfigError(Exception):
    """Configuration validation error."""
    pass


def _validate_rfc3339_timestamp(ts_str: str) -> None:
    """Validate RFC3339 UTC timestamp format.
    
    Args:
        ts_str: timestamp string to validate
        
    Raises:
        ConfigError: if format is invalid
    """
    try:
        # Parse RFC3339 format: 2026-05-29T12:00:00Z
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        if dt.tzinfo is None or dt.tzinfo.utcoffset(None).total_seconds() != 0:
            raise ConfigError(f"Timestamp must be UTC: {ts_str}")
    except (ValueError, AttributeError) as e:
        raise ConfigError(f"Invalid RFC3339 timestamp: {ts_str}") from e


@dataclass
class DatasetMetadata:
    """Dataset range for training/backtest source data."""
    exchange: str
    timeframe: str
    symbols: List[str]
    from_utc: str
    to_utc: str
    
    def validate(self) -> None:
        """Validate dataset metadata."""
        if not self.exchange:
            raise ConfigError("dataset.exchange must be non-empty")
        if not self.timeframe:
            raise ConfigError("dataset.timeframe must be non-empty")
        if not self.symbols or not all(self.symbols):
            raise ConfigError("dataset.symbols must be a non-empty array of non-empty strings")
        _validate_rfc3339_timestamp(self.from_utc)
        _validate_rfc3339_timestamp(self.to_utc)


@dataclass
class Metadata:
    """Training/provenance metadata."""
    created_utc: str
    git_commit: str
    dataset: DatasetMetadata
    notes: Optional[str] = None
    
    def validate(self) -> None:
        """Validate metadata."""
        _validate_rfc3339_timestamp(self.created_utc)
        if not self.git_commit:
            raise ConfigError("metadata.git_commit must be non-empty")
        self.dataset.validate()


@dataclass
class GeneralConfig:
    """Core dataset and market scope settings."""
    timeframe: str = "30m"
    symbols: List[str] = field(default_factory=list)
    history_candles: int = 1400
    
    def validate(self) -> None:
        """Validate general configuration."""
        if not self.timeframe:
            raise ConfigError("general.timeframe must be non-empty and supported")
        if not self.symbols or not all(self.symbols):
            raise ConfigError("general.symbols must be a non-empty array of uppercase BASE-QUOTE strings")
        # Validate BASE-QUOTE format (basic check)
        for symbol in self.symbols:
            if not symbol or '-' not in symbol:
                raise ConfigError(f"general.symbols must be in BASE-QUOTE format: {symbol}")
        if self.history_candles < 1:
            raise ConfigError("general.history_candles must be >= 1")


@dataclass
class LabelingConfig:
    """Label generation settings."""
    window_size: int = 6
    min_profit: float = 1.02
    max_loss: float = 0.997
    sell_max_profit: float = 1.0
    sell_min_loss: float = 1.0
    
    def validate(self) -> None:
        """Validate labeling configuration."""
        if self.window_size < 1:
            raise ConfigError("labeling.window_size must be >= 1")


@dataclass
class ModelConfig:
    """Neural network structure settings."""
    hidden_layers: List[int] = field(default_factory=lambda: [30, 10, 5])
    activation: str = "elliot_symmetric"
    dropout_rate: float = 0.4
    output_dim: int = 1
    
    def validate(self) -> None:
        """Validate model configuration."""
        if not self.hidden_layers or not all(x > 0 for x in self.hidden_layers):
            raise ConfigError("model.hidden_layers must be non-empty array of positive integers")
        if self.activation != "elliot_symmetric":
            raise ConfigError(f"model.activation allowed values (v1): elliot_symmetric, got {self.activation}")
        if not (0 <= self.dropout_rate < 1):
            raise ConfigError("model.dropout_rate must be in [0, 1)")
        if self.output_dim != 1:
            raise ConfigError("model.output_dim must equal 1")


@dataclass
class OptimizerConfig:
    """Optimizer settings."""
    name: str = "rprop"
    rprop_initial_update: float = 0.001
    rprop_max_step: float = 0.5
    
    def validate(self) -> None:
        """Validate optimizer configuration."""
        if self.name != "rprop":
            raise ConfigError(f"hyper_parameters.optimizer.name allowed values (v1): rprop, got {self.name}")
        if self.rprop_initial_update <= 0:
            raise ConfigError("hyper_parameters.optimizer.rprop_initial_update must be > 0")
        if self.rprop_max_step <= 0:
            raise ConfigError("hyper_parameters.optimizer.rprop_max_step must be > 0")


@dataclass
class RegularizationConfig:
    """Regularization settings."""
    l2: float = 0.001
    
    def validate(self) -> None:
        """Validate regularization configuration."""
        if self.l2 < 0:
            raise ConfigError("hyper_parameters.regularization.l2 must be >= 0")


@dataclass
class HyperParametersConfig:
    """Training process settings."""
    train_validation_split: float = 0.7
    optimizer: OptimizerConfig = field(default_factory=OptimizerConfig)
    regularization: RegularizationConfig = field(default_factory=RegularizationConfig)
    
    def validate(self) -> None:
        """Validate hyper parameters configuration."""
        if not (0 < self.train_validation_split < 1):
            raise ConfigError("hyper_parameters.train_validation_split must be in (0, 1)")
        self.optimizer.validate()
        self.regularization.validate()


@dataclass
class RecentCandlesConfig:
    """Recent candles feature settings."""
    count: int = 5
    fields: List[str] = field(default_factory=lambda: ["open", "high", "low"])
    
    def validate(self) -> None:
        """Validate recent candles configuration."""
        if self.count < 1:
            raise ConfigError("input_features.recent_candles.count must be >= 1")
        if not self.fields:
            raise ConfigError("input_features.recent_candles.fields must be non-empty")
        allowed_fields = {"open", "high", "low", "close"}
        for field_name in self.fields:
            if field_name not in allowed_fields:
                raise ConfigError(f"input_features.recent_candles.fields must be subset of {allowed_fields}, got {field_name}")


@dataclass
class IndicatorsConfig:
    """Technical indicator settings."""
    mins: List[int] = field(default_factory=lambda: [5, 13, 34, 89, 360, 1400])
    maxs: List[int] = field(default_factory=lambda: [5, 13, 34, 89, 360, 1400])
    stls: List[int] = field(default_factory=lambda: [13, 34, 89, 360, 1400])
    vwaps: List[int] = field(default_factory=lambda: [5, 13, 34, 89])
    emas: List[int] = field(default_factory=lambda: [5, 13, 34, 89])
    atrs: List[int] = field(default_factory=lambda: [5, 13, 34])
    
    def validate(self) -> None:
        """Validate indicators configuration."""
        for indicator_name, windows in [
            ("mins", self.mins),
            ("maxs", self.maxs),
            ("stls", self.stls),
            ("vwaps", self.vwaps),
            ("emas", self.emas),
            ("atrs", self.atrs),
        ]:
            if not all(isinstance(w, int) and w > 0 for w in windows):
                raise ConfigError(f"input_features.indicators.{indicator_name} must contain positive integers")
    
    def max_window(self) -> int:
        """Get maximum indicator window size."""
        all_windows = self.mins + self.maxs + self.stls + self.vwaps + self.emas + self.atrs
        return max(all_windows) if all_windows else 0


@dataclass
class InputFeaturesConfig:
    """Feature engineering settings."""
    recent_candles: RecentCandlesConfig = field(default_factory=RecentCandlesConfig)
    indicators: IndicatorsConfig = field(default_factory=IndicatorsConfig)
    
    def validate(self) -> None:
        """Validate input features configuration."""
        self.recent_candles.validate()
        self.indicators.validate()


@dataclass
class TradingConfig:
    """Trading signal-to-order behavior settings."""
    buy_threshold: float = 0.2
    sell_threshold: float = -0.1
    position_add_fraction_backtest: float = 0.05
    position_add_fraction_live: float = 0.25
    sell_all_on_signal: bool = True
    fee_rate: float = 0.0025
    
    def validate(self) -> None:
        """Validate trading configuration."""
        if not (-1 <= self.buy_threshold <= 1):
            raise ConfigError("trading.buy_threshold must be in [-1, 1]")
        if not (-1 <= self.sell_threshold <= 1):
            raise ConfigError("trading.sell_threshold must be in [-1, 1]")
        if self.sell_threshold >= self.buy_threshold:
            raise ConfigError("trading.sell_threshold must be < trading.buy_threshold")
        if not (0 < self.position_add_fraction_backtest <= 1):
            raise ConfigError("trading.position_add_fraction_backtest must be in (0, 1]")
        if not (0 < self.position_add_fraction_live <= 1):
            raise ConfigError("trading.position_add_fraction_live must be in (0, 1]")
        if not (0 <= self.fee_rate < 1):
            raise ConfigError("trading.fee_rate must be in [0, 1)")


@dataclass
class StrategyConfig:
    """Complete strategy configuration for training, backtest, and live trading.
    
    This is the unified configuration object that ensures parity across all modes.
    It includes model architecture, training hyperparameters, feature engineering settings,
    and trading decision thresholds, along with provenance metadata.
    
    Attributes:
        schema_version: Configuration schema version (must be 1)
        metadata: Training/provenance information
        general: Core dataset and market scope
        labeling: Label generation settings
        model: Neural network structure
        hyper_parameters: Training process settings
        input_features: Feature engineering settings
        trading: Trading signal behavior
    """
    schema_version: int = 1
    metadata: Optional[Metadata] = None
    general: GeneralConfig = field(default_factory=GeneralConfig)
    labeling: LabelingConfig = field(default_factory=LabelingConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    hyper_parameters: HyperParametersConfig = field(default_factory=HyperParametersConfig)
    input_features: InputFeaturesConfig = field(default_factory=InputFeaturesConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    
    def validate(self) -> None:
        """Validate the complete strategy configuration.
        
        Raises:
            ConfigError: if any validation rule fails
        """
        # Rule 1
        if self.schema_version != 1:
            raise ConfigError(f"schema_version must equal 1, got {self.schema_version}")
        
        # Validate nested configs
        self.general.validate()
        self.labeling.validate()
        self.model.validate()
        self.hyper_parameters.validate()
        self.input_features.validate()
        self.trading.validate()
        
        if self.metadata:
            self.metadata.validate()
        
        # Rule 5: history_candles >= max(all indicator windows)
        max_indicator_window = self.input_features.indicators.max_window()
        if self.general.history_candles < max_indicator_window:
            raise ConfigError(
                f"general.history_candles ({self.general.history_candles}) must be >= "
                f"max indicator window ({max_indicator_window})"
            )
    
    @classmethod
    def from_json(cls, path: Path) -> "StrategyConfig":
        """Load and validate strategy config from JSON file.
        
        Args:
            path: Path to JSON configuration file
            
        Returns:
            Validated StrategyConfig instance
            
        Raises:
            ConfigError: if JSON is invalid or validation fails
            FileNotFoundError: if file does not exist
        """
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Strategy config not found: {path}")
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in {path}: {e}")
        
        try:
            # Deserialize nested structures
            if "metadata" in data and data["metadata"]:
                metadata_data = data["metadata"]
                dataset_data = metadata_data.get("dataset", {})
                dataset = DatasetMetadata(**dataset_data)
                metadata = Metadata(
                    created_utc=metadata_data["created_utc"],
                    git_commit=metadata_data["git_commit"],
                    dataset=dataset,
                    notes=metadata_data.get("notes")
                )
            else:
                metadata = None
            
            general = GeneralConfig(**data.get("general", {}))
            labeling = LabelingConfig(**data.get("labeling", {}))
            model = ModelConfig(**data.get("model", {}))
            
            hyper_params_data = data.get("hyper_parameters", {})
            optimizer = OptimizerConfig(**hyper_params_data.get("optimizer", {}))
            regularization = RegularizationConfig(**hyper_params_data.get("regularization", {}))
            hyper_parameters = HyperParametersConfig(
                train_validation_split=hyper_params_data.get("train_validation_split", 0.7),
                optimizer=optimizer,
                regularization=regularization
            )
            
            input_features_data = data.get("input_features", {})
            recent_candles = RecentCandlesConfig(**input_features_data.get("recent_candles", {}))
            indicators = IndicatorsConfig(**input_features_data.get("indicators", {}))
            input_features = InputFeaturesConfig(recent_candles=recent_candles, indicators=indicators)
            
            trading = TradingConfig(**data.get("trading", {}))
            
            config = cls(
                schema_version=data.get("schema_version", 1),
                metadata=metadata,
                general=general,
                labeling=labeling,
                model=model,
                hyper_parameters=hyper_parameters,
                input_features=input_features,
                trading=trading
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ConfigError(f"Failed to deserialize config: {e}")
        
        config.validate()
        return config
    
    def to_json(self, path: Path) -> None:
        """Save strategy config to JSON file with deterministic field ordering.
        
        Args:
            path: Path to write JSON configuration file
            
        Raises:
            IOError: if write fails
        """
        # Build dict with deterministic field ordering matching schema
        config_dict = {
            "schema_version": self.schema_version,
            "metadata": None,
            "general": {},
            "labeling": {},
            "model": {},
            "hyper_parameters": {},
            "input_features": {},
            "trading": {}
        }
        
        # Metadata
        if self.metadata:
            config_dict["metadata"] = {
                "created_utc": self.metadata.created_utc,
                "git_commit": self.metadata.git_commit,
                "dataset": {
                    "exchange": self.metadata.dataset.exchange,
                    "timeframe": self.metadata.dataset.timeframe,
                    "symbols": self.metadata.dataset.symbols,
                    "from_utc": self.metadata.dataset.from_utc,
                    "to_utc": self.metadata.dataset.to_utc,
                },
                "notes": self.metadata.notes,
            }
        
        # General
        config_dict["general"] = {
            "timeframe": self.general.timeframe,
            "symbols": self.general.symbols,
            "history_candles": self.general.history_candles,
        }
        
        # Labeling
        config_dict["labeling"] = {
            "window_size": self.labeling.window_size,
            "min_profit": self.labeling.min_profit,
            "max_loss": self.labeling.max_loss,
            "sell_max_profit": self.labeling.sell_max_profit,
            "sell_min_loss": self.labeling.sell_min_loss,
        }
        
        # Model
        config_dict["model"] = {
            "hidden_layers": self.model.hidden_layers,
            "activation": self.model.activation,
            "dropout_rate": self.model.dropout_rate,
            "output_dim": self.model.output_dim,
        }
        
        # Hyper parameters
        config_dict["hyper_parameters"] = {
            "train_validation_split": self.hyper_parameters.train_validation_split,
            "optimizer": {
                "name": self.hyper_parameters.optimizer.name,
                "rprop_initial_update": self.hyper_parameters.optimizer.rprop_initial_update,
                "rprop_max_step": self.hyper_parameters.optimizer.rprop_max_step,
            },
            "regularization": {
                "l2": self.hyper_parameters.regularization.l2,
            },
        }
        
        # Input features
        config_dict["input_features"] = {
            "recent_candles": {
                "count": self.input_features.recent_candles.count,
                "fields": self.input_features.recent_candles.fields,
            },
            "indicators": {
                "mins": self.input_features.indicators.mins,
                "maxs": self.input_features.indicators.maxs,
                "stls": self.input_features.indicators.stls,
                "vwaps": self.input_features.indicators.vwaps,
                "emas": self.input_features.indicators.emas,
                "atrs": self.input_features.indicators.atrs,
            },
        }
        
        # Trading
        config_dict["trading"] = {
            "buy_threshold": self.trading.buy_threshold,
            "sell_threshold": self.trading.sell_threshold,
            "position_add_fraction_backtest": self.trading.position_add_fraction_backtest,
            "position_add_fraction_live": self.trading.position_add_fraction_live,
            "sell_all_on_signal": self.trading.sell_all_on_signal,
            "fee_rate": self.trading.fee_rate,
        }
        
        # Write with consistent formatting
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(config_dict, f, indent=2)
