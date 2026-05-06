import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from db.database import (
    get_all_users, get_users_by_digest_time,
    get_subscriptions, get_recent_articles,
    get_unsent_breaking, mark_breaking_sent,
    get_users_subscribed_to,
)
from bot.formatter import format_article, format_digest_header
from parser.rss import poll_all_sources

_bot = None


def setup_scheduler(bot, timezone: str = "Europe/Moscow") -> AsyncIOScheduler:
    global _bot
    _bot = bot

    scheduler = AsyncIOScheduler(timezone=timezone)
    scheduler.add_job(
        job_rss_poll, "interval", minutes=30, id="rss_poll",
        max_instances=1, coalesce=True, misfire_grace_time=600,
    )
    scheduler.add_job(
        job_breaking_check, "interval", minutes=30, id="breaking_check",
        max_instances=1, coalesce=True, misfire_grace_time=600,
    )
    scheduler.add_job(
        job_digest_send, "cron", minute=0, id="digest_send",
        max_instances=1, coalesce=True, misfire_grace_time=300,
    )
    return scheduler


async def job_rss_poll() -> None:
    logger.info("Scheduler: RSS poll started")
    try:
        count = await poll_all_sources()
        logger.info(f"Scheduler: RSS poll finished — {count} new articles")
    except Exception as exc:
        logger.error(f"Scheduler: RSS poll error: {exc}")


async def job_breaking_check() -> None:
    if _bot is None:
        return
    articles = await get_unsent_breaking()
    if not articles:
        return
    logger.info(f"Scheduler: {len(articles)} breaking article(s) to send")
    for art in articles:
        category = art["category"] or "other"
        users = await get_users_subscribed_to(category)
        text = format_article(art)
        for user in users:
            try:
                await _bot.send_message(
                    user["chat_id"], text,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(0.05)
            except Exception as exc:
                logger.warning(f"Breaking send failed to {user['chat_id']}: {exc}")
        await mark_breaking_sent(art["id"])


async def job_digest_send() -> None:
    if _bot is None:
        return
    now_msk = datetime.now().strftime("%H:%M")
    users = await get_users_by_digest_time(now_msk)
    if not users:
        return
    logger.info(f"Scheduler: digest for {len(users)} user(s) at {now_msk}")
    for user in users:
        subs = await get_subscriptions(user["chat_id"])
        if not subs:
            continue
        topics = subs if "all" not in subs else ["all"]
        for topic in topics:
            articles = await get_recent_articles(topic, hours=24, limit=5)
            if not articles:
                continue
            header = format_digest_header(topic, len(articles))
            try:
                await _bot.send_message(
                    user["chat_id"], header, parse_mode="MarkdownV2"
                )
            except Exception as exc:
                logger.warning(f"Digest header failed: {exc}")
                continue
            for art in articles:
                try:
                    await _bot.send_message(
                        user["chat_id"],
                        format_article(art),
                        parse_mode="MarkdownV2",
                        disable_web_page_preview=True,
                    )
                    await asyncio.sleep(0.05)
                except Exception as exc:
                    logger.warning(f"Digest article failed: {exc}")
