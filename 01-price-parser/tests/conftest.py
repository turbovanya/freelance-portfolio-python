from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from price_parser.config import Settings
from price_parser.http import HttpClient
from price_parser.models import Product
from price_parser.profile import load_profile
from price_parser.storage import PriceStore

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://books.toscrape.com/"


@pytest.fixture
def profile():
    return load_profile(ROOT / "profiles" / "books.yaml")


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        profiles_dir=ROOT / "profiles",
        output_dir=tmp_path / "out",
        db_path=tmp_path / "prices.db",
        request_delay=0,
        retries=3,
    )


@pytest.fixture
def store():
    with PriceStore(":memory:") as s:
        yield s


def catalog_transport(pages: dict[str, str]) -> httpx.MockTransport:
    """Отдаёт фикстуры вместо настоящего сайта: {url: имя файла}."""

    def handler(request: httpx.Request) -> httpx.Response:
        name = pages.get(str(request.url))
        if name is None:
            return httpx.Response(404)
        body = (FIXTURES / name).read_bytes()
        return httpx.Response(200, content=body, headers={"content-type": "text/html"})

    return httpx.MockTransport(handler)


@pytest.fixture
def site_client(settings):
    transport = catalog_transport({BASE: "catalog_page1.html", BASE + "page-2.html": "catalog_page2.html"})
    with HttpClient(settings, transport=transport, sleep=lambda _: None) as client:
        yield client


def product(url="u1", price=10.0, rating=3, in_stock=True, title="Книга"):
    return Product(title=title, url=url, price=price, currency="£", rating=rating, in_stock=in_stock)


NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
