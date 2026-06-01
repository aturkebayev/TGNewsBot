import asyncio
import os
import sys

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from loguru import logger

from db.database import init_db, close_db
from bot.handlers import router
from scheduler.jobs import setup_scheduler
from parser.rss import poll_all_sources

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE  = os.getenv("TIMEZONE", "Asia/Almaty")
DATA_DIR  = os.getenv("DATA_DIR", ".")

# logs go into DATA_DIR so they land on the persistent volume when hosted
LOG_FILE = os.path.join(DATA_DIR, "logs", "bot.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logger.remove()
logger.add(
    sys.stdout, level=LOG_LEVEL, colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
)
logger.add(LOG_FILE, level=LOG_LEVEL, rotation="10 MB",
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

    logger.info("Initial RSS poll…")
    asyncio.create_task(poll_all_sources())

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
