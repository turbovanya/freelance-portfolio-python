"""Короткая сводка в Telegram после запуска, если цены изменились."""

import html
import logging

import httpx

from .config import Settings
from .models import RunResult

log = logging.getLogger(__name__)
MAX_LINES = 15


def build_message(result: RunResult, threshold_percent: float = 0.0) -> str | None:
    changes = [c for c in result.changes if abs(c.percent) >= threshold_percent]
    if not changes and not result.new_products:
        return None
    lines = [f"<b>Мониторинг цен: {html.escape(result.profile)}</b>"]
    if changes:
        up = sum(c.is_increase for c in changes)
        lines.append(f"Изменилось цен: {len(changes)} (выросло {up}, снизилось {len(changes) - up})\n")
        for c in changes[:MAX_LINES]:
            arrow = "🔺" if c.is_increase else "🔻"
            lines.append(
                f'{arrow} <a href="{html.escape(c.url)}">{html.escape(c.title)}</a>: '
                f"{c.old_price:g} → {c.new_price:g} ({c.percent:+.1f}%)"
            )
        if len(changes) > MAX_LINES:
            lines.append(f"...и ещё {len(changes) - MAX_LINES}")
    if result.new_products:
        lines.append(f"\nНовых товаров: {len(result.new_products)}")
    return "\n".join(lines)


def send_telegram(settings: Settings, text: str, transport: httpx.BaseTransport | None = None) -> bool:
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        with httpx.Client(timeout=10, transport=transport) as client:
            resp = client.post(url, json=payload)
        resp.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        log.error("Не удалось отправить уведомление в Telegram: %s", exc)
        return False
