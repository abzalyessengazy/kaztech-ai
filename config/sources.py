"""
Источники редакции. Два деска:

  GLOBAL_SOURCES — мировые AI/tech новости.
  KZ_SOURCES     — казахстанский деск (Phase 2 differentiation).

Именно локальный деск — настоящий moat: глобальный AI + казахстанские
стартапы + местный бизнес + гос-AI + казнет-культура = контент, которого
больше ни у кого нет. Ищем не только большие мировые новости, но и истории,
которые «никто пока не заметил», но релевантные казахстанской аудитории.

Каждый источник:
  type: "rss" | "hn" | "reddit"
  name, url, weight (0.5–1.5), is_local (0/1)
"""

GLOBAL_SOURCES = [
    {"type": "rss", "name": "OpenAI", "url": "https://openai.com/blog/rss.xml", "weight": 1.4, "is_local": 0},
    {"type": "rss", "name": "Google AI", "url": "https://blog.google/technology/ai/rss/", "weight": 1.3, "is_local": 0},
    {"type": "rss", "name": "DeepMind", "url": "https://deepmind.google/blog/rss.xml", "weight": 1.3, "is_local": 0},
    {"type": "rss", "name": "HuggingFace", "url": "https://huggingface.co/blog/feed.xml", "weight": 1.1, "is_local": 0},
    {"type": "rss", "name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "weight": 1.1, "is_local": 0},
    {"type": "rss", "name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "weight": 1.0, "is_local": 0},
    {"type": "rss", "name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index", "weight": 1.0, "is_local": 0},
    {"type": "rss", "name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/", "weight": 0.9, "is_local": 0},
    {"type": "hn", "name": "Hacker News", "url": "https://hn.algolia.com/api/v1/search?tags=front_page", "weight": 1.0, "is_local": 0},
    {"type": "rss", "name": "MIT Tech Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "weight": 0.9, "is_local": 0},
    {"type": "rss", "name": "Product Hunt", "url": "https://www.producthunt.com/feed", "weight": 0.8, "is_local": 0},
]

# ⚠️ URL феодов ниже — предположения. Проверь и поправь под реальные RSS.
# Scout переживёт нерабочий фид (просто пропустит), но лучше выверить.
# is_local=1 -> локальные истории получают приоритет на этапе фильтра.
KZ_SOURCES = [
    {"type": "rss", "name": "Digital Business KZ", "url": "https://digitalbusiness.kz/feed/", "weight": 1.5, "is_local": 1},
    {"type": "rss", "name": "Bluescreen KZ", "url": "https://bluescreen.kz/feed/", "weight": 1.5, "is_local": 1},
    {"type": "rss", "name": "Profit.kz", "url": "https://profit.kz/rss/", "weight": 1.4, "is_local": 1},
    {"type": "rss", "name": "Kapital.kz Tech", "url": "https://kapital.kz/rss", "weight": 1.2, "is_local": 1},
    # Добавь: Astana Hub, гос-инициативы (egov/Smart Data Ukimet), казнет-каналы.
]

SOURCES = GLOBAL_SOURCES + KZ_SOURCES

# Ключевые слова локальной релевантности — фильтр и ранкер поднимают их выше.
KAZAKH_RELEVANCE_HINTS = [
    "kazakhstan", "kazakh", "almaty", "astana", "central asia", "astana hub",
    "kaspi", "казахстан", "алматы", "астана", "қазақстан", "tengri", "freedom",
]

# Мусорный денилист для дешёвого фильтра (LLM на это тратить нельзя).
JUNK_PATTERNS = [
    "emoji", "wordle", "how to watch", "trailer", "deal of the day", "coupon",
    "black friday", "prime day", "recipe", "horoscope", "giveaway",
    "best deals", "on sale", "discount code",
]
