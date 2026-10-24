"""Один запуск целиком: загрузка страниц -> разбор -> история -> выгрузки."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .config import Settings
from .exporters import EXPORTERS
from .extract import parse_page
from .filters import ProductFilter
from .http import HttpClient
from .models import Product, RunResult
from .profile import SiteProfile
from .storage import PriceStore

PageCallback = Callable[[int, str, int], None]


@dataclass(slots=True)
class RunOptions:
    max_pages: int
    formats: tuple[str, ...] = ("xlsx", "csv", "html")
    product_filter: ProductFilter = field(default_factory=ProductFilter)
    output_name: str = "products"


def scrape(
    client: HttpClient, profile: SiteProfile, max_pages: int, on_page: PageCallback | None = None
) -> tuple[list[Product], int]:
    url: str | None = profile.start_url
    products: dict[str, Product] = {}  # по url: одинаковые товары на разных страницах не дублируются
    pages = 0
    while url and (max_pages == 0 or pages < max_pages):
        html = client.get_text(url, profile.encoding)
        items, url_next = parse_page(html, url, profile)
        for item in items:
            products.setdefault(item.url, item)
        pages += 1
        if on_page:
            on_page(pages, url, len(items))
        url = url_next
    return list(products.values()), pages


def run(
    settings: Settings,
    profile: SiteProfile,
    options: RunOptions,
    client: HttpClient,
    store: PriceStore,
    on_page: PageCallback | None = None,
    now: datetime | None = None,
) -> tuple[RunResult, list[Product], dict[str, Path]]:
    started_at = now or datetime.now().astimezone()
    products, pages = scrape(client, profile, options.max_pages, on_page)

    # в историю пишем всё, фильтры влияют только на выгрузку
    diff = store.save_run(profile.name, started_at, products)
    result = RunResult(
        profile=profile.title or profile.name,
        started_at=started_at,
        products=products,
        changes=diff.changes,
        new_products=diff.new_products,
        removed=diff.removed,
        pages=pages,
        first_run=diff.first_run,
    )
    selected = options.product_filter.apply(products)
    base = settings.output_dir / options.output_name
    files = {fmt: EXPORTERS[fmt](result, selected, base) for fmt in options.formats}
    return result, selected, files
