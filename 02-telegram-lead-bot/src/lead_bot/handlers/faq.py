from aiogram import F, Router
from aiogram.types import Message

from .. import keyboards, texts
from ..services import Faq


async def topics(message: Message, faq: Faq) -> None:
    lines = "\n".join(f"• {item.question}" for item in faq.items)
    await message.answer(texts.FAQ_INTRO.format(topics=lines))


async def unknown_command(message: Message) -> None:
    await message.answer(texts.UNKNOWN_COMMAND, reply_markup=keyboards.main_menu())


async def free_text(message: Message, faq: Faq) -> None:
    item = faq.find(message.text or "")
    if item:
        await message.answer(item.answer)
    else:
        await message.answer(texts.FAQ_NOT_FOUND, reply_markup=keyboards.main_menu())


def make_router() -> Router:
    router = Router(name="faq")
    router.message.register(topics, F.text == texts.BTN_FAQ)
    router.message.register(unknown_command, F.text.startswith("/"))
    router.message.register(free_text, F.text)
    return router
