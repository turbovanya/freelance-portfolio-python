"""Команды и кнопки для администраторов. Обычные пользователи их не видят и не могут вызвать."""

import logging
from datetime import datetime

from aiogram import Bot, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, Filter
from aiogram.types import BufferedInputFile, CallbackQuery, Message, TelegramObject

from .. import keyboards, texts
from ..config import Settings
from ..db import Lead, LeadRepository, LeadStatus
from ..services import leads_to_csv

log = logging.getLogger(__name__)


class IsAdmin(Filter):
    async def __call__(self, event: TelegramObject, settings: Settings) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id in settings.admin_ids)


async def admin_help(message: Message) -> None:
    await message.answer(texts.ADMIN_HELP)


async def stats(message: Message, repo: LeadRepository) -> None:
    await message.answer(texts.stats_text(await repo.stats()))


async def _send_list(message: Message, leads: list[Lead], settings: Settings, empty: str) -> None:
    if not leads:
        await message.answer(empty)
        return
    for lead in reversed(leads):
        await message.answer(
            texts.admin_card(lead, settings.tz), reply_markup=keyboards.lead_actions(lead.id, lead.status)
        )


async def last_leads(message: Message, repo: LeadRepository, settings: Settings) -> None:
    await _send_list(message, await repo.recent(5), settings, "Заявок пока нет.")


async def new_leads(message: Message, repo: LeadRepository, settings: Settings) -> None:
    await _send_list(message, await repo.recent(10, LeadStatus.NEW), settings, "Необработанных заявок нет 👍")


async def export(message: Message, repo: LeadRepository, settings: Settings) -> None:
    leads = await repo.all()
    filename = f"leads_{datetime.now(settings.tz):%Y-%m-%d}.csv"
    await message.answer_document(
        BufferedInputFile(leads_to_csv(leads, settings.tz), filename=filename),
        caption=f"Заявок в файле: {len(leads)}",
    )


async def change_status(
    query: CallbackQuery,
    callback_data: keyboards.LeadAction,
    bot: Bot,
    repo: LeadRepository,
    settings: Settings,
) -> None:
    lead = await repo.set_status(callback_data.id, callback_data.status, query.from_user.id)
    if lead is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    await query.answer(f"Статус: {lead.status.label}")
    if query.message is not None and isinstance(query.message, Message):
        await query.message.edit_text(
            texts.admin_card(lead, settings.tz), reply_markup=keyboards.lead_actions(lead.id, lead.status)
        )

    client_text = texts.STATUS_FOR_CLIENT.get(lead.status.value)
    if client_text:
        try:
            await bot.send_message(lead.user_id, client_text.format(id=lead.id))
        except TelegramAPIError:
            log.warning("Не удалось сообщить клиенту %s о статусе заявки №%s", lead.user_id, lead.id)


def make_router() -> Router:
    router = Router(name="admin")
    router.message.filter(IsAdmin())
    router.callback_query.filter(IsAdmin())
    router.message.register(admin_help, Command("help", "admin"))
    router.message.register(stats, Command("stats"))
    router.message.register(last_leads, Command("leads"))
    router.message.register(new_leads, Command("new"))
    router.message.register(export, Command("export"))
    router.callback_query.register(change_status, keyboards.LeadAction.filter())
    return router
