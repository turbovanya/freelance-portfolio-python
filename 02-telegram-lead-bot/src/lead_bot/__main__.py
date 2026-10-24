import asyncio
import logging

from aiogram.exceptions import TelegramAPIError

from .app import create_bot, create_dispatcher, set_commands
from .config import Settings
from .db import create_engine, init_db

log = logging.getLogger("lead_bot")


async def run() -> None:
    settings = Settings()
    engine = create_engine(settings.database_url)
    await init_db(engine)
    bot = create_bot(settings)
    dp = create_dispatcher(settings, engine)
    try:
        await set_commands(bot, settings)
    except TelegramAPIError as exc:
        log.warning("Не удалось установить меню команд: %s", exc)
    if not settings.admin_ids:
        log.warning("ADMIN_IDS не задан: заявки будут сохраняться, но уведомлять будет некого")
    log.info("Бот запущен")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
