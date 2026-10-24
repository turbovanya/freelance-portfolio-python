from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr
    admin_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    database_url: str = "sqlite+aiosqlite:///data/leads.db"
    faq_path: Path = Path("faq.json")
    business_name: str = "Студия «Пример»"
    timezone: str = "Europe/Moscow"
    # защита от спама: сколько заявок один человек может оставить за сутки
    max_leads_per_day: int = Field(default=3, ge=1)

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [int(x) for x in value.replace(" ", "").split(",") if x.lstrip("-").isdigit()]
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"неизвестный часовой пояс: {value}") from exc
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)
