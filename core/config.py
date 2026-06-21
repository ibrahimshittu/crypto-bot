"""Central configuration, loaded from environment / .env."""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingEnv(str, Enum):
    DEMO = "demo"
    TESTNET = "testnet"
    LIVE = "live"


BYBIT_REST_HOSTS = {
    TradingEnv.DEMO: "https://api-demo.bybit.com",
    TradingEnv.TESTNET: "https://api-testnet.bybit.com",
    TradingEnv.LIVE: "https://api.bybit.com",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    trading_env: TradingEnv = TradingEnv.DEMO

    bybit_api_key: str = ""
    bybit_api_secret: str = ""
    bybit_api_private_key_path: str = ""

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "minimax/minimax-m3"

    exa_api_key: str = ""
    cryptopanic_api_key: str = ""
    lunarcrush_api_key: str = ""     # unused (free tier has no social data)
    santiment_api_key: str = ""

    database_url: str = "postgresql://crypto:crypto@localhost:5432/crypto_bot"
    redis_url: str = "redis://localhost:6379/0"

    logfire_token: str = ""
    logfire_environment: str = "dev"

    universe_max_symbols: int = Field(default=150, ge=0)   # 0 = scan the ENTIRE universe
    max_candidates: int = Field(default=25, ge=1)
    max_new_orders_per_cycle: int = Field(default=3, ge=1)
    cycle_seconds: float = Field(default=60.0, ge=5.0)

    risk_per_trade_pct: float = Field(default=1.0, ge=0.0, le=100.0)
    max_position_pct: float = Field(default=20.0, ge=0.0, le=100.0)
    daily_loss_halt_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    max_leverage: float = Field(default=3.0, ge=1.0, le=125.0)

    @property
    def is_live(self) -> bool:
        return self.trading_env == TradingEnv.LIVE

    @property
    def bybit_rest_host(self) -> str:
        return BYBIT_REST_HOSTS[self.trading_env]

    @property
    def bybit_use_testnet_flag(self) -> bool:
        """pybit's `testnet` constructor flag (demo uses its own host, not this flag)."""
        return self.trading_env == TradingEnv.TESTNET


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so every module shares one Settings instance."""
    return Settings()
