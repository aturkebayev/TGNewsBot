import asyncio
import re
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from langdetect import detect, LangDetectException
except ImportError:
    detect = None
    LangDetectException = Exception

from deep_translator import GoogleTranslator

CATEGORY_KEYWORDS = {
    "politics": [
        "election", "government", "president", "minister",
        "parliament", "war", "sanctions", "diplomat", "coup", "protest",
    ],
    "tech": [
        "ai", "software", "startup", "apple", "google", "microsoft",
        "meta", "openai", "cybersecurity", "hack", "chip", "robot",
    ],
    "sport": [
        "football", "soccer", "basketball", "tennis", "olympic",
        "championship", "league", "tournament", "fifa", "nba", "ufc",
    ],
    "economy": [
        "market", "economy", "stock", "inflation", "fed", "gdp",
        "recession", "trade", "bank", "oil", "dollar", "crypto",
    ],
    "science": [
        "climate", "space", "nasa", "research", "vaccine", "health",
        "disease", "cancer", "earthquake", "flood", "discovery",
    ],
}

BREAKING_KEYWORDS = [
    "killed", "dead", "death", "attack", "explosion", "war", "crisis",
    "emergency", "breaking", "urgent", "crash", "disaster", "terror",
    "coup", "nuclear", "missile",
]


def _word_match(keyword: str, text: str) -> bool:
    return bool(re.search(r"\b" + re.escape(keyword) + r"\b", text))


def categorize(text: str) -> str:
    tl = text.lower()
    scores = {
        c: sum(1 for kw in kws if _word_match(kw, tl))
        for c, kws in CATEGORY_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "other"


def score_importance(text: str, source: str) -> int:
    tl = text.lower()
    score = 5
    if source in ("Reuters", "AP News"):
        score += 2
    score += min(sum(1 for kw in BREAKING_KEYWORDS if _word_match(kw, tl)), 3)
    return min(score, 10)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _do_translate(text: str) -> str:
    return GoogleTranslator(source="auto", target="ru").translate(text)


def translate_to_ru(text: str) -> str:
    if not text:
        return ""
    try:
        if detect is not None:
            try:
                if detect(text) == "ru":
                    return text
            except Exception:
                pass
        return _do_translate(text)
    except Exception as exc:
        logger.warning(f"Translation failed: {exc}")
        return text


async def process_article(title: str, summary: str, source: str) -> dict:
    combined = f"{title} {summary}"
    imp = score_importance(combined, source)
    title_ru = await asyncio.to_thread(translate_to_ru, title)
    summary_ru = await asyncio.to_thread(translate_to_ru, summary)
    return {
        "title_ru": title_ru,
        "summary_ru": summary_ru,
        "category": categorize(combined),
        "importance": imp,
        "is_breaking": 1 if imp >= 9 else 0,
    }
