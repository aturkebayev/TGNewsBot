import asyncio

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from db.database import (
    upsert_user, get_user, set_digest_time, set_alert_threshold,
    get_subscriptions, add_subscription, remove_subscription,
    get_recent_articles, mark_manually_read,
    get_disabled_sources, toggle_source,
)
from bot.keyboards import topics_keyboard, settings_keyboard, main_menu, sources_keyboard
from parser.rss import ALL_RSS_SOURCES
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
    "📰 Новости — свежий дайджест (только новые)\n"
    "🔄 Обновить — загрузить RSS прямо сейчас\n"
    "🗂 Темы — выбрать категории\n"
    "📡 Источники — включить/отключить источники\n"
    "⚙️ Настройки — время дайджеста и порог уведомлений\n"
    "❓ Помощь — эта справка\n\n"
    "Или слэш-команды: /news /topics /sources /settings /fetch /help"
)


# ── helpers ───────────────────────────────────────────────────────────────────

async def _get_enabled_sources(user_id: int) -> list[str] | None:
    """Returns list of enabled sources, or None if all enabled."""
    disabled = await get_disabled_sources(user_id)
    if not disabled:
        return None  # all sources enabled — no filter needed
    all_src = list(ALL_RSS_SOURCES.keys())
    return [s for s in all_src if s not in disabled]


async def _send_news(message: Message) -> None:
    user_id = message.chat.id
    subs = await get_subscriptions(user_id)
    if not subs:
        await message.answer(
            "Темы не выбраны. Нажми 🗂 Темы чтобы подписаться.",
            reply_markup=main_menu(),
        )
        return

    enabled_sources = await _get_enabled_sources(user_id)
    topics = subs if "all" not in subs else ["all"]
    sent_ids: list[int] = []

    for topic in topics:
        # manual_reads=True: exclude only articles THIS user has manually read before.
        # Articles received via push/digest (user_article_views) are NOT excluded,
        # so one user's push history never blocks another user from seeing the same news.
        articles = await get_recent_articles(
            topic, hours=24, limit=5,
            exclude_user_id=user_id,
            enabled_sources=enabled_sources,
            manual_reads=True,
        )
        if not articles:
            continue
        header = format_digest_header(topic, len(articles))
        await message.answer(header, parse_mode="MarkdownV2")
        for art in articles:
            try:
                await message.answer(
                    format_article(art),
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True,
                )
                sent_ids.append(art["id"])
                await asyncio.sleep(0.05)
            except Exception:
                pass

    # Track only what THIS user manually read — stored in user_manual_reads,
    # completely isolated from other users' read history.
    await mark_manually_read(user_id, sent_ids)

    if not sent_ids:
        await message.answer(
            "Нет новых новостей. Все свежие статьи уже показаны.\n"
            "Нажми 🔄 Обновить чтобы загрузить свежие.",
            reply_markup=main_menu(),
        )
    else:
        await message.answer("Всё прочитано ✅", reply_markup=main_menu())


async def _do_fetch(message: Message) -> None:
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
    current_time = user["digest_time"] if user else "09:00"
    current_thr = user["alert_threshold"] if user else 8
    await message.answer(
        "⚙️ Настройки:\n\n"
        "🕐 *Время дайджеста* — раз в сутки в выбранное время\n"
        "🔔 *Порог уведомлений* — при каком importance слать push прямо сейчас",
        parse_mode="Markdown",
        reply_markup=settings_keyboard(current_time, current_thr),
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
    current_time = user["digest_time"] if user else "09:00"
    current_thr = user["alert_threshold"] if user else 8
    await message.answer(
        "⚙️ Настройки:\n\n"
        "🕐 *Время дайджеста* — раз в сутки в выбранное время\n"
        "🔔 *Порог уведомлений* — при каком importance слать push прямо сейчас",
        parse_mode="Markdown",
        reply_markup=settings_keyboard(current_time, current_thr),
    )


@router.message(F.text == "❓ Помощь")
async def btn_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(Command("sources"))
@router.message(F.text == "📡 Источники")
async def cmd_sources(message: Message) -> None:
    await upsert_user(message.chat.id)
    disabled = await get_disabled_sources(message.chat.id)
    all_src = list(ALL_RSS_SOURCES.keys())
    await message.answer(
        "📡 *Источники новостей*\n\nВсе источники включены по умолчанию\\.\nНажми на источник чтобы включить/отключить\\.",
        parse_mode="MarkdownV2",
        reply_markup=sources_keyboard(all_src, disabled),
    )


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


@router.callback_query(F.data.startswith("src:"))
async def cb_source(call: CallbackQuery) -> None:
    source = call.data.split(":", 1)[1]
    all_src = list(ALL_RSS_SOURCES.keys())
    if source == "save":
        disabled = await get_disabled_sources(call.from_user.id)
        enabled_count = len(all_src) - len(disabled)
        await call.message.edit_text(
            f"✅ Сохранено: включено *{enabled_count}* из *{len(all_src)}* источников",
            parse_mode="MarkdownV2",
        )
        await call.answer("Сохранено!")
        return
    if source not in all_src:
        await call.answer("Неизвестный источник")
        return
    now_enabled = await toggle_source(call.from_user.id, source)
    disabled = await get_disabled_sources(call.from_user.id)
    await call.message.edit_reply_markup(reply_markup=sources_keyboard(all_src, disabled))
    await call.answer(f"{'✅ Включён' if now_enabled else '❌ Отключён'}: {source}")


@router.callback_query(F.data.startswith("digest_time:"))
async def cb_digest_time(call: CallbackQuery) -> None:
    time_str = call.data.split(":", 1)[1]
    await set_digest_time(call.from_user.id, time_str)
    user = await get_user(call.from_user.id)
    current_thr = user["alert_threshold"] if user else 8
    await call.message.edit_reply_markup(
        reply_markup=settings_keyboard(time_str, current_thr)
    )
    await call.answer(f"✅ Дайджест в {time_str} МСК")


@router.callback_query(F.data.startswith("alert_threshold:"))
async def cb_alert_threshold(call: CallbackQuery) -> None:
    threshold = int(call.data.split(":", 1)[1])
    await set_alert_threshold(call.from_user.id, threshold)
    user = await get_user(call.from_user.id)
    current_time = user["digest_time"] if user else "09:00"
    await call.message.edit_reply_markup(
        reply_markup=settings_keyboard(current_time, threshold)
    )
    labels = {7: "Все заметные (7+)", 8: "Важные (8+)", 9: "Только срочные (9+)", 0: "отключены"}
    await call.answer(f"🔔 Уведомления: {labels.get(threshold, str(threshold))}")
