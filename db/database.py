import aiosqlite
from loguru import logger

DB_PATH = "news.db"

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

_conn: aiosqlite.Connection | None = None


async def get_conn() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        _conn = await aiosqlite.connect(DB_PATH)
        _conn.row_factory = aiosqlite.Row
    return _conn


async def init_db() -> None:
    conn = await get_conn()
    await conn.execute(CREATE_ARTICLES)
    await conn.execute(CREATE_USERS)
    await conn.execute(CREATE_SUBSCRIPTIONS)
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


async def get_recent_articles(topic: str, hours: int = 24, limit: int = 5) -> list:
    conn = await get_conn()
    query = """
        SELECT * FROM articles
        WHERE processed_at >= datetime('now', ?)
        {where_cat}
        ORDER BY importance DESC, published_at DESC
        LIMIT ?
    """
    params: list = [f"-{hours} hours"]
    if topic != "all":
        query = query.replace("{where_cat}", "AND category=?")
        params.append(topic)
    else:
        query = query.replace("{where_cat}", "")
    params.append(limit)

    async with conn.execute(query, params) as cur:
        return await cur.fetchall()


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
        """INSERT OR IGNORE INTO users (chat_id, digest_time, created_at)
           VALUES (?, '09:00', datetime('now'))""",
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
