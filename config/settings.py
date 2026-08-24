"""Загрузка конфигурации из окружения."""
import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# LLM
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")
MODEL_RANKER = _get("MODEL_RANKER", "claude-sonnet-5")
MODEL_EDITOR = _get("MODEL_EDITOR", "claude-opus-4-8")
# Арзан тіл сапасы QA өткізгіш (polish.py) — editor-ден кейінгі жеңіл түзету.
MODEL_CHECKER = _get("MODEL_CHECKER", "claude-haiku-4-5-20251001")

# Telegram
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID")
TELEGRAM_CHANNEL_ID = _get("TELEGRAM_CHANNEL_ID")
TELEGRAM_CHANNEL_ENABLED = _get("TELEGRAM_CHANNEL_ENABLED", "1") == "1"

# LinkedIn
LINKEDIN_ENABLED = _get("LINKEDIN_ENABLED", "1") == "1"
LINKEDIN_ACCESS_TOKEN = _get("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_AUTHOR_URN = _get("LINKEDIN_AUTHOR_URN")
LINKEDIN_VISIBILITY = _get("LINKEDIN_VISIBILITY", "PUBLIC").upper()
LINKEDIN_POST_API = _get("LINKEDIN_POST_API", "rest").lower()
LINKEDIN_API_VERSION = _get("LINKEDIN_API_VERSION", "202608")
LINKEDIN_IMAGE_MODE = _get("LINKEDIN_IMAGE_MODE", "source").lower()

# Общее
DB_PATH = _get("DB_PATH", "kaztech.db")
SCOUT_MAX_ITEMS = int(_get("SCOUT_MAX_ITEMS", "40"))
MIN_EDITORIAL_SCORE = float(_get("MIN_EDITORIAL_SCORE", "6.5"))
DRY_RUN = _get("DRY_RUN", "1") == "1"
SCOUT_INTERVAL_HOURS = int(_get("SCOUT_INTERVAL_HOURS", "3"))
NEWSROOM_INTERVAL_HOURS = int(_get("NEWSROOM_INTERVAL_HOURS", "0"))
