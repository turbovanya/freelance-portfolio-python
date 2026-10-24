import logging
from html import escape
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx

from .db import Lead

log = logging.getLogger(__name__)


class NotifyError(RuntimeError):
    pass


class Notifier(Protocol):
    enabled: bool

    async def send(self, text: str) -> None: ...


def format_lead(lead: Lead, tz: ZoneInfo) -> str:
    lines = [
        f"🔔 <b>Заявка №{lead.id}</b> · {escape(lead.source)}",
        "",
        f"👤 {escape(lead.name)}",
        f"📞 <code>{lead.phone}</code>",
    ]
    if lead.email:
        lines.append(f"✉️ {escape(lead.email)}")
    if lead.message:
        lines.append(f"💬 {escape(lead.message)}")
    utm = " / ".join(escape(v) for v in (lead.utm_source, lead.utm_medium, lead.utm_campaign) if v)
    if utm:
        lines.append(f"📈 {utm}")
    lines.append(f"🕒 {lead.local_time(tz):%d.%m.%Y %H:%M}")
    return "\n".join(lines)


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._transport = transport
        self.enabled = bool(token and chat_id)

    async def send(self, text: str) -> None:
        if not self.enabled:
            raise NotifyError("Telegram не настроен")
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            async with httpx.AsyncClient(timeout=10, transport=self._transport) as client:
                resp = await client.post(self._url, json=payload)
        except httpx.HTTPError as exc:
            raise NotifyError(f"сеть: {exc}") from exc
        if resp.status_code != 200:
            # токен в тексте ошибки не светим, только ответ Telegram
            raise NotifyError(f"Telegram {resp.status_code}: {resp.text[:200]}")
