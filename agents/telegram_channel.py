"""Publish approved posts to the public Telegram channel."""
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

    resp = requests.post(
        f"{API}/sendMessage",
        json={
            "chat_id": settings.TELEGRAM_CHANNEL_ID,
            "text": _trim(text),
            "disable_web_page_preview": False,
        },
        timeout=35,
    )
    resp.raise_for_status()
    message_id = resp.json()["result"]["message_id"]
    print(f"[telegram_channel] отправлено в канал: message_id={message_id}")
    return message_id