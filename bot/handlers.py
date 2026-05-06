import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from db.database import (
    upsert_user, get_user, set_digest_time,
    get_subscriptions, add_subscription, remove_subscription,
    get_recent_articles,
)
from bot.keyboards import topics_keyboard, settings_keyboard, main_menu
from bot.formatter import format_article, format_digest_header
from parser.rss import poll_all_sources

router = Router()

WELCOME = (
    "👋 Привет! Я бот мировых новостей на русском языке.\n\n"
    "Выбери темы и получай дайджест в удобное время.\n\n"
    "Используй кнопки меню внизу экрана."
)

HELP_TEXT = (
    "📖 Команды бота:\n\n"
    "📰 Новости — свежий дайджест\n"
    "🔄 Обновить — загрузить RSS прямо сейчас\n"
    "🗂 Темы — выбрать категории\n"
    "⚙️ Настройки — время дайджеста (МСК)\n"
    "❓ Помощь — эта справка\n\n"
    "Или слэш-команды: /news /topics /settings /fetch /help"
)


# ── helpers ───────────────────────────────────────────────────────────────────

async def _send_news(message: Message) -> None:
    subs = await get_subscriptions(message.chat.id)
    if not subs:
        await message.answer(
            "Темы не выбраны. Нажми 🗂 Темы чтобы подписаться.",
            reply_markup=main_menu(),
        )
        return

    topics = subs if "all" not in subs else ["all"]
    all_articles: list = []
    for topic in topics:
        articles = await get_recent_articles(topic, hours=24, limit=5)
        if not articles:
            continue
        header = format_digest_header(topic, len(articles))
        await message.answer(header, parse_mode="MarkdownV2")
        for i, art in enumerate(articles):
            is_last = (topic == topics[-1]) and (i == len(articles) - 1)
            try:
                await message.answer(
                    format_article(art),
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True,
                    reply_markup=main_menu() if is_last else None,
                )
                await asyncio.sleep(0.05)
            except Exception:
                pass
        all_articles.extend(articles)

    if not all_articles:
        await message.answer(
            "Нет свежих новостей за последние 24 часа. Нажми 🔄 Обновить.",
            reply_markup=main_menu(),
        )


async def _do_fetch(message: Message) -> None:
    # edit_text поддерживает только InlineKeyboardMarkup,
    # поэтому сначала редактируем текст, потом шлём новое сообщение с меню
    msg = await message.answer("⏳ Загружаю новости, подожди…")
    try:
        count = await poll_all_sources()
        await msg.edit_text(f"✅ Готово! Загружено новых статей: {count}")
    except Exception as exc:
        await msg.edit_text(f"❌ Ошибка: {exc}")
    await message.answer("Выбери действие:", reply_markup=main_menu())


# ── commands ──────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await upsert_user(message.chat.id)
    subs = await get_subscriptions(message.chat.id)
    await message.answer(WELCOME, reply_markup=main_menu())
    await message.answer("Выбери темы для подписки:", reply_markup=topics_keyboard(subs))


@router.message(Command("topics"))
async def cmd_topics(message: Message) -> None:
    await upsert_user(message.chat.id)
    subs = await get_subscriptions(message.chat.id)
    await message.answer("Выбери темы:", reply_markup=topics_keyboard(subs))


@router.message(Command("news"))
async def cmd_news(message: Message) -> None:
    await upsert_user(message.chat.id)
    await _send_news(message)


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
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(Command("fetch"))
async def cmd_fetch(message: Message) -> None:
    await upsert_user(message.chat.id)
    await _do_fetch(message)


# ── reply keyboard buttons ────────────────────────────────────────────────────

@router.message(F.text == "📰 Новости")
async def btn_news(message: Message) -> None:
    await upsert_user(message.chat.id)
    await _send_news(message)


@router.message(F.text == "🔄 Обновить")
async def btn_fetch(message: Message) -> None:
    await upsert_user(message.chat.id)
    await _do_fetch(message)


@router.message(F.text == "🗂 Темы")
async def btn_topics(message: Message) -> None:
    await upsert_user(message.chat.id)
    subs = await get_subscriptions(message.chat.id)
    await message.answer("Выбери темы:", reply_markup=topics_keyboard(subs))


@router.message(F.text == "⚙️ Настройки")
async def btn_settings(message: Message) -> None:
    await upsert_user(message.chat.id)
    user = await get_user(message.chat.id)
    current = user["digest_time"] if user else "09:00"
    await message.answer(
        "⏰ Выбери время ежедневного дайджеста (МСК):",
        reply_markup=settings_keyboard(current),
    )


@router.message(F.text == "❓ Помощь")
async def btn_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


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
        await call.message.edit_text("⚠️ Нет активных подписок. Нажми 🗂 Темы")
    await call.answer("Сохранено!")


@router.callback_query(F.data.startswith("digest_time:"))
async def cb_digest_time(call: CallbackQuery) -> None:
    time_str = call.data.split(":", 1)[1]
    await set_digest_time(call.from_user.id, time_str)
    await call.message.edit_reply_markup(reply_markup=settings_keyboard(time_str))
    await call.answer(f"Время дайджеста: {time_str} МСК")
