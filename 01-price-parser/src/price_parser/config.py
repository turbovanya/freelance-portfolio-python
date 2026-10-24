"""Настройки приложения. Читаются из переменных окружения и файла .env."""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    profiles_dir: Path = Path("profiles")
    output_dir: Path = Path("output")
    db_path: Path = Path("output/prices.db")

    max_pages: int = Field(default=3, ge=0, description="0 = все страницы")
    request_delay: float = Field(default=0.5, ge=0, description="пауза между запросами, сек")
    request_timeout: float = Field(default=15.0, gt=0)
    retries: int = Field(default=3, ge=1)
    user_agent: str = "Mozilla/5.0 (compatible; price-parser/1.2; +https://github.com/turbovanya)"
    proxy: str | None = None

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    # уведомлять только об изменениях больше этого порога, в процентах
    notify_threshold_percent: float = Field(default=0.0, ge=0)

    @field_validator("proxy", mode="before")
    @classmethod
    def _empty_proxy(cls, value: str | None) -> str | None:
        return value or None

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)
