import re
from datetime import datetime, timezone

CATEGORY_EMOJI = {
    "politics": "🌍",
    "tech":     "💻",
    "sport":    "⚽",
    "economy":  "💰",
    "science":  "🔬",
    "other":    "📌",
}

_ESCAPE = re.compile(r"([_\*\[\]()~`>#+\-=|{}.!\\])")


def escape(text: str) -> str:
    return _ESCAPE.sub(r"\\\1", text or "")


def time_ago(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        minutes = int(delta.total_seconds() // 60)
        if minutes < 60:
            return f"{minutes} мин. назад"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} ч. назад"
        days = hours // 24
        return f"{days} д. назад"
    except Exception:
        return ""


def format_article(row) -> str:
    cat = row["category"] or "other"
    emoji = CATEGORY_EMOJI.get(cat, "📌")
    prefix = ""
    if row["is_breaking"]:
        prefix = "🔴 *СРОЧНО*\n\n"

    title = escape(row["title_ru"] or row["title_orig"] or "")
    summary = escape(row["summary_ru"] or row["summary_orig"] or "")
    source = escape(row["source"] or "")
    ago = escape(time_ago(row["published_at"] or row["processed_at"] or ""))
    url = row["url"] or ""

    return (
        f"{prefix}{emoji} *{title}*\n\n"
        f"📰 {source} · 🕐 {ago}\n\n"
        f"{summary}\n\n"
        f"🔗 [Читать полностью]({url})"
    )


def format_digest_header(topic: str, count: int) -> str:
    emoji = CATEGORY_EMOJI.get(topic, "📌")
    topic_ru = {
        "politics": "Политика",
        "tech":     "Технологии",
        "sport":    "Спорт",
        "economy":  "Экономика",
        "science":  "Наука",
        "all":      "Все темы",
        "other":    "Прочее",
    }.get(topic, topic)
    return f"{emoji} *{escape(topic_ru)}* — топ {count} новостей за 24 часа"
