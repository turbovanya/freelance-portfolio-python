import csv
import io
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from harness import ROOT

from lead_bot.config import Settings
from lead_bot.db import Lead, LeadStatus
from lead_bot.services import Faq, clean_comment, csv_safe, leads_to_csv, normalize_phone, validate_name


@pytest.mark.parametrize("raw", ["+7 (912) 345-67-89", "8 912 345 67 89", "79123456789", "9123456789"])
def test_phone_normalized(raw):
    assert normalize_phone(raw) == "+79123456789"


@pytest.mark.parametrize("raw", ["", "123", "abc", "+1 202 555 0100", "891234", "+7 000 000 00 00"])
def test_phone_rejected(raw):
    assert normalize_phone(raw) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("  Иван   Петров ", "Иван Петров"), ("Анна-Мария", "Анна-Мария"), ("O'Neil", "O'Neil")],
)
def test_name_accepted(raw, expected):
    assert validate_name(raw) == expected


@pytest.mark.parametrize("raw", ["И", "Ivan2", "x" * 51, "!!!", "👍👍", "--"])
def test_name_rejected(raw):
    assert validate_name(raw) is None


def test_comment_cleaned_and_limited():
    assert clean_comment("  много   пробелов ") == "много пробелов"
    assert len(clean_comment("a" * 1000)) == 500


def test_faq_search_handles_word_forms():
    faq = Faq.load(ROOT / "faq.json")
    assert "50%" in faq.find("Как можно оплатить заказ?").answer
    assert faq.find("Сколько это будет стоить").question == "Сколько стоит услуга?"
    assert faq.find("какие у вас сроки?").question == "Как быстро вы работаете?"
    assert faq.find("абракадабра") is None


def test_csv_safe():
    assert csv_safe("=1+1") == "'=1+1"
    assert csv_safe("-5") == "'-5"
    assert csv_safe("+79123456789") == "+79123456789"
    assert csv_safe(None) == ""


def test_csv_export_format():
    lead = Lead(
        id=1, user_id=7, username=None, name="Иван", phone="+79123456789", comment="=HYPERLINK(1); срочно",
        status=LeadStatus.IN_WORK, created_at=datetime(2026, 10, 24, 9, 30, tzinfo=UTC),
    )  # fmt: skip
    rows = list(
        csv.reader(
            io.StringIO(leads_to_csv([lead], ZoneInfo("Europe/Moscow")).decode("utf-8-sig")), delimiter=";"
        )
    )
    assert rows[0][0] == "№"
    assert rows[1] == [
        "1",
        "24.10.2026 12:30",
        "Иван",
        "+79123456789",
        "'=HYPERLINK(1); срочно",
        "7",
        "В работе",
    ]


def test_settings_parse_admin_ids_and_validate_timezone():
    s = Settings(_env_file=None, bot_token="1:x", admin_ids="1, 2,x,, -3")
    assert s.admin_ids == [1, 2, -3]
    with pytest.raises(ValueError):
        Settings(_env_file=None, bot_token="1:x", timezone="Mars/Olympus")
