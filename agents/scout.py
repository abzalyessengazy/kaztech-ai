"""
🛰️ SCOUT AGENTS — «Что произошло?» (global + KZ desk)

Обходит источники, нормализует записи и складывает НОВЫЕ в News Inbox.
Всегда сохраняет источник (source_url/source_name/published_at) — пост
без источника не выйдет. Устойчив к падению отдельного фида.
"""
import html
import re
import socket
import feedparser
import requests

from config import sources
from core import db

HEADERS = {"User-Agent": "KazTechNewsroom/1.0 (+editorial scout)"}
TIMEOUT = 15


def _clean(text: str, limit: int = 400) -> str:
    if not text:
        return ""
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
    return text[:limit]


def _item(url, title, summary, src, published=""):
    return {
        "source_url": url,
        "original_title": _clean(title, 300),
        "original_summary": _clean(summary, 500),
        "source_name": src["name"],
        "source_weight": src["weight"],
        "is_local": src.get("is_local", 0),
        "published_at": published,
    }


def _from_rss(src: dict) -> list[dict]:
    # feedparser has no timeout arg and can hang forever on an unresponsive host.
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(TIMEOUT)
    try:
        feed = feedparser.parse(src["url"], request_headers=HEADERS)
    finally:
        socket.setdefaulttimeout(old_timeout)
    items = []
    for e in feed.entries[:15]:
        link, title = e.get("link"), e.get("title", "").strip()
        if not link or not title:
            continue
        published = e.get("published", "") or e.get("updated", "")
        items.append(_item(link, title, e.get("summary", ""), src, published))
    return items


def _from_hn(src: dict) -> list[dict]:
    r = requests.get(src["url"], headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    items = []
    for hit in r.json().get("hits", [])[:15]:
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        if not hit.get("title"):
            continue
        summary = f"{hit.get('points', 0)} points · {hit.get('num_comments', 0)} comments"
        items.append(_item(url, hit["title"], summary, src, hit.get("created_at", "")))
    return items


def _from_reddit(src: dict) -> list[dict]:
    r = requests.get(src["url"], headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    items = []
    for child in r.json().get("data", {}).get("children", []):
        d = child.get("data", {})
        if not d.get("title") or d.get("stickied"):
            continue
        url = d.get("url_overridden_by_dest") or ("https://www.reddit.com" + d.get("permalink", ""))
        items.append(_item(url, d["title"], f"↑{d.get('ups', 0)} · r/{d.get('subreddit','')}", src))
    return items


FETCHERS = {"rss": _from_rss, "hn": _from_hn, "reddit": _from_reddit}


def run() -> dict:
    db.init_db()
    seen, added, local, failed = 0, 0, 0, []
    for src in sources.SOURCES:
        fetcher = FETCHERS.get(src["type"])
        if not fetcher:
            continue
        try:
            items = fetcher(src)
        except Exception as exc:
            failed.append(f"{src['name']}: {exc}")
            continue
        for item in items:
            seen += 1
            if db.add_news(item):
                added += 1
                local += item["is_local"]
    print(f"[scout] увидел {seen}, новых {added} (из них локальных {local}), упало {len(failed)}")
    for f in failed:
        print(f"  ⚠️  {f}")
    return {"seen": seen, "added": added, "local": local, "failed": failed}


if __name__ == "__main__":
    run()
