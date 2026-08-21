"""
👨‍💼 TELEGRAM EDITOR-IN-CHIEF — обучаемый аппрув.

Кнопки не просто Publish/Reject, а инструменты вкуса:

  ✅ Publish   ✏️ Regenerate   🔥 Spicier
  🇰🇿 More KZ  📰 Less satire  ❌ Reject

Модификаторы перегенерируют пост на месте (editMessageText) и логируют
сигнал в taste_feedback → редактор учится вкусу главреда без промптов.

Голый Bot API, без внешних SDK. review() ведёт весь интерактив и
возвращает финальный статус.
"""
import time
import requests

from config import settings
from core import db
from agents import editor, visual, publisher, telegram_channel

API = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

BUTTONS = [
    [{"text": "✅ Publish", "callback_data": "publish"},
     {"text": "✏️ Regenerate", "callback_data": "regenerate"}],
    [{"text": "🔥 Spicier", "callback_data": "spicier"},
     {"text": "🇰🇿 More KZ", "callback_data": "more_kazakh"},
     {"text": "📰 Less satire", "callback_data": "less_satire"}],
    [{"text": "❌ Reject", "callback_data": "reject"}],
]
MODIFIERS = {"regenerate", "spicier", "more_kazakh", "less_satire"}
MAX_CARD_CHARS = 3900


def _trim(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "…"


def _api(method: str, **params):
    r = requests.post(f"{API}/{method}", json=params, timeout=35)
    r.raise_for_status()
    return r.json()


def _next_update_offset() -> int | None:
    """Skip old pending callbacks before a new approval session starts."""
    updates = _api("getUpdates", timeout=0).get("result", [])
    if not updates:
        return None
    return max(update["update_id"] for update in updates) + 1


def _answer_callback(callback_id: str, text: str) -> None:
    try:
        _api("answerCallbackQuery", callback_query_id=callback_id, text=text)
    except requests.HTTPError:
        pass


def _story_summary(story: dict) -> str:
    title = story.get("original_title") or story.get("title", "")
    summary = story.get("original_summary") or story.get("summary", "")
    reason = story.get("selection_reason") or story.get("rank_reason", "")
    source_name = story.get("source_name", "")
    source_url = story.get("source_url", "")

    parts = [f"🗞 {title}".strip()]
    if summary:
        parts.append(f"Қысқаша: {_trim(summary, 450)}")
    if reason:
        parts.append(f"Неге таңдадық: {reason}")
    if source_name or source_url:
        source = f"Дереккөз: {source_name}".strip()
        if source_url:
            source += f"\n{source_url}"
        parts.append(source)
    return "\n".join(parts)


def _card(story: dict, post: dict, score: float, regen: int) -> str:
    tag = f"  ·  regen ×{regen}" if regen else ""
    card = (
        f"🔥 БҮГІНГІ ИСТОРИЯ  ·  SCORE {score}{tag}\n"
        f"🏷 {post.get('theme','')}   🔗 {post.get('source_name','')}\n\n"
        f"{_story_summary(story)}\n\n"
        f"--- ҰСЫНЫЛҒАН LINKEDIN ПОСТ ---\n"
        f"📌 {post['title']}\n\n{post['body']}\n\n"
        f"🎯 {post['cta']}\n😏 Сатира: {post['satire_note']}"
    )
    return _trim(card, MAX_CARD_CHARS)


def _send(story, post, score, regen=0):
    return _api("sendMessage", chat_id=settings.TELEGRAM_CHAT_ID,
                text=_card(story, post, score, regen),
                reply_markup={"inline_keyboard": BUTTONS})


def _edit(message_id, story, post, score, regen):
    _api("editMessageText", chat_id=settings.TELEGRAM_CHAT_ID, message_id=message_id,
         text=_card(story, post, score, regen), reply_markup={"inline_keyboard": BUTTONS})


def _notify(text):
    try:
        _api("sendMessage", chat_id=settings.TELEGRAM_CHAT_ID, text=text)
    except Exception:
        pass


def review(story: dict, post: dict, post_id: int, timeout_minutes: int = 30) -> str:
    """
    Интерактивный цикл: показывает карточку, обрабатывает модификаторы
    (перегенерирует на месте), пока не Publish/Reject/timeout.
    Возвращает 'published' | 'rejected' | 'timeout'.
    """
    score = story.get("editorial", 0)
    offset = _next_update_offset()
    sent = _send(story, post, score)
    message_id = sent["result"]["message_id"]
    regen = 0

    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        updates = _api("getUpdates", offset=offset, timeout=5).get("result", [])
        for upd in updates:
            offset = upd["update_id"] + 1
            cb = upd.get("callback_query")
            if not cb:
                continue
            signal = cb["data"]
            _answer_callback(cb["id"], f"⏳ {signal}…")
            db.log_feedback(signal, post_id)

            if signal == "publish":
                db.set_approval(post_id, 1)
                urn = publisher.publish_post(post_id)
                channel_message_id = telegram_channel.publish_post(post_id)
                _notify(f"✅ Жарияланды (post {post_id}). LinkedIn: {urn}. Telegram: {channel_message_id}")
                return "published"
            if signal == "reject":
                db.set_approval(post_id, -1)
                _notify(f"❌ Қабылданбады (post {post_id}).")
                return "rejected"
            if signal in MODIFIERS:
                post = editor.run(story, modifier=signal)
                post = visual.run(post)
                db.update_post_body(post_id, post)
                regen += 1
                _edit(message_id, story, post, score, regen)
        time.sleep(3)

    _notify("⏳ Уақыт бітті — жарияланбады.")
    return "timeout"
