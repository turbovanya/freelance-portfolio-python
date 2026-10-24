"""Прогон бота без Telegram: апдейты подаются в Dispatcher, исходящие запросы к API перехватываются.

Используется в тестах и в scripts/render_demo.py.
"""

from dataclasses import dataclass, field
from datetime import datetime
from itertools import count
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageText,
    SendDocument,
    SendMessage,
    TelegramMethod,
)
from aiogram.types import CallbackQuery, Chat, Contact, Message, Update, User
from sqlalchemy.ext.asyncio import AsyncEngine

from lead_bot.app import create_dispatcher
from lead_bot.config import Settings
from lead_bot.db import create_engine, init_db

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Outgoing:
    """Сообщение, которое бот отправил (или отредактировал)."""

    chat_id: int
    message_id: int
    text: str
    reply_markup: Any = None
    document: str | None = None
    edited: bool = False


@dataclass
class FakeTelegram:
    messages: list[Outgoing] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    fail_for: set[int] = field(default_factory=set)
    _ids: Any = field(default_factory=lambda: count(1000))

    async def __call__(self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None) -> Any:
        if isinstance(method, (SendMessage, SendDocument)) and method.chat_id in self.fail_for:
            from aiogram.exceptions import TelegramForbiddenError

            raise TelegramForbiddenError(method=method, message="Forbidden: bot was blocked by the user")
        if isinstance(method, SendMessage):
            out = Outgoing(int(method.chat_id), next(self._ids), method.text, method.reply_markup)
            self.messages.append(out)
            return self._as_message(out)
        if isinstance(method, SendDocument):
            name = getattr(method.document, "filename", "file")
            out = Outgoing(int(method.chat_id), next(self._ids), method.caption or "", document=name)
            out.raw = method.document.data  # type: ignore[attr-defined]
            self.messages.append(out)
            return self._as_message(out)
        if isinstance(method, EditMessageText):
            out = Outgoing(
                int(method.chat_id or 0),
                int(method.message_id or 0),
                method.text,
                method.reply_markup,
                edited=True,
            )
            self.messages.append(out)
            return self._as_message(out)
        if isinstance(method, AnswerCallbackQuery):
            self.alerts.append(method.text or "")
            return True
        return True

    @staticmethod
    def _as_message(out: Outgoing) -> Message:
        return Message(
            message_id=out.message_id,
            date=datetime.now(),
            chat=Chat(id=out.chat_id, type="private"),
            text=out.text or None,
        )

    def texts(self, chat_id: int) -> list[str]:
        return [m.text for m in self.messages if m.chat_id == chat_id]

    def last(self, chat_id: int) -> Outgoing:
        return [m for m in self.messages if m.chat_id == chat_id][-1]


class BotHarness:
    def __init__(self, settings: Settings, engine: AsyncEngine) -> None:
        self.settings = settings
        self.engine = engine
        self.dp: Dispatcher = create_dispatcher(settings, engine)
        self.bot = Bot("42:TEST", default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.tg = FakeTelegram()
        self.bot.session.make_request = self.tg  # type: ignore[method-assign]
        self._update_ids = count(1)
        self.incoming: list[tuple[int, str]] = []

    @classmethod
    async def create(cls, **overrides: Any) -> "BotHarness":
        values: dict[str, Any] = {
            "bot_token": "42:TEST",
            "admin_ids": [100],
            "database_url": "sqlite+aiosqlite:///:memory:",
            "faq_path": ROOT / "faq.json",
            "business_name": "Студия «Пример»",
        }
        values.update(overrides)
        settings = Settings(_env_file=None, **values)  # type: ignore[call-arg]
        engine = create_engine(settings.database_url)
        await init_db(engine)
        return cls(settings, engine)

    @property
    def repo(self) -> Any:
        return self.dp["repo"]

    def _user(self, user_id: int, username: str | None, name: str) -> User:
        return User(id=user_id, is_bot=False, first_name=name, username=username)

    async def say(
        self, text: str | None, user_id: int = 7, username: str | None = "client", contact: str | None = None
    ) -> None:
        uid = next(self._update_ids)
        self.incoming.append((user_id, text or f"📱 {contact}"))
        msg = Message(
            message_id=uid,
            date=datetime.now(),
            chat=Chat(id=user_id, type="private"),
            from_user=self._user(user_id, username, "Клиент"),
            text=text,
            contact=Contact(phone_number=contact, first_name="Клиент", user_id=user_id) if contact else None,
        )
        await self.dp.feed_update(self.bot, Update(update_id=uid, message=msg))

    async def press(self, message: Outgoing, button_text: str, user_id: int = 100) -> None:
        button = next(b for row in message.reply_markup.inline_keyboard for b in row if b.text == button_text)
        uid = next(self._update_ids)
        query = CallbackQuery(
            id=str(uid),
            from_user=self._user(user_id, "manager", "Менеджер"),
            chat_instance="1",
            data=button.callback_data,
            message=Message(
                message_id=message.message_id,
                date=datetime.now(),
                chat=Chat(id=message.chat_id, type="private"),
                text=message.text,
            ),
        )
        await self.dp.feed_update(self.bot, Update(update_id=uid, callback_query=query))

    async def close(self) -> None:
        await self.bot.session.close()
        await self.engine.dispose()
