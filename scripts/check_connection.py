"""
Hello-world script: connect to Bitvavo and read the exchange time.

Reads credentials from:
  <workspace_path>/<exchange>/account.toml

Expected account.toml format:
  api_key    = "your-api-key"
  api_secret = "your-api-secret"

Run from the project root:
  uv run scripts/check_connection.py
"""

import tomllib
from datetime import datetime, timezone
from pathlib import Path

import ccxt


def load_bot_config(project_root: Path) -> dict:
    with open(project_root / "bot.toml", "rb") as f:
        return tomllib.load(f)


def load_account_config(workspace_path: str, exchange: str) -> dict:
    account_path = Path(workspace_path) / exchange / "account.toml"
    with open(account_path, "rb") as f:
        data = tomllib.load(f)
    # Support both flat and [account]-table formats
    return data.get("account", data)


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent

    bot_cfg = load_bot_config(project_root)["bot"]
    workspace_path: str = bot_cfg["workspace_path"]
    exchange_id: str = bot_cfg["exchange"]

    account_cfg = load_account_config(workspace_path, exchange_id)
    api_key: str = account_cfg["api_key"]
    api_secret: str = account_cfg["api_secret"]

    exchange: ccxt.Exchange = getattr(ccxt, exchange_id)(
        {"apiKey": api_key, "secret": api_secret}
    )

    print(f"Exchange : {exchange.name}")
    print(f"API URL  : {exchange.urls['api']}")

    server_time_ms: int = exchange.fetch_time()
    server_dt = datetime.fromtimestamp(server_time_ms / 1000, tz=timezone.utc)
    local_dt = datetime.now(tz=timezone.utc)
    drift_ms = server_time_ms - int(local_dt.timestamp() * 1000)

    print(f"Server time : {server_dt.isoformat()}")
    print(f"Local time  : {local_dt.isoformat()}")
    print(f"Clock drift : {drift_ms:+d} ms")
    print("\nConnection successful.")


if __name__ == "__main__":
    main()
