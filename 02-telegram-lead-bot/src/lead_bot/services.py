"""Логика без Telegram: проверка ввода, поиск по FAQ, выгрузка CSV."""

import csv
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from .db import Lead


def validate_name(text: str) -> str | None:
    """Имя: 2-50 символов, только буквы, пробел, дефис и апостроф."""
    name = " ".join((text or "").split())
    if not 2 <= len(name) <= 50 or not re.fullmatch(r"[^\W\d_]+(?:[ '\-][^\W\d_]+)*", name):
        return None
    return name


def normalize_phone(text: str) -> str | None:
    """Российский номер в любом виде -> +7XXXXXXXXXX. Мобильные на 9, городские на 3, 4, 8."""
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10 or digits[0] not in "3489":
        return None
    return "+7" + digits


def clean_comment(text: str, limit: int = 500) -> str:
    return " ".join((text or "").split())[:limit]


@dataclass(slots=True, frozen=True)
class FaqItem:
    question: str
    answer: str
    keywords: tuple[str, ...]


class Faq:
    """Поиск ответа по ключевым словам. Сравниваем начала слов, чтобы работали падежи и окончания."""

    STEM = 5

    def __init__(self, items: list[FaqItem]) -> None:
        self.items = items

    @classmethod
    def load(cls, path: Path) -> "Faq":
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            [FaqItem(i["question"], i["answer"], tuple(k.lower() for k in i["keywords"])) for i in raw]
        )

    def find(self, text: str) -> FaqItem | None:
        words = re.findall(r"\w+", (text or "").lower())
        best, best_score = None, 0
        for item in self.items:
            score = sum(1 for kw in item.keywords if any(w.startswith(kw[: self.STEM]) for w in words))
            if score > best_score:
                best, best_score = item, score
        return best


def csv_safe(value: object) -> str:
    """Excel выполняет ячейки, начинающиеся с = + - @, как формулы. Пользовательский ввод экранируем."""
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@") and not re.fullmatch(r"\+7\d{10}", text):
        return "'" + text
    return text


def leads_to_csv(leads: list[Lead], tz: ZoneInfo) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["№", "Дата", "Имя", "Телефон", "Комментарий", "Telegram", "Статус"])
    for lead in leads:
        writer.writerow(
            [
                lead.id,
                lead.created_local(tz).strftime("%d.%m.%Y %H:%M"),
                csv_safe(lead.name),
                lead.phone,
                csv_safe(lead.comment),
                f"@{lead.username}" if lead.username else lead.user_id,
                lead.status.label.split(" ", 1)[1],
            ]
        )
    return buf.getvalue().encode("utf-8-sig")
