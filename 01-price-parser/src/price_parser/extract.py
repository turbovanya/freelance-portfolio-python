"""Разбор HTML-страницы каталога по правилам из профиля."""

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import Product
from .profile import FieldRule, SiteProfile

log = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"([^\d\s.,]*)\s*(\d[\d\s ]*(?:[.,]\d+)?)\s*([^\d\s.,]*)")


class ExtractError(ValueError):
    pass


def parse_price(text: str) -> tuple[float, str]:
    """'£51.77' -> (51.77, '£'), '1 299,90 ₽' -> (1299.9, '₽')."""
    match = _PRICE_RE.search(text.replace("Â", ""))
    if not match:
        raise ExtractError(f"не удалось разобрать цену: {text!r}")
    before, number, after = match.groups()
    number = re.sub(r"[\s ]", "", number).replace(",", ".")
    return float(number), (before or after).strip()


def _raw_value(card: Tag, rule: FieldRule) -> str | list[str] | None:
    el = card.select_one(rule.selector)
    if el is None:
        return None
    if rule.attr is None:
        return el.get_text(" ", strip=True)
    value = el.get(rule.attr)
    return value if value is None or isinstance(value, (str, list)) else str(value)


def _convert(raw: str | list[str] | None, rule: FieldRule, page_url: str) -> object:
    if raw is None:
        return rule.default
    if rule.map is not None:
        tokens = raw if isinstance(raw, list) else raw.split()
        return next((rule.map[t] for t in tokens if t in rule.map), rule.default)
    text = " ".join(raw) if isinstance(raw, list) else raw
    if rule.type == "bool":
        return (rule.contains or "").lower() in text.lower()
    if rule.type == "int":
        digits = re.sub(r"\D", "", text)
        return int(digits) if digits else rule.default
    if rule.type == "price":
        return parse_price(text)
    if rule.absolute:
        return urljoin(page_url, text)
    return text


def parse_page(html: str, page_url: str, profile: SiteProfile) -> tuple[list[Product], str | None]:
    """Возвращает товары со страницы и адрес следующей страницы (или None)."""
    soup = BeautifulSoup(html, "lxml")
    products: list[Product] = []
    for index, card in enumerate(soup.select(profile.item), start=1):
        values: dict[str, object] = {}
        try:
            for name, rule in profile.fields.items():
                values[name] = _convert(_raw_value(card, rule), rule, page_url)
            price = values.pop("price")
            if not isinstance(price, tuple):
                raise ExtractError("нет цены")
            values["price"], currency = price
            values.setdefault("currency", currency)
            if not values.get("title") or not values.get("url"):
                raise ExtractError("нет названия или ссылки")
            products.append(Product(**values))  # type: ignore[arg-type]
        except (ExtractError, TypeError) as exc:
            log.warning("%s: карточка %s пропущена (%s)", page_url, index, exc)

    next_url = None
    if profile.next_page:
        link = soup.select_one(profile.next_page)
        href = link.get("href") if link else None
        if isinstance(href, str):
            next_url = urljoin(page_url, href)
    return products, next_url
