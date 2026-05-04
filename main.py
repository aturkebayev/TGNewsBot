import asyncio
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from loguru import logger

from db.database import init_db, close_db
from bot.handlers import router
from scheduler.jobs import setup_scheduler

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")

logger.remove()
logger.add(sys.stdout, level=LOG_LEVEL, colorize=True,
           format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}")
logger.add("logs/bot.log", level=LOG_LEVEL, rotation="10 MB",
           format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN is not set")
        sys.exit(1)

    await init_db()

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = setup_scheduler(bot, timezone=TIMEZONE)
    scheduler.start()
    logger.info("Scheduler started")

    try:
        logger.info("Bot starting (long-polling)")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Shutting down…")
        scheduler.shutdown(wait=False)
        await close_db()
        await bot.session.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
