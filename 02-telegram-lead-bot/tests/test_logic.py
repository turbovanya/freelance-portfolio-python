import csv
import io

import pytest

from bot.config import Config, parse_admin_ids
from bot.db import LeadStorage
from bot.faq import find_answer, load_faq
from bot.validators import clean_comment, csv_safe, normalize_phone, validate_name


@pytest.mark.parametrize("raw", ["+7 (912) 345-67-89", "8 912 345 67 89", "79123456789", "9123456789"])
def test_phone_normalized(raw):
    assert normalize_phone(raw) == "+79123456789"


@pytest.mark.parametrize("raw", ["", "123", "abc", "+1 202 555 0100", "891234", "+7 000 000 00 00"])
def test_phone_invalid(raw):
    assert normalize_phone(raw) is None


def test_name_validation():
    assert validate_name("  Иван   Петров ") == "Иван Петров"
    assert validate_name("И") is None
    assert validate_name("Ivan2") is None
    assert validate_name("x" * 51) is None


def test_comment_cleaning():
    assert clean_comment("  много   пробелов ") == "много пробелов"
    assert len(clean_comment("a" * 1000)) == 500


def test_storage_add_stats_export():
    s = LeadStorage(":memory:")
    assert s.stats() == {"total": 0, "last_day": 0}
    lead_id = s.add(1, "ivan", "Иван", "+79123456789", "нужен бот; срочно")
    s.add(2, None, "Мария", "+79990001122", "")
    assert lead_id == 1
    assert s.stats() == {"total": 2, "last_day": 2}
    assert [r["name"] for r in s.recent(1)] == ["Мария"]
    rows = list(csv.reader(io.StringIO(s.export_csv().decode("utf-8-sig")), delimiter=";"))
    assert len(rows) == 3 and rows[1][4] == "+79123456789"
    assert rows[1][5] == "нужен бот; срочно"  # разделитель внутри поля экранируется


def test_csv_export_neutralizes_formulas():
    s = LeadStorage(":memory:")
    s.add(1, None, "Иван", "+79123456789", '=HYPERLINK("http://evil","x")')
    rows = list(csv.reader(io.StringIO(s.export_csv().decode("utf-8-sig")), delimiter=";"))
    assert rows[1][5].startswith("'=")
    assert rows[1][4] == "+79123456789"  # телефон не портим
    assert csv_safe("-1") == "'-1" and csv_safe(None) == ""


def test_faq_search():
    faq = load_faq("faq.json")
    assert "50%" in find_answer(faq, "Как можно оплатить заказ?")["answer"]
    assert find_answer(faq, "Сколько это будет стоить")["question"] == "Сколько стоит услуга?"
    assert find_answer(faq, "абракадабра") is None


def test_admin_ids_parsing():
    assert parse_admin_ids("1, 2,x,, 3") == [1, 2, 3]
    assert parse_admin_ids("") == []


def test_config_requires_token(monkeypatch):
    monkeypatch.setattr("bot.config.load_dotenv", lambda: None)
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        Config.from_env()
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    monkeypatch.setenv("ADMIN_IDS", "42")
    cfg = Config.from_env()
    assert cfg.token == "123:abc" and cfg.admin_ids == [42]
