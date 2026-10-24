"""Форма заявки: имя -> телефон -> комментарий. Состояние хранится в FSM aiogram."""

import logging
from datetime import timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from .. import keyboards, texts
from ..config import Settings
from ..db import LeadRepository, utcnow
from ..services import clean_comment, normalize_phone, validate_name

log = logging.getLogger(__name__)


class LeadForm(StatesGroup):
    name = State()
    phone = State()
    comment = State()


async def start_form(message: Message, state: FSMContext, repo: LeadRepository, settings: Settings) -> None:
    assert message.from_user
    recent = await repo.count_by_user_since(message.from_user.id, utcnow() - timedelta(days=1))
    if recent >= settings.max_leads_per_day:
        await message.answer(texts.TOO_MANY_LEADS, reply_markup=keyboards.main_menu())
        return
    await state.set_state(LeadForm.name)
    await message.answer(texts.ASK_NAME, reply_markup=keyboards.cancel())


async def got_name(message: Message, state: FSMContext) -> None:
    name = validate_name(message.text or "")
    if not name:
        await message.answer(texts.BAD_NAME)
        return
    await state.update_data(name=name)
    await state.set_state(LeadForm.phone)
    await message.answer(texts.ASK_PHONE.format(name=name), reply_markup=keyboards.phone())


async def got_phone(message: Message, state: FSMContext) -> None:
    raw = message.contact.phone_number if message.contact else (message.text or "")
    phone = normalize_phone(raw)
    if not phone:
        await message.answer(texts.BAD_PHONE)
        return
    await state.update_data(phone=phone)
    await state.set_state(LeadForm.comment)
    await message.answer(texts.ASK_COMMENT, reply_markup=keyboards.comment())


async def got_comment(
    message: Message, state: FSMContext, bot: Bot, repo: LeadRepository, settings: Settings
) -> None:
    assert message.from_user
    comment = "" if message.text == texts.BTN_SKIP else clean_comment(message.text or "")
    data = await state.get_data()
    await state.clear()

    # сначала сохраняем, потом уведомляем: если Telegram не доставит сообщение, заявка останется в базе
    lead = await repo.add(
        user_id=message.from_user.id,
        username=message.from_user.username,
        name=data["name"],
        phone=data["phone"],
        comment=comment,
    )
    await message.answer(texts.LEAD_ACCEPTED.format(id=lead.id), reply_markup=keyboards.main_menu())

    card = texts.admin_card(lead, settings.tz)
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, card, reply_markup=keyboards.lead_actions(lead.id, lead.status))
        except TelegramAPIError:
            # обычно админ ещё не нажал /start у бота
            log.exception("Заявка №%s не доставлена админу %s", lead.id, admin_id)


def make_router() -> Router:
    router = Router(name="lead_form")
    router.message.register(start_form, F.text == texts.BTN_LEAD)
    router.message.register(got_name, LeadForm.name)
    router.message.register(got_phone, LeadForm.phone)
    router.message.register(got_comment, LeadForm.comment)
    return router
