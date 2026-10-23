import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import Config
from bot.db import LeadStorage
from bot.faq import load_faq
from bot.handlers import build_router


async def main():
    logging.basicConfig(level=logging.INFO)
    config = Config.from_env()
    storage = LeadStorage(config.db_path)
    dp = Dispatcher()
    dp.include_router(build_router(config, storage, load_faq(config.faq_path)))
    bot = Bot(config.token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
