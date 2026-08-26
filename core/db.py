"""
SQLite-хранилище редакции (newsroom).

Расширено под второй этап:
  · источник новости хранится всегда (доверие + защита от «AI выдумал»);
  · двухступенчатый пайплайн статусов (inbox → candidate → ranked → finalist → chosen);
  · EDITORIAL MEMORY — что публиковали, что зашло (второй moat после style guide);
  · TASTE FEEDBACK — кнопки Telegram обучают редактора вкусу главреда;
  · THEME ENGAGEMENT — feedback loop: какие темы дают вовлечённость.

SQLite осознанно (в MVP не нужен тяжёлый infra). Схема Postgres-совместима —
при росте меняется только connection-слой, не логика агентов.
"""
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

from config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url     TEXT UNIQUE NOT NULL,
    source_name    TEXT,
    source_weight  REAL DEFAULT 1.0,
    original_title TEXT NOT NULL,
    original_summary TEXT,
    published_at   TEXT,
    fetched_at     TEXT NOT NULL,
    is_local       INTEGER DEFAULT 0,
    importance   REAL, novelty REAL, kz_relevance REAL,
    ai_relevance REAL, virality REAL, satire_pot REAL,
    editorial    REAL, theme TEXT, rank_reason TEXT,
    status       TEXT DEFAULT 'inbox'
);

CREATE TABLE IF NOT EXISTS posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id       INTEGER REFERENCES news(id),
    title         TEXT,
    body          TEXT,
    image_prompt  TEXT,
    satire_note   TEXT,
    cta           TEXT,
    theme         TEXT,
    source_name   TEXT,
    source_url    TEXT,
    created_at    TEXT NOT NULL,
    regen_count   INTEGER DEFAULT 0,
    approved      INTEGER DEFAULT 0,
    published_at  TEXT,
    linkedin_urn  TEXT
);

CREATE TABLE IF NOT EXISTS analytics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id       INTEGER REFERENCES posts(id),
    linkedin_urn  TEXT,
    likes         INTEGER DEFAULT 0,
    comments      INTEGER DEFAULT 0,
    impressions   INTEGER DEFAULT 0,
    collected_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS taste_feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    signal        TEXT NOT NULL,
    post_id       INTEGER,
    created_at    TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def candidate_cutoff() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=settings.CANDIDATE_MAX_AGE_DAYS)).isoformat()


@contextmanager
def connect():
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


# ---------- News (инбокс + этапы) ----------

def add_news(item: dict) -> bool:
    """True, если новость новая (нет дубля по source_url)."""
    with connect() as conn:
        try:
            conn.execute(
                """INSERT INTO news
                   (source_url, source_name, source_weight, original_title,
                    original_summary, published_at, fetched_at, is_local, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'inbox')""",
                (item["source_url"], item.get("source_name", ""),
                 item.get("source_weight", 1.0), item["original_title"],
                 item.get("original_summary", ""), item.get("published_at", ""),
                 now(), int(item.get("is_local", 0))),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def get_inbox(limit: int):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM news WHERE status='inbox' ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def set_status(news_id: int, status: str):
    with connect() as conn:
        conn.execute("UPDATE news SET status=? WHERE id=?", (status, news_id))


def get_candidates(limit: int):
    with connect() as conn:
        # Recency only — no is_local-first bias here. rules_filter already
        # gives locals a scoring bonus; sorting is_local DESC on top of that
        # let local candidates crowd out ALL global ones (OpenAI/Anthropic/etc.)
        # once the local backlog exceeded `limit`.
        rows = conn.execute(
            """SELECT * FROM news
               WHERE status='candidate' AND fetched_at >= ?
               ORDER BY fetched_at DESC LIMIT ?""",
            (candidate_cutoff(), limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_used_news(limit: int = 500):
    """Stories already approved/published/rejected; do not pitch them again."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT * FROM news
               WHERE status IN ('chosen', 'rejected', 'published')
               ORDER BY fetched_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def save_ranking(news_id: int, s: dict):
    with connect() as conn:
        conn.execute(
            """UPDATE news SET status='ranked',
               importance=?, novelty=?, kz_relevance=?, ai_relevance=?,
               virality=?, satire_pot=?, editorial=?, theme=?, rank_reason=?
               WHERE id=?""",
            (s["importance"], s["novelty"], s["kz_relevance"], s["ai_relevance"],
             s["virality"], s["satire_potential"], s["editorial"],
             s.get("theme", ""), s.get("reason", ""), news_id),
        )


def get_finalists(n: int, min_score: float):
    """Top-N by score. min_score gates whether TODAY is worth running at all
    (best story too weak → skip day) — it must NOT filter #2..#N individually,
    or a day with one 8.2 and four 5-6s would show only 1 option instead of 5."""
    with connect() as conn:
        rows = conn.execute(
                """SELECT * FROM news
                    WHERE status='ranked' AND fetched_at >= ?
               ORDER BY editorial DESC LIMIT ?""",
                (candidate_cutoff(), n),
        ).fetchall()
        results = [dict(r) for r in rows]
        if not results or results[0]["editorial"] < min_score:
            return []
        return results


def get_news(news_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM news WHERE id=?", (news_id,)).fetchone()
        return dict(row) if row else None


# ---------- Posts ----------

def save_post(post: dict) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO posts
               (news_id, title, body, image_prompt, satire_note, cta, theme,
                source_name, source_url, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (post["news_id"], post["title"], post["body"], post.get("image_prompt", ""),
             post.get("satire_note", ""), post.get("cta", ""), post.get("theme", ""),
             post.get("source_name", ""), post.get("source_url", ""), now()),
        )
        return cur.lastrowid


def update_post_body(post_id: int, post: dict):
    """После Regenerate/модификатора — перезаписываем тело и растим счётчик."""
    with connect() as conn:
        conn.execute(
            """UPDATE posts SET title=?, body=?, image_prompt=?, satire_note=?,
               cta=?, theme=?, regen_count=regen_count+1 WHERE id=?""",
            (post["title"], post["body"], post.get("image_prompt", ""),
             post.get("satire_note", ""), post.get("cta", ""),
             post.get("theme", ""), post_id),
        )


def set_approval(post_id: int, approved: int):
    with connect() as conn:
        conn.execute("UPDATE posts SET approved=? WHERE id=?", (approved, post_id))


def mark_published(post_id: int, linkedin_urn: str):
    with connect() as conn:
        conn.execute(
            "UPDATE posts SET published_at=?, linkedin_urn=? WHERE id=?",
            (now(), linkedin_urn, post_id),
        )


def get_post(post_id: int):
    with connect() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
        return dict(row) if row else None


# ---------- EDITORIAL MEMORY ----------

def successful_posts(n: int = 3):
    """Топ опубликованных постов по вовлечённости — примеры «что зашло»."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT p.title, p.body, p.theme,
                      COALESCE(SUM(a.likes + a.comments*2), 0) AS eng
               FROM posts p
               LEFT JOIN analytics a ON a.post_id = p.id
               WHERE p.published_at IS NOT NULL
               GROUP BY p.id ORDER BY eng DESC LIMIT ?""",
            (n,),
        ).fetchall()
        return [dict(r) for r in rows]


def recent_published(n: int = 5):
    """Недавно опубликованные темы — чтобы Editor не повторялся."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT title, theme, published_at FROM posts
               WHERE published_at IS NOT NULL
               ORDER BY published_at DESC LIMIT ?""",
            (n,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- TASTE FEEDBACK (вкус главреда) ----------

def log_feedback(signal: str, post_id=None):
    with connect() as conn:
        conn.execute(
            "INSERT INTO taste_feedback (signal, post_id, created_at) VALUES (?, ?, ?)",
            (signal, post_id, now()),
        )


def taste_counts() -> dict:
    with connect() as conn:
        rows = conn.execute(
            "SELECT signal, COUNT(*) c FROM taste_feedback GROUP BY signal",
        ).fetchall()
        return {r["signal"]: r["c"] for r in rows}


# ---------- THEME ENGAGEMENT (feedback loop) ----------

def theme_engagement():
    """Средняя вовлечённость по темам — подсказка для Ranker."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT p.theme,
                      AVG(a.likes + a.comments*2 + a.impressions*0.01) AS score,
                      COUNT(DISTINCT p.id) AS posts
               FROM analytics a JOIN posts p ON p.id = a.post_id
               WHERE p.theme IS NOT NULL AND p.theme != ''
               GROUP BY p.theme ORDER BY score DESC""",
        ).fetchall()
        return [dict(r) for r in rows]


def save_analytics(post_id: int, urn: str, likes: int, comments: int, impressions: int):
    with connect() as conn:
        conn.execute(
            """INSERT INTO analytics (post_id, linkedin_urn, likes, comments, impressions, collected_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (post_id, urn, likes, comments, impressions, now()),
        )


# ---------- утилита ----------

def normalize_title(title: str) -> str:
    return re.sub(r"[^a-zа-яё0-9 ]", "", title.lower()).strip()
