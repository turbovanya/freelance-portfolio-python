"""Сборка приложения. Используется и при запуске, и в тестах."""

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault, ErrorEvent
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from .config import Settings
from .db import LeadRepository
from .handlers import build_router
from .services import Faq

log = logging.getLogger(__name__)


def create_bot(settings: Settings) -> Bot:
    return Bot(settings.bot_token.get_secret_value(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(settings: Settings, engine: AsyncEngine) -> Dispatcher:
    # всё, что передано сюда, aiogram подставит в обработчики по имени аргумента
    dp = Dispatcher(
        settings=settings,
        repo=LeadRepository(async_sessionmaker(engine, expire_on_commit=False)),
        faq=Faq.load(settings.faq_path),
    )
    dp.include_router(build_router())

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Ошибка при обработке апдейта %s", event.update.update_id, exc_info=event.exception)
        return True

    return dp


async def set_commands(bot: Bot, settings: Settings) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="cancel", description="Отмена"),
        ],
        scope=BotCommandScopeDefault(),
    )
    admin_commands = [
        BotCommand(command="new", description="Необработанные заявки"),
        BotCommand(command="leads", description="Последние заявки"),
        BotCommand(command="stats", description="Статистика"),
        BotCommand(command="export", description="Выгрузка в CSV"),
    ]
    for admin_id in settings.admin_ids:
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
