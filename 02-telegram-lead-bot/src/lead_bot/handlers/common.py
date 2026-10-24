from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .. import keyboards, texts
from ..config import Settings


async def start(message: Message, state: FSMContext, settings: Settings) -> None:
    await state.clear()
    await message.answer(
        texts.START.format(business=escape(settings.business_name)), reply_markup=keyboards.main_menu()
    )


async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=keyboards.main_menu())


async def contacts(message: Message) -> None:
    await message.answer(texts.CONTACTS, reply_markup=keyboards.main_menu())


def make_router() -> Router:
    router = Router(name="common")
    router.message.register(start, CommandStart())
    router.message.register(cancel, Command("cancel"))
    router.message.register(cancel, F.text == texts.BTN_CANCEL)
    router.message.register(contacts, F.text == texts.BTN_CONTACTS)
    return router
