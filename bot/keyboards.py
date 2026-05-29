from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)

TOPICS = ["politics", "tech", "sport", "economy", "science", "all"]

TOPIC_LABELS = {
    "politics": "🌍 Политика",
    "tech":     "💻 Технологии",
    "sport":    "⚽ Спорт",
    "economy":  "💰 Экономика",
    "science":  "🔬 Наука",
    "all":      "📰 Все темы",
}

DIGEST_TIMES = ["09:00", "14:00", "19:00"]

ALERT_THRESHOLDS = {
    7: "🔔 Все заметные (7+)",
    8: "🔔 Важные (8+)",
    9: "🚨 Только срочные (9+)",
    0: "🔕 Отключить",
}


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📰 Новости"),   KeyboardButton(text="🔄 Обновить")],
            [KeyboardButton(text="🗂 Темы"),       KeyboardButton(text="📡 Источники")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


def sources_keyboard(all_sources: list[str], disabled: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for source in all_sources:
        enabled = source not in disabled
        buttons.append([InlineKeyboardButton(
            text=f"{'✅' if enabled else '❌'} {source}",
            callback_data=f"src:{source}",
        )])
    buttons.append([InlineKeyboardButton(text="💾 Сохранить", callback_data="src:save")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def topics_keyboard(active: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for topic in TOPICS:
        label = TOPIC_LABELS[topic]
        checked = "✅ " if topic in active else ""
        buttons.append(
            [InlineKeyboardButton(
                text=f"{checked}{label}",
                callback_data=f"topic:{topic}",
            )]
        )
    buttons.append(
        [InlineKeyboardButton(text="💾 Сохранить", callback_data="topics:save")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_keyboard(current_time: str, current_threshold: int) -> InlineKeyboardMarkup:
    # Row 1-3: digest time
    time_row = [
        InlineKeyboardButton(
            text=f"{'✅ ' if t == current_time else ''}{t} МСК",
            callback_data=f"digest_time:{t}",
        )
        for t in DIGEST_TIMES
    ]
    # Row 4+: alert threshold
    threshold_rows = [
        [InlineKeyboardButton(
            text=f"{'✅ ' if v == current_threshold else ''}{label}",
            callback_data=f"alert_threshold:{v}",
        )]
        for v, label in ALERT_THRESHOLDS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=[[*time_row], *threshold_rows])
