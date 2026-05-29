"""Unit tests for strategy configuration module."""

import json
import tempfile
from pathlib import Path
import pytest

from ccxt_pred.config import (
    StrategyConfig, Metadata, DatasetMetadata, GeneralConfig, LabelingConfig,
    ModelConfig, HyperParametersConfig, InputFeaturesConfig, TradingConfig,
    ConfigError
)


def test_default_strategy_config():
    """Test that default StrategyConfig has all defaults set correctly."""
    config = StrategyConfig()
    
    assert config.schema_version == 1
    assert config.general.timeframe == "30m"
    assert config.general.history_candles == 1400
    assert config.labeling.window_size == 6
    assert config.labeling.min_profit == 1.02
    assert config.model.hidden_layers == [30, 10, 5]
    assert config.model.activation == "elliot_symmetric"
    assert config.model.dropout_rate == 0.4
    assert config.trading.buy_threshold == 0.2
    assert config.trading.sell_threshold == -0.1


def test_valid_config_validates():
    """Test that a valid config passes validation."""
    config = StrategyConfig(
        general=GeneralConfig(
            timeframe="30m",
            symbols=["BTC-EUR", "ETH-EUR"],
            history_candles=1400
        )
    )
    # Should not raise
    config.validate()


def test_invalid_schema_version():
    """Test validation fails with wrong schema version."""
    config = StrategyConfig(schema_version=2)
    with pytest.raises(ConfigError, match="schema_version must equal 1"):
        config.validate()


def test_invalid_empty_symbols():
    """Test validation fails with empty symbols list."""
    config = StrategyConfig(
        general=GeneralConfig(symbols=[])
    )
    with pytest.raises(ConfigError, match="must be a non-empty array"):
        config.validate()


def test_invalid_symbol_format():
    """Test validation fails with invalid symbol format."""
    config = StrategyConfig(
        general=GeneralConfig(symbols=["INVALID"])
    )
    with pytest.raises(ConfigError, match="BASE-QUOTE format"):
        config.validate()


def test_invalid_history_candles():
    """Test validation fails when history_candles < max indicator window."""
    config = StrategyConfig(
        general=GeneralConfig(
            symbols=["BTC-EUR"],
            history_candles=100  # Too small; default max window is 1400
        )
    )
    with pytest.raises(ConfigError, match="history_candles.*must be"):
        config.validate()


def test_invalid_dropout_rate():
    """Test validation fails with invalid dropout rate."""
    config = StrategyConfig(
        model=ModelConfig(dropout_rate=1.5),
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    with pytest.raises(ConfigError, match="dropout_rate must be in"):
        config.validate()


def test_invalid_activation():
    """Test validation fails with unsupported activation."""
    config = StrategyConfig(
        model=ModelConfig(activation="tanh"),
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    with pytest.raises(ConfigError, match="activation"):
        config.validate()


def test_invalid_sell_threshold():
    """Test validation fails when sell_threshold >= buy_threshold."""
    config = StrategyConfig(
        trading=TradingConfig(
            buy_threshold=0.2,
            sell_threshold=0.3  # Invalid: should be less
        ),
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    with pytest.raises(ConfigError, match="sell_threshold.*must be"):
        config.validate()


def test_invalid_train_split():
    """Test validation fails with invalid train/validation split."""
    config = StrategyConfig(
        hyper_parameters=HyperParametersConfig(
            train_validation_split=1.5
        ),
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    with pytest.raises(ConfigError, match="train_validation_split"):
        config.validate()


def test_rfc3339_timestamp_validation():
    """Test RFC3339 timestamp validation."""
    # Valid timestamp
    config = StrategyConfig(
        metadata=Metadata(
            created_utc="2026-05-29T12:00:00Z",
            git_commit="abc123",
            dataset=DatasetMetadata(
                exchange="bitvavo",
                timeframe="30m",
                symbols=["BTC-EUR"],
                from_utc="2019-03-08T10:30:00Z",
                to_utc="2026-05-25T16:30:00Z"
            )
        ),
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    config.validate()  # Should not raise
    
    # Invalid timezone (not UTC)
    with pytest.raises(ConfigError, match="UTC"):
        config.metadata.created_utc = "2026-05-29T12:00:00+01:00"
        config.validate()


def test_json_roundtrip():
    """Test that config can be serialized to JSON and deserialized back."""
    original = StrategyConfig(
        metadata=Metadata(
            created_utc="2026-05-29T12:00:00Z",
            git_commit="abc123def",
            dataset=DatasetMetadata(
                exchange="bitvavo",
                timeframe="30m",
                symbols=["BTC-EUR", "ETH-EUR"],
                from_utc="2019-03-08T10:30:00Z",
                to_utc="2026-05-25T16:30:00Z"
            ),
            notes="Test config"
        ),
        general=GeneralConfig(
            timeframe="30m",
            symbols=["BTC-EUR", "ETH-EUR"],
            history_candles=1400
        )
    )
    original.validate()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.json"
        original.to_json(path)
        loaded = StrategyConfig.from_json(path)
        
        # Verify all fields match
        assert loaded.schema_version == original.schema_version
        assert loaded.general.timeframe == original.general.timeframe
        assert loaded.general.symbols == original.general.symbols
        assert loaded.metadata.created_utc == original.metadata.created_utc
        assert loaded.metadata.git_commit == original.metadata.git_commit
        assert loaded.metadata.notes == original.metadata.notes


def test_json_deterministic_ordering():
    """Test that JSON output is deterministic (same field order each time)."""
    config = StrategyConfig(
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        path1 = Path(tmpdir) / "config1.json"
        path2 = Path(tmpdir) / "config2.json"
        
        config.to_json(path1)
        config.to_json(path2)
        
        content1 = path1.read_text()
        content2 = path2.read_text()
        
        # Same content
        assert content1 == content2
        
        # Verify top-level field order matches schema
        data = json.loads(content1)
        keys = list(data.keys())
        expected_order = [
            "schema_version", "metadata", "general", "labeling", "model",
            "hyper_parameters", "input_features", "trading"
        ]
        assert keys == expected_order


def test_missing_file_raises():
    """Test that loading from non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        StrategyConfig.from_json(Path("/nonexistent/path.json"))


def test_invalid_json_raises():
    """Test that invalid JSON raises ConfigError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "invalid.json"
        path.write_text("{invalid json")
        
        with pytest.raises(ConfigError, match="Invalid JSON"):
            StrategyConfig.from_json(path)


def test_missing_required_field_raises():
    """Test that missing required fields raise ConfigError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.json"
        # Write minimal valid config but missing general.symbols
        path.write_text(json.dumps({
            "schema_version": 1,
            "general": {"timeframe": "30m", "history_candles": 1400},
        }))
        
        with pytest.raises(ConfigError):
            StrategyConfig.from_json(path)


def test_config_with_all_defaults():
    """Test that a config using defaults (with valid symbols) is valid."""
    config = StrategyConfig(
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    # Should not raise
    config.validate()
    
    # Verify defaults are applied
    assert config.general.timeframe == "30m"
    assert config.general.history_candles == 1400
    assert config.labeling.window_size == 6
    assert config.model.dropout_rate == 0.4


def test_indicator_windows_validation():
    """Test that indicator window validation catches non-positive integers."""
    config = StrategyConfig(
        input_features=InputFeaturesConfig(
            indicators=__import__('ccxt_pred.config', fromlist=['IndicatorsConfig']).IndicatorsConfig(
                mins=[5, 0, 34]  # Invalid: 0 is not positive
            )
        ),
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    with pytest.raises(ConfigError, match="must contain positive integers"):
        config.validate()


def test_recent_candles_fields_validation():
    """Test validation of recent candles fields."""
    from ccxt_pred.config import RecentCandlesConfig
    
    config = StrategyConfig(
        input_features=InputFeaturesConfig(
            recent_candles=RecentCandlesConfig(
                fields=["open", "invalid_field"]
            )
        ),
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    with pytest.raises(ConfigError, match="subset of"):
        config.validate()


def test_empty_hidden_layers():
    """Test validation fails with empty hidden layers."""
    config = StrategyConfig(
        model=ModelConfig(hidden_layers=[]),
        general=GeneralConfig(symbols=["BTC-EUR"])
    )
    with pytest.raises(ConfigError, match="non-empty array"):
        config.validate()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
