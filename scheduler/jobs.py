import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from db.database import (
    get_users_by_digest_time,
    get_subscriptions, get_recent_articles,
    get_unsent_breaking, mark_breaking_sent,
    get_users_subscribed_to, mark_articles_viewed,
    get_all_subscribed_users, get_disabled_sources,
)
from bot.formatter import format_article, format_digest_compact
from parser.rss import poll_all_sources, ALL_RSS_SOURCES

_bot = None
_tz: ZoneInfo = ZoneInfo("Asia/Almaty")


async def _get_enabled_sources(user_id: int) -> list[str] | None:
    """Returns list of enabled sources, or None if all enabled."""
    disabled = await get_disabled_sources(user_id)
    if not disabled:
        return None
    all_src = list(ALL_RSS_SOURCES.keys())
    return [s for s in all_src if s not in disabled]


def setup_scheduler(bot, timezone: str = "Asia/Almaty") -> AsyncIOScheduler:
    global _bot, _tz
    _bot = bot
    _tz = ZoneInfo(timezone)

    scheduler = AsyncIOScheduler(timezone=timezone)
    # RSS poll every 30 min; immediately triggers breaking-news check after each poll
    scheduler.add_job(
        job_rss_poll, "interval", minutes=30, id="rss_poll",
        max_instances=1, coalesce=True, misfire_grace_time=600,
    )
    # Breaking-news safety net: catches any unsent articles the poll may have missed
    scheduler.add_job(
        job_breaking_check, "interval", minutes=30, id="breaking_check",
        max_instances=1, coalesce=True, misfire_grace_time=600,
    )
    # Digest: once per hour, headlines-only, importance 5–8
    scheduler.add_job(
        job_digest_send, "cron", minute=0, id="digest_send",
        max_instances=1, coalesce=True, misfire_grace_time=300,
    )
    return scheduler


# ── RSS poll ──────────────────────────────────────────────────────────────────

async def job_rss_poll() -> None:
    logger.info("Scheduler: RSS poll started")
    try:
        count = await poll_all_sources()
        logger.info(f"Scheduler: RSS poll finished — {count} new articles")
        if count > 0:
            # Send breaking news immediately after receiving new articles
            await job_breaking_check()
    except Exception as exc:
        logger.error(f"Scheduler: RSS poll error: {exc}")


# ── Breaking news (immediate, full article) ───────────────────────────────────

async def job_breaking_check() -> None:
    """Send any unsent is_breaking=1 articles immediately to subscribed users."""
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
            thr = user["alert_threshold"] if user["alert_threshold"] is not None else 8
            if thr == 0:
                continue
            try:
                await _bot.send_message(
                    user["chat_id"], text,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True,
                )
                await mark_articles_viewed(user["chat_id"], [art["id"]])
                await asyncio.sleep(0.05)
            except Exception as exc:
                logger.warning(f"Breaking send failed to {user['chat_id']}: {exc}")
        await mark_breaking_sent(art["id"])


# ── Digest (scheduled, headlines only, importance 5–8) ────────────────────────

async def job_digest_send() -> None:
    """Send a compact headline digest at the user's chosen time (Almaty TZ).

    Only includes articles with importance 5–8.
    Breaking articles (importance 9–10) are already delivered immediately
    via job_breaking_check, so they are excluded from the digest.
    """
    if _bot is None:
        return
    now_str = datetime.now(_tz).strftime("%H:%M")
    users = await get_users_by_digest_time(now_str)
    if not users:
        return
    logger.info(f"Scheduler: digest for {len(users)} user(s) at {now_str} ALT")
    for user in users:
        uid = user["chat_id"]
        subs = await get_subscriptions(uid)
        if not subs:
            continue
        enabled_sources = await _get_enabled_sources(uid)
        topics = subs if "all" not in subs else ["all"]
        for topic in topics:
            articles = await get_recent_articles(
                topic, hours=24, limit=7,
                exclude_user_id=uid,
                min_importance=5,
                max_importance=8,   # exclude breaking (9+), already sent immediately
                enabled_sources=enabled_sources,
            )
            if not articles:
                continue
            text = format_digest_compact(topic, articles)
            try:
                await _bot.send_message(
                    uid, text,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True,
                )
                sent_ids = [art["id"] for art in articles]
                await mark_articles_viewed(uid, sent_ids)
                await asyncio.sleep(0.05)
            except Exception as exc:
                logger.warning(f"Digest send failed to {uid}: {exc}")
