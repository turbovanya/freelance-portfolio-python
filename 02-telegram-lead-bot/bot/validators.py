import re
from typing import Optional


def validate_name(text: str) -> Optional[str]:
    """Имя: 2–50 символов, без цифр. Возвращает очищенное имя или None."""
    name = " ".join((text or "").split())
    if not 2 <= len(name) <= 50 or re.search(r"\d", name):
        return None
    return name


def normalize_phone(text: str) -> Optional[str]:
    """Российский номер -> +7XXXXXXXXXX. Принимает 8..., +7..., 7..., со скобками и дефисами."""
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10 or digits[0] != "9" and not digits[0] in "348":
        return None
    return "+7" + digits


def clean_comment(text: str, limit: int = 500) -> str:
    return " ".join((text or "").split())[:limit]
