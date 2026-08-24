"""Publish approved posts to the public Telegram channel."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
import time

import requests

from agents import publisher
from config import settings
from core import db

API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
MAX_MESSAGE_CHARS = 4096
MAX_CAPTION_CHARS = 1024


class _MetaImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        data = {key.lower(): value for key, value in attrs if key and value}
        name = (data.get("property") or data.get("name") or "").lower()
        if name in {"og:image", "og:image:secure_url", "twitter:image"} and data.get("content"):
            self.images.append(data["content"])


def _trim(text: str, limit: int = MAX_MESSAGE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "…"


def _send_message(text: str, attempts: int = 3) -> dict:
    """POST sendMessage with a couple of retries — a lost channel post is
    expensive, and Telegram's API does occasionally hiccup with a transient 4xx/5xx."""
    last_exc = None
    for attempt in range(1, attempts + 1):
        resp = requests.post(
            f"{API}/sendMessage",
            json={
                "chat_id": settings.TELEGRAM_CHANNEL_ID,
                "text": text,
                "disable_web_page_preview": False,
            },
            timeout=35,
        )
        if resp.ok:
            return resp.json()
        print(f"[telegram_channel] sendMessage сәтсіз (попытка {attempt}/{attempts}, "
              f"HTTP {resp.status_code}): {resp.text[:500]}")
        last_exc = requests.HTTPError(f"{resp.status_code}: {resp.text[:500]}", response=resp)
        if attempt < attempts:
            time.sleep(2 * attempt)
    raise last_exc


def _find_source_image_url(source_url: str) -> str | None:
    if not source_url:
        return None
    resp = requests.get(source_url, timeout=20)
    resp.raise_for_status()
    parser = _MetaImageParser()
    parser.feed(resp.text[:200000])
    if not parser.images:
        return None
    return urljoin(source_url, parser.images[0])


def _send_photo(post: dict, text: str) -> dict | None:
    image_path = (post.get("image_path") or "").strip()
    if image_path:
        path = Path(image_path)
        if path.exists() and path.is_file():
            with path.open("rb") as fh:
                resp = requests.post(
                    f"{API}/sendPhoto",
                    data={
                        "chat_id": settings.TELEGRAM_CHANNEL_ID,
                        "caption": _trim(text, MAX_CAPTION_CHARS),
                    },
                    files={"photo": fh},
                    timeout=60,
                )
            if resp.ok:
                print(f"[telegram_channel] sent photo from local file: {path}")
                return resp.json()
            print(f"[telegram_channel] sendPhoto local failed: HTTP {resp.status_code} {resp.text[:300]}")

    source_url = (post.get("source_url") or "").strip()
    image_url = _find_source_image_url(source_url)
    if not image_url:
        print("[telegram_channel] no source image metadata found; using text message")
        return None

    resp = requests.post(
        f"{API}/sendPhoto",
        json={
            "chat_id": settings.TELEGRAM_CHANNEL_ID,
            "photo": image_url,
            "caption": _trim(text, MAX_CAPTION_CHARS),
        },
        timeout=35,
    )
    if resp.ok:
        print(f"[telegram_channel] sent photo from source preview: {image_url}")
        return resp.json()

    print(f"[telegram_channel] sendPhoto source failed: HTTP {resp.status_code} {resp.text[:300]}")
    return None


def publish_post(post_id: int) -> int | None:
    """Send the exact final publisher text to TELEGRAM_CHANNEL_ID."""
    post = db.get_post(post_id)
    if not post:
        raise ValueError(f"post {post_id} не найден")

    text = publisher.compose_text(post)
    if not settings.TELEGRAM_CHANNEL_ENABLED:
        print("[telegram_channel] TELEGRAM_CHANNEL_ENABLED=0 — пропускаем канал.")
        return None

    if settings.DRY_RUN:
        print("[telegram_channel] DRY_RUN — не отправлено. Финальный текст:\n")
        print(text)
        print("\n[telegram_channel] (DRY_RUN=0 в .env — чтобы отправлять в канал)")
        return None

    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан (см. .env).")
    if not settings.TELEGRAM_CHANNEL_ID:
        print("[telegram_channel] TELEGRAM_CHANNEL_ID не задан — пропускаем канал.")
        return None

    body = _send_photo(post, text)
    if body is None:
        print("[telegram_channel] sending text-only message")
        body = _send_message(_trim(text))

    message_id = body["result"]["message_id"]
    print(f"[telegram_channel] отправлено в канал: message_id={message_id}")
    return message_id
