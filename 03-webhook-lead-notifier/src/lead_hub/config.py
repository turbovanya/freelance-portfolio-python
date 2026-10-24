from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

INSECURE_KEYS = {"", "change-me", "secret", "test"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_key: SecretStr
    database_url: str = "sqlite+aiosqlite:///data/leads.db"

    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""

    admin_user: str = "admin"
    admin_password: SecretStr = SecretStr("")

    allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])
    rate_limit_per_minute: int = Field(default=10, ge=1)
    resend_interval_seconds: int = Field(default=60, ge=5)
    timezone: str = "Europe/Moscow"
    # показывать демонстрационную форму на /demo
    demo_form: bool = False

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token.get_secret_value() and self.telegram_chat_id)

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password.get_secret_value())

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def check_production_ready(self) -> None:
        key = self.api_key.get_secret_value()
        if key in INSECURE_KEYS or len(key) < 16:
            raise RuntimeError(
                "Задайте в .env случайный API_KEY от 16 символов: со слабым ключом сервис не запускается"
            )
