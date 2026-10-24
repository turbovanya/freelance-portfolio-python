"""Доставка уведомлений и выгрузка. Не зависит от FastAPI, поэтому легко тестируется."""

import asyncio
import csv
import io
import logging
from zoneinfo import ZoneInfo

from .db import Lead, LeadRepository
from .notifier import Notifier, NotifyError, format_lead

log = logging.getLogger(__name__)


class Delivery:
    def __init__(self, repo: LeadRepository, notifier: Notifier, tz: ZoneInfo) -> None:
        self.repo, self.notifier, self.tz = repo, notifier, tz

    async def deliver(self, lead: Lead) -> bool:
        try:
            await self.notifier.send(format_lead(lead, self.tz))
        except NotifyError as exc:
            log.warning("Заявка №%s не доставлена: %s", lead.id, exc)
            await self.repo.mark_failed(lead.id, str(exc))
            return False
        await self.repo.mark_notified(lead.id)
        return True

    async def resend_pending(self) -> int:
        """Досылает всё, что не ушло раньше. Останавливается на первой ошибке, чтобы не долбить Telegram."""
        sent = 0
        for lead in await self.repo.pending():
            if not await self.deliver(lead):
                break
            sent += 1
        return sent

    async def run_forever(self, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                sent = await self.resend_pending()
            except Exception:
                # фоновая задача не должна умирать из-за одной ошибки базы или сети
                log.exception("Ошибка при повторной отправке")
                continue
            if sent:
                log.info("Дослано заявок: %s", sent)


def csv_safe(value: object) -> str:
    """Excel выполняет ячейки, начинающиеся с = + - @, как формулы. Данные с формы экранируем."""
    text = "" if value is None else str(value)
    if text[:1] in ("=", "+", "-", "@") and not (text.startswith("+7") and text[1:].isdigit()):
        return "'" + text
    return text


CSV_HEADER = ["№", "Дата", "Имя", "Телефон", "Email", "Сообщение", "Источник", "UTM", "Уведомление"]


def leads_to_csv(leads: list[Lead], tz: ZoneInfo) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(CSV_HEADER)
    for lead in leads:
        utm = "/".join(v for v in (lead.utm_source, lead.utm_medium, lead.utm_campaign) if v)
        writer.writerow(
            [
                lead.id,
                lead.local_time(tz).strftime("%d.%m.%Y %H:%M"),
                csv_safe(lead.name),
                lead.phone,
                csv_safe(lead.email),
                csv_safe(lead.message),
                csv_safe(lead.source),
                csv_safe(utm),
                "доставлено" if lead.notified else "ожидает",
            ]
        )
    return buf.getvalue().encode("utf-8-sig")
