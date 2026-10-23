"""Парсинг каталога books.toscrape.com: HTML -> список товаров."""
import logging
import re
import time
from dataclasses import dataclass, asdict
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .config import Settings

log = logging.getLogger(__name__)

RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


@dataclass
class Product:
    title: str
    price: float
    currency: str
    rating: int
    in_stock: bool
    url: str
    image_url: str

    def to_dict(self) -> dict:
        return asdict(self)


def parse_price(text: str) -> tuple[float, str]:
    """'£51.77' -> (51.77, '£'). Терпимо к мусорным символам кодировки (Â)."""
    match = re.search(r"([^\d\s.,]*)\s*(\d[\d\s]*[.,]?\d*)", text.replace("Â", ""))
    if not match:
        raise ValueError(f"Не удалось разобрать цену: {text!r}")
    currency = match.group(1).strip()
    number = match.group(2).replace(" ", "").replace(",", ".")
    return float(number), currency


def parse_catalog_page(html: str, page_url: str) -> tuple[list[Product], Optional[str]]:
    """Возвращает товары страницы и ссылку на следующую страницу (или None)."""
    soup = BeautifulSoup(html, "lxml")
    products = []
    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")
        price_tag = card.select_one("p.price_color")
        if not link or not price_tag:
            log.warning("Пропускаю карточку без названия/цены")
            continue
        rating_tag = card.select_one("p.star-rating")
        classes = (rating_tag.get("class") or []) if rating_tag else []
        rating_word = next((c for c in classes if c in RATINGS), None)
        image = card.select_one("img")
        availability = card.select_one("p.availability") or card
        price, currency = parse_price(price_tag.get_text())
        products.append(
            Product(
                title=link.get("title") or link.get_text(strip=True),
                price=price,
                currency=currency,
                rating=RATINGS.get(rating_word, 0),
                in_stock="in stock" in availability.get_text().lower(),
                url=urljoin(page_url, link["href"]),
                image_url=urljoin(page_url, image["src"]) if image and image.get("src") else "",
            )
        )
    next_link = soup.select_one("li.next a")
    return products, urljoin(page_url, next_link["href"]) if next_link else None


def fetch(session: requests.Session, url: str, settings: Settings) -> str:
    error: Optional[Exception] = None
    for attempt in range(1, settings.retries + 1):
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            # 4xx повторять бессмысленно, 5xx — пробуем ещё раз
            if exc.response is not None and exc.response.status_code < 500:
                raise
            error = exc
        except requests.RequestException as exc:
            error = exc
        else:
            # сайт не указал кодировку -> requests считает её latin-1 и ломает символы (Â£)
            if "charset" not in resp.headers.get("Content-Type", ""):
                resp.encoding = "utf-8"
            return resp.text
        log.warning("Попытка %s/%s для %s не удалась: %s", attempt, settings.retries, url, error)
        if attempt < settings.retries:
            time.sleep(settings.request_delay * attempt)
    raise RuntimeError(f"Не удалось загрузить {url} за {settings.retries} попыток") from error


def scrape(settings: Settings, session: Optional[requests.Session] = None) -> list[Product]:
    session = session or requests.Session()
    session.headers["User-Agent"] = settings.user_agent
    url: Optional[str] = settings.base_url
    result: list[Product] = []
    pages = 0
    while url and (settings.max_pages == 0 or pages < settings.max_pages):
        html = fetch(session, url, settings)
        items, url = parse_catalog_page(html, url)
        result.extend(items)
        pages += 1
        log.info("Страница %s: %s товаров (всего %s)", pages, len(items), len(result))
        if url:
            time.sleep(settings.request_delay)
    return result


def filter_products(products, min_price=None, max_price=None, min_rating=None, only_in_stock=False):
    out = []
    for p in products:
        if min_price is not None and p.price < min_price:
            continue
        if max_price is not None and p.price > max_price:
            continue
        if min_rating is not None and p.rating < min_rating:
            continue
        if only_in_stock and not p.in_stock:
            continue
        out.append(p)
    return out
