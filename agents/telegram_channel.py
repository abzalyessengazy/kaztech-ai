"""Publish approved posts to the public Telegram channel."""
import time

import requests

from agents import publisher
from config import settings
from core import db

API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
MAX_MESSAGE_CHARS = 4096


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

    body = _send_message(_trim(text))
    message_id = body["result"]["message_id"]
    print(f"[telegram_channel] отправлено в канал: message_id={message_id}")
    return message_id
