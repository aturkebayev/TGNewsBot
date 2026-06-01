import os
import aiosqlite
from loguru import logger

DATA_DIR = os.getenv("DATA_DIR", ".")
DB_PATH = os.path.join(DATA_DIR, "news.db")

CREATE_ARTICLES = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE,
    source TEXT,
    category TEXT,
    title_orig TEXT,
    summary_orig TEXT,
    title_ru TEXT,
    summary_ru TEXT,
    importance INTEGER DEFAULT 5,
    is_breaking INTEGER DEFAULT 0,
    published_at TEXT,
    processed_at TEXT,
    sent_breaking INTEGER DEFAULT 0
)
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    digest_time TEXT DEFAULT '09:00',
    alert_threshold INTEGER DEFAULT 8,
    created_at TEXT
)
"""

CREATE_SUBSCRIPTIONS = """
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id INTEGER,
    topic TEXT,
    UNIQUE(user_id, topic)
)
"""

CREATE_VIEWED = """
CREATE TABLE IF NOT EXISTS user_article_views (
    user_id INTEGER,
    article_id INTEGER,
    viewed_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, article_id)
)
"""

# Tracks articles that were shown to the user via manual "📰 Новости" request.
# Kept separate from user_article_views (push/digest tracking) so that
# one user's manual reads never affect another user's ability to see the same articles.
CREATE_MANUAL_READS = """
CREATE TABLE IF NOT EXISTS user_manual_reads (
    user_id INTEGER,
    article_id INTEGER,
    read_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, article_id)
)
"""

# Stores DISABLED sources per user (empty = all sources enabled)
CREATE_DISABLED_SOURCES = """
CREATE TABLE IF NOT EXISTS user_disabled_sources (
    user_id INTEGER,
    source  TEXT,
    PRIMARY KEY (user_id, source)
)
"""

_conn: aiosqlite.Connection | None = None


async def get_conn() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _conn = await aiosqlite.connect(DB_PATH)
        _conn.row_factory = aiosqlite.Row
    return _conn


async def init_db() -> None:
    conn = await get_conn()
    await conn.execute(CREATE_ARTICLES)
    await conn.execute(CREATE_USERS)
    await conn.execute(CREATE_SUBSCRIPTIONS)
    await conn.execute(CREATE_VIEWED)
    await conn.execute(CREATE_MANUAL_READS)
    await conn.execute(CREATE_DISABLED_SOURCES)
    # migrate: add alert_threshold if missing (existing DBs)
    try:
        await conn.execute("ALTER TABLE users ADD COLUMN alert_threshold INTEGER DEFAULT 8")
    except Exception:
        pass
    await conn.commit()
    logger.info("Database initialized")


async def close_db() -> None:
    global _conn
    if _conn:
        await _conn.close()
        _conn = None


# ── articles ──────────────────────────────────────────────────────────────────

async def article_exists(url: str, title_prefix: str) -> bool:
    conn = await get_conn()
    async with conn.execute(
        "SELECT 1 FROM articles WHERE url=? OR LOWER(SUBSTR(title_orig,1,60))=?",
        (url, title_prefix),
    ) as cur:
        return await cur.fetchone() is not None


async def insert_article(article: dict) -> None:
    conn = await get_conn()
    await conn.execute(
        """INSERT OR IGNORE INTO articles
           (url, source, category, title_orig, summary_orig,
            title_ru, summary_ru, importance, is_breaking,
            published_at, processed_at)
           VALUES (:url,:source,:category,:title_orig,:summary_orig,
                   :title_ru,:summary_ru,:importance,:is_breaking,
                   :published_at,:processed_at)""",
        article,
    )
    await conn.commit()


async def get_recent_articles(
    topic: str,
    hours: int = 24,
    limit: int = 5,
    exclude_user_id: int | None = None,
    min_importance: int = 0,
    max_importance: int | None = None,
    enabled_sources: list[str] | None = None,
    manual_reads: bool = False,
) -> list:
    """Fetch recent articles.

    exclude_user_id — skip articles already seen by this user.
    min_importance / max_importance — filter by importance score (1–10).
    manual_reads=True  → checks user_manual_reads (ручной запрос новостей)
    manual_reads=False → checks user_article_views (push/дайджест, по умолчанию)
    """
    conn = await get_conn()

    cat_filter = "" if topic == "all" else "AND a.category=?"
    imp_filter = "" if min_importance == 0 else "AND a.importance>=?"
    max_filter = "" if max_importance is None else "AND a.importance<=?"
    params: list = [f"-{hours} hours"]

    if topic != "all":
        params.append(topic)
    if min_importance > 0:
        params.append(min_importance)
    if max_importance is not None:
        params.append(max_importance)

    # source filter: only include enabled sources
    src_filter = ""
    if enabled_sources is not None:
        if not enabled_sources:
            return []  # all sources disabled
        placeholders = ",".join("?" * len(enabled_sources))
        src_filter = f"AND a.source IN ({placeholders})"
        params.extend(enabled_sources)

    view_filter = ""
    if exclude_user_id is not None:
        view_table = "user_manual_reads" if manual_reads else "user_article_views"
        view_filter = f"AND a.id NOT IN (SELECT article_id FROM {view_table} WHERE user_id=?)"
        params.append(exclude_user_id)

    query = f"""
        SELECT a.* FROM articles a
        WHERE a.processed_at >= datetime('now', ?)
        {cat_filter}
        {imp_filter}
        {max_filter}
        {src_filter}
        {view_filter}
        ORDER BY a.importance DESC, a.published_at DESC
        LIMIT ?
    """
    params.append(limit)
    async with conn.execute(query, params) as cur:
        return await cur.fetchall()


async def mark_articles_viewed(user_id: int, article_ids: list[int]) -> None:
    """Mark articles as seen via push/digest (used by scheduler only)."""
    if not article_ids:
        return
    conn = await get_conn()
    await conn.executemany(
        "INSERT OR IGNORE INTO user_article_views (user_id, article_id) VALUES (?, ?)",
        [(user_id, aid) for aid in article_ids],
    )
    await conn.commit()


async def mark_manually_read(user_id: int, article_ids: list[int]) -> None:
    """Mark articles as manually read by the user (used by the 📰 Новости handler).

    Writes to BOTH tables:
    - user_manual_reads  → prevents showing the same article again in manual requests
    - user_article_views → prevents the digest/alert scheduler from re-sending articles
                          the user has already read manually (Bug-1 fix)
    Each table is scoped per user, so one user's reads never affect another's.
    """
    if not article_ids:
        return
    conn = await get_conn()
    pairs = [(user_id, aid) for aid in article_ids]
    await conn.executemany(
        "INSERT OR IGNORE INTO user_manual_reads (user_id, article_id) VALUES (?, ?)",
        pairs,
    )
    await conn.executemany(
        "INSERT OR IGNORE INTO user_article_views (user_id, article_id) VALUES (?, ?)",
        pairs,
    )
    await conn.commit()


async def get_unsent_breaking() -> list:
    conn = await get_conn()
    async with conn.execute(
        "SELECT * FROM articles WHERE is_breaking=1 AND sent_breaking=0"
    ) as cur:
        return await cur.fetchall()


async def mark_breaking_sent(article_id: int) -> None:
    conn = await get_conn()
    await conn.execute(
        "UPDATE articles SET sent_breaking=1 WHERE id=?", (article_id,)
    )
    await conn.commit()


# ── users ─────────────────────────────────────────────────────────────────────

async def upsert_user(chat_id: int) -> None:
    conn = await get_conn()
    await conn.execute(
        """INSERT OR IGNORE INTO users (chat_id, digest_time, alert_threshold, created_at)
           VALUES (?, '09:00', 8, datetime('now'))""",
        (chat_id,),
    )
    await conn.commit()


async def get_user(chat_id: int) -> aiosqlite.Row | None:
    conn = await get_conn()
    async with conn.execute("SELECT * FROM users WHERE chat_id=?", (chat_id,)) as cur:
        return await cur.fetchone()


async def set_digest_time(chat_id: int, time_str: str) -> None:
    conn = await get_conn()
    await conn.execute(
        "UPDATE users SET digest_time=? WHERE chat_id=?", (time_str, chat_id)
    )
    await conn.commit()


async def set_alert_threshold(chat_id: int, threshold: int) -> None:
    conn = await get_conn()
    await conn.execute(
        "UPDATE users SET alert_threshold=? WHERE chat_id=?", (threshold, chat_id)
    )
    await conn.commit()


async def get_all_users() -> list:
    conn = await get_conn()
    async with conn.execute("SELECT * FROM users") as cur:
        return await cur.fetchall()


async def get_users_by_digest_time(time_str: str) -> list:
    conn = await get_conn()
    async with conn.execute(
        "SELECT * FROM users WHERE digest_time=?", (time_str,)
    ) as cur:
        return await cur.fetchall()


# ── subscriptions ─────────────────────────────────────────────────────────────

async def add_subscription(chat_id: int, topic: str) -> None:
    conn = await get_conn()
    await conn.execute(
        "INSERT OR IGNORE INTO subscriptions (user_id, topic) VALUES (?,?)",
        (chat_id, topic),
    )
    await conn.commit()


async def remove_subscription(chat_id: int, topic: str) -> None:
    conn = await get_conn()
    await conn.execute(
        "DELETE FROM subscriptions WHERE user_id=? AND topic=?", (chat_id, topic)
    )
    await conn.commit()


async def get_subscriptions(chat_id: int) -> list[str]:
    conn = await get_conn()
    async with conn.execute(
        "SELECT topic FROM subscriptions WHERE user_id=?", (chat_id,)
    ) as cur:
        rows = await cur.fetchall()
        return [r["topic"] for r in rows]


async def get_users_subscribed_to(topic: str) -> list:
    conn = await get_conn()
    query = """
        SELECT DISTINCT u.* FROM users u
        JOIN subscriptions s ON s.user_id = u.chat_id
        WHERE s.topic=? OR s.topic='all'
    """
    async with conn.execute(query, (topic,)) as cur:
        return await cur.fetchall()


async def get_all_subscribed_users() -> list:
    """Return all users that have at least one subscription."""
    conn = await get_conn()
    async with conn.execute(
        "SELECT DISTINCT u.* FROM users u JOIN subscriptions s ON s.user_id=u.chat_id"
    ) as cur:
        return await cur.fetchall()


# ── source preferences ────────────────────────────────────────────────────────

async def get_disabled_sources(user_id: int) -> list[str]:
    """Returns list of source names the user has disabled. Empty = all enabled."""
    conn = await get_conn()
    async with conn.execute(
        "SELECT source FROM user_disabled_sources WHERE user_id=?", (user_id,)
    ) as cur:
        rows = await cur.fetchall()
        return [r["source"] for r in rows]


async def toggle_source(user_id: int, source: str) -> bool:
    """Toggle source. Returns True if now enabled, False if now disabled."""
    conn = await get_conn()
    async with conn.execute(
        "SELECT 1 FROM user_disabled_sources WHERE user_id=? AND source=?",
        (user_id, source),
    ) as cur:
        exists = await cur.fetchone()
    if exists:
        await conn.execute(
            "DELETE FROM user_disabled_sources WHERE user_id=? AND source=?",
            (user_id, source),
        )
        await conn.commit()
        return True  # now enabled
    else:
        await conn.execute(
            "INSERT OR IGNORE INTO user_disabled_sources (user_id, source) VALUES (?,?)",
            (user_id, source),
        )
        await conn.commit()
        return False  # now disabled
