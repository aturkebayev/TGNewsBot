import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from db.database import (
    upsert_user, get_user, set_digest_time,
    get_subscriptions, add_subscription, remove_subscription,
    get_recent_articles,
)
from parser.rss import poll_all_sources
from bot.keyboards import topics_keyboard, settings_keyboard
from bot.formatter import format_article, format_digest_header

router = Router()

WELCOME = (
    "👋 *Привет\\!* Я бот мировых новостей на русском языке\\.\n\n"
    "Выбери темы, которые тебя интересуют, и получай дайджест в удобное время\\.\n\n"
    "Команды:\n"
    "/topics — выбрать темы\n"
    "/news — получить новости сейчас\n"
    "/settings — настроить время дайджеста\n"
    "/help — помощь"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await upsert_user(message.chat.id)
    subs = await get_subscriptions(message.chat.id)
    await message.answer(WELCOME, parse_mode="MarkdownV2")
    await message.answer(
        "Выбери темы для подписки:",
        reply_markup=topics_keyboard(subs),
    )


@router.message(Command("topics"))
async def cmd_topics(message: Message) -> None:
    await upsert_user(message.chat.id)
    subs = await get_subscriptions(message.chat.id)
    await message.answer("Выбери темы:", reply_markup=topics_keyboard(subs))


@router.message(Command("news"))
async def cmd_news(message: Message) -> None:
    await upsert_user(message.chat.id)
    subs = await get_subscriptions(message.chat.id)
    if not subs:
        await message.answer("Ты ещё не выбрал(а) темы. Используй /topics")
        return

    topics = subs if "all" not in subs else ["all"]
    sent = False
    for topic in topics:
        articles = await get_recent_articles(topic, hours=24, limit=5)
        if not articles:
            continue
        header = format_digest_header(topic, len(articles))
        await message.answer(header, parse_mode="MarkdownV2")
        for art in articles:
            try:
                await message.answer(
                    format_article(art), parse_mode="MarkdownV2",
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(0.05)
            except Exception:
                pass
        sent = True

    if not sent:
        await message.answer("Нет свежих новостей за последние 24 часа.")


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    await upsert_user(message.chat.id)
    user = await get_user(message.chat.id)
    current = user["digest_time"] if user else "09:00"
    await message.answer(
        "⏰ Выбери время ежедневного дайджеста (МСК):",
        reply_markup=settings_keyboard(current),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    text = (
        "📖 *Команды бота:*\n\n"
        "/start — начать работу\n"
        "/topics — выбрать темы новостей\n"
        "/news — получить свежие новости\n"
        "/fetch — загрузить новости прямо сейчас\n"
        "/settings — время дайджеста\n"
        "/help — эта справка"
    )
    await message.answer(text, parse_mode="MarkdownV2")


@router.message(Command("fetch"))
async def cmd_fetch(message: Message) -> None:
    await upsert_user(message.chat.id)
    msg = await message.answer("⏳ Загружаю новости, подожди…")
    try:
        count = await poll_all_sources()
        await msg.edit_text(f"✅ Готово\\! Загружено новых статей: *{count}*", parse_mode="MarkdownV2")
    except Exception as exc:
        await msg.edit_text(f"❌ Ошибка: {exc}")


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("topic:"))
async def cb_topic(call: CallbackQuery) -> None:
    topic = call.data.split(":", 1)[1]
    subs = await get_subscriptions(call.from_user.id)
    if topic in subs:
        await remove_subscription(call.from_user.id, topic)
    else:
        await add_subscription(call.from_user.id, topic)
    subs = await get_subscriptions(call.from_user.id)
    await call.message.edit_reply_markup(reply_markup=topics_keyboard(subs))
    await call.answer()


@router.callback_query(F.data == "topics:save")
async def cb_topics_save(call: CallbackQuery) -> None:
    subs = await get_subscriptions(call.from_user.id)
    if subs:
        await call.message.edit_text(f"✅ Сохранено: {', '.join(subs)}")
    else:
        await call.message.edit_text("⚠️ Нет активных подписок. Используй /topics")
    await call.answer("Сохранено!")


@router.callback_query(F.data.startswith("digest_time:"))
async def cb_digest_time(call: CallbackQuery) -> None:
    time_str = call.data.split(":", 1)[1]
    await set_digest_time(call.from_user.id, time_str)
    await call.message.edit_reply_markup(reply_markup=settings_keyboard(time_str))
    await call.answer(f"Время дайджеста: {time_str} МСК")
