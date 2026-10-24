"""Входные и выходные модели API.

Формы на разных конструкторах называют поля по-разному (Name, fio, Phone, tel...),
поэтому входные данные сначала приводятся к единым именам.
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "fio", "fullname", "first_name", "имя"),
    "phone": ("phone", "tel", "telephone", "phone_number", "телефон"),
    "email": ("email", "e-mail", "mail", "почта"),
    "message": ("message", "comment", "comments", "text", "question", "сообщение", "комментарий"),
    "source": ("source", "formname", "form_name", "form"),
    "page_url": ("page_url", "referer", "referrer", "page"),
    "utm_source": ("utm_source",),
    "utm_medium": ("utm_medium",),
    "utm_campaign": ("utm_campaign",),
    "website": ("website", "hp", "honeypot"),
}
_LOOKUP = {alias: field for field, aliases in ALIASES.items() for alias in aliases}


def normalize_payload(raw: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in raw.items():
        field = _LOOKUP.get(str(key).strip().lower())
        if field and field not in result and value not in (None, ""):
            result[field] = value.strip() if isinstance(value, str) else value
    return result


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "3489":
        raise ValueError("некорректный номер телефона, нужен российский номер")
    return "+7" + digits


class LeadIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=80)
    phone: str
    email: EmailStr | None = None
    message: str = Field(default="", max_length=2000)
    source: str = Field(default="website", max_length=80)
    page_url: str | None = Field(default=None, max_length=500)
    utm_source: str | None = Field(default=None, max_length=100)
    utm_medium: str | None = Field(default=None, max_length=100)
    utm_campaign: str | None = Field(default=None, max_length=100)
    # ловушка для ботов: поле скрыто на странице, человек его не заполняет
    website: str = ""

    @field_validator("name", "message", "source")
    @classmethod
    def _squash_spaces(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        return normalize_phone(value)


class LeadCreated(BaseModel):
    ok: bool = True
    id: int | None
    duplicate: bool = False


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    email: str | None
    message: str
    source: str
    utm_source: str | None
    utm_campaign: str | None
    created_at: datetime
    notified: bool
    notify_attempts: int


class LeadPage(BaseModel):
    items: list[LeadOut]
    total: int
    limit: int
    offset: int
