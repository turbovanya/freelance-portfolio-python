"""Профиль сайта: какие CSS-селекторы использовать для каждого поля.

Под новый сайт не нужно трогать код, достаточно добавить YAML-файл в папку profiles/.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

FieldName = Literal["title", "url", "price", "currency", "rating", "in_stock", "image_url"]
REQUIRED_FIELDS = {"title", "url", "price"}


class FieldRule(BaseModel):
    selector: str
    attr: str | None = None  # None: берём текст элемента
    type: Literal["str", "price", "int", "bool"] = "str"
    absolute: bool = False  # превратить относительную ссылку в полную
    map: dict[str, int] | None = None  # для рейтинга вида class="star-rating Three"
    contains: str | None = None  # для bool: True, если текст содержит подстроку
    default: str | int | float | bool | None = None


class SiteProfile(BaseModel):
    name: str
    title: str = ""
    start_url: str
    item: str = Field(description="селектор карточки товара")
    next_page: str | None = None
    encoding: str | None = None
    fields: dict[FieldName, FieldRule]

    @model_validator(mode="after")
    def _check_required(self) -> "SiteProfile":
        missing = REQUIRED_FIELDS - set(self.fields)
        if missing:
            raise ValueError(f"в профиле {self.name} не хватает полей: {', '.join(sorted(missing))}")
        return self


def load_profile(path: Path) -> SiteProfile:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.setdefault("name", path.stem)
    return SiteProfile.model_validate(data)


def find_profile(profiles_dir: Path, name: str) -> SiteProfile:
    path = profiles_dir / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(p.stem for p in sorted(profiles_dir.glob("*.yaml"))) or "нет"
        raise FileNotFoundError(f"профиль {name!r} не найден. Доступные: {available}")
    return load_profile(path)


def list_profiles(profiles_dir: Path) -> list[SiteProfile]:
    return [load_profile(p) for p in sorted(profiles_dir.glob("*.yaml"))]
