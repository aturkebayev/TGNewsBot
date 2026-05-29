import asyncio
import html
import re
from datetime import datetime, timezone, timedelta

import feedparser
import httpx
from loguru import logger

from db.database import article_exists, insert_article
from processor.engine import process_article

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return " ".join(text.split())


def _get_summary(entry) -> str:
    content = getattr(entry, "content", None)
    if content:
        return _strip_html(content[0].get("value", "") or "")
    raw = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    return _strip_html(raw)


# All available RSS sources (displayed in /sources menu)
ALL_RSS_SOURCES: dict[str, str] = {
    "BBC":           "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Guardian":      "https://www.theguardian.com/world/rss",
    "Al Jazeera":    "https://www.aljazeera.com/xml/rss/all.xml",
    "NPR News":      "https://feeds.npr.org/1004/rss.xml",
    "Deutsche Welle":"https://rss.dw.com/rdf/rss-en-all",
    "France 24":     "https://www.france24.com/en/rss",
    "The Independent":"https://www.independent.co.uk/news/world/rss",
    "Euronews":      "https://feeds.feedburner.com/euronews/en/news",
    "SCMP":          "https://www.scmp.com/rss/91/feed",
}

MAX_AGE_HOURS = 24
BATCH_SIZE = 10


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


async def _fetch_feed(client: httpx.AsyncClient, name: str, url: str) -> list[dict]:
    try:
        resp = await client.get(url, timeout=30)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as exc:
        logger.warning(f"RSS fetch failed [{name}]: {exc}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    items = []
    for entry in feed.entries:
        pub = _parse_date(entry)
        if pub and pub < cutoff:
            continue
        title = _strip_html(getattr(entry, "title", "") or "")
        summary = _get_summary(entry)
        link = getattr(entry, "link", "") or ""
        if not link:
            continue
        items.append({
            "source": name,
            "url": link,
            "title_orig": title,
            "summary_orig": summary,
            "published_at": pub.isoformat() if pub else datetime.now(timezone.utc).isoformat(),
        })
    return items


async def poll_all_sources() -> int:
    new_count = 0
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [
            _fetch_feed(client, name, url)
            for name, url in ALL_RSS_SOURCES.items()
        ]
        results = await asyncio.gather(*tasks)

    candidates: list[dict] = []
    for batch in results:
        candidates.extend(batch)

    new_articles = []
    for item in candidates:
        title_prefix = item["title_orig"].lower()[:60]
        if not await article_exists(item["url"], title_prefix):
            new_articles.append(item)

    for i in range(0, len(new_articles), BATCH_SIZE):
        batch = new_articles[i : i + BATCH_SIZE]
        for item in batch:
            try:
                processed = await process_article(
                    item["title_orig"], item["summary_orig"], item["source"]
                )
                row = {
                    **item,
                    **processed,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                }
                await insert_article(row)
                new_count += 1
            except Exception as exc:
                logger.error(f"Failed to process article {item['url']}: {exc}")
        if i + BATCH_SIZE < len(new_articles):
            await asyncio.sleep(1)

    logger.info(f"RSS poll done: {new_count} new articles stored")
    return new_count
