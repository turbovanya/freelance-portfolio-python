import pytest

from conftest import FIXTURES
from price_parser.extract import ExtractError, parse_page, parse_price
from price_parser.profile import SiteProfile, list_profiles

URL = "https://books.toscrape.com/"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("£51.77", (51.77, "£")),
        ("Â£51.77", (51.77, "£")),
        ("1 299,90 ₽", (1299.9, "₽")),
        ("1 299 ₽", (1299.0, "₽")),
        ("$ 15", (15.0, "$")),
    ],
)
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_parse_price_rejects_garbage():
    with pytest.raises(ExtractError):
        parse_price("бесплатно")


def test_parse_page_by_profile(profile):
    html = (FIXTURES / "catalog_page1.html").read_text(encoding="utf-8")
    products, next_url = parse_page(html, URL, profile)

    assert len(products) == 2  # битая карточка пропущена, а не уронила разбор
    first, second = products
    assert first.title == "A Light in the Attic"
    assert (first.price, first.currency, first.rating, first.in_stock) == (51.77, "£", 3, True)
    assert first.url == "https://books.toscrape.com/a-light-in-the-attic_1000/index.html"
    assert first.image_url == "https://books.toscrape.com/media/a.jpg"
    assert (second.rating, second.in_stock) == (5, False)
    assert next_url == "https://books.toscrape.com/page-2.html"


def test_last_page_has_no_next(profile):
    html = (FIXTURES / "catalog_page2.html").read_text(encoding="utf-8")
    _, next_url = parse_page(html, URL, profile)
    assert next_url is None


def test_profile_requires_core_fields():
    with pytest.raises(ValueError, match="price"):
        SiteProfile.model_validate(
            {
                "name": "x",
                "start_url": URL,
                "item": "li",
                "fields": {"title": {"selector": "a"}, "url": {"selector": "a"}},
            }
        )


def test_all_bundled_profiles_are_valid(settings):
    names = {p.name for p in list_profiles(settings.profiles_dir)}
    assert "books" in names
