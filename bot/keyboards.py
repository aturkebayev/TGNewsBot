from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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


def settings_keyboard(current_time: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if t == current_time else ''}{t} МСК",
                callback_data=f"digest_time:{t}",
            )
            for t in DIGEST_TIMES
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
