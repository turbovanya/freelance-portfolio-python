"""Полный диалог бота через Dispatcher.feed_update с подменой отправки сообщений — без токена и сети."""
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.methods import SendMessage, TelegramMethod
from aiogram.types import Chat, Message, Update, User

from bot.config import Config
from bot.db import LeadStorage
from bot.faq import load_faq
from bot.handlers import BTN_LEAD, build_router

ADMIN = 42


class Recorder:
    """Подмена Bot.session.make_request: запоминает все исходящие вызовы Telegram API."""

    def __init__(self):
        self.calls = []

    async def __call__(self, bot, method: TelegramMethod, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(message_id=1, date=datetime.now(), chat=Chat(id=method.chat_id, type="private"), text=method.text)
        return True


@pytest.fixture
def env():
    storage = LeadStorage(":memory:")
    config = Config(token="1:test", admin_ids=[ADMIN], business_name="Тест")
    dp = Dispatcher()
    dp.include_router(build_router(config, storage, load_faq("faq.json")))
    bot = Bot("1:test")
    rec = Recorder()
    bot.session.make_request = rec
    return dp, bot, storage, rec


_update_id = 0


async def say(dp, bot, text, user_id=7, username="client"):
    global _update_id
    _update_id += 1
    user = User(id=user_id, is_bot=False, first_name="C", username=username)
    msg = Message(message_id=_update_id, date=datetime.now(), chat=Chat(id=user_id, type="private"), from_user=user, text=text)
    await dp.feed_update(bot, Update(update_id=_update_id, message=msg))


def sent_texts(rec, chat_id=None):
    return [c.text for c in rec.calls if isinstance(c, SendMessage) and (chat_id is None or c.chat_id == chat_id)]


async def test_full_lead_flow_notifies_admin(env):
    dp, bot, storage, rec = env
    await say(dp, bot, "/start")
    await say(dp, bot, BTN_LEAD)
    await say(dp, bot, "Иван")
    await say(dp, bot, "8 (912) 345-67-89")
    await say(dp, bot, "Нужен парсер")
    leads = storage.recent()
    assert len(leads) == 1
    assert (leads[0]["name"], leads[0]["phone"], leads[0]["comment"]) == ("Иван", "+79123456789", "Нужен парсер")
    admin_msgs = sent_texts(rec, ADMIN)
    assert len(admin_msgs) == 1 and "Новая заявка №1" in admin_msgs[0] and "@client" in admin_msgs[0]
    assert "Заявка №1 принята" in sent_texts(rec, 7)[-1]


async def test_invalid_input_is_rejected_and_form_continues(env):
    dp, bot, storage, rec = env
    await say(dp, bot, BTN_LEAD)
    await say(dp, bot, "12345")        # имя с цифрами
    await say(dp, bot, "Мария")
    await say(dp, bot, "не телефон")   # плохой номер
    assert storage.stats()["total"] == 0
    assert "российский номер" in sent_texts(rec, 7)[-1]
    await say(dp, bot, "+7 999 000 11 22")
    await say(dp, bot, "-")
    assert storage.recent()[0]["comment"] == ""


async def test_cancel_resets_form(env):
    dp, bot, storage, rec = env
    await say(dp, bot, BTN_LEAD)
    await say(dp, bot, "Отмена")
    await say(dp, bot, "Иван")  # уже не в форме -> обычный текст, заявки быть не должно
    assert storage.stats()["total"] == 0


async def test_faq_answer_and_fallback(env):
    dp, bot, storage, rec = env
    await say(dp, bot, "а какая у вас стоимость?")
    assert "рассчитаем" in sent_texts(rec, 7)[-1]
    await say(dp, bot, "ывапывап")
    assert "Оставить заявку" in sent_texts(rec, 7)[-1]


async def test_admin_commands_protected(env):
    dp, bot, storage, rec = env
    storage.add(1, "a", "Иван", "+79123456789", "")
    await say(dp, bot, "/stats", user_id=7)       # не админ — тишина
    assert sent_texts(rec, 7) == []
    await say(dp, bot, "/stats", user_id=ADMIN)
    assert "Заявок всего: 1" in sent_texts(rec, ADMIN)[-1]
