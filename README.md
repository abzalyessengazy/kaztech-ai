# 🇰🇿 Kazakh Tech Intelligence — AI-powered Kazakh editorial newsroom

Это **не новостной портал**. Это редакция: AI newsroom ищет, проверяет,
ранжирует и готовит до **пяти историй на выбор**. Главред (человек) выбирает
одну и утверждает финальный пост.
*TechCrunch × The Onion × қазақ интернет-мәдениеті.*

Роли: система = **newsroom**, ты = **editor-in-chief**.

---

## Пайплайн (2-й этап)

```
        INTERNET (Global desk + 🇰🇿 KZ desk)
                     │
              🛰️ SCOUT  ──────► News Inbox (источник хранится всегда)
                     │
              🧹 RULES FILTER ─► ~20 кандидатов (без LLM: денилист, дедуп, 50/50 local/global)
                     │
              🧠 RANKER ───────► batch scoring → до 5 финалистов → главред выбирает 1 историю
                     │              ▲ theme feedback loop
              ✍️ EDITOR ───────► KZ + сатира (+ MEMORY + вкус главреда)
                     │
              🎨 VISUAL ───────► фирменный визуал
                     │
              👨‍💼 TELEGRAM ────► ✅Publish ✏️Regenerate 🔥Spicier 🇰🇿MoreKZ 📰LessSatire ❌Reject
                     │
              🚀 PUBLISHER ────► LinkedIn (+ 🔗 Дереккөз: источник)
                     │
              📊 ENGAGEMENT ───► MEMORY ──► обратно в RANKER
```

## Что нового во 2-м этапе

| Улучшение | Где | Зачем |
|---|---|---|
| **Источник всегда** | `scout`, `publisher` | доверие + защита от «AI выдумал»; в посте `🔗 Дереккөз:` |
| **2-ступенчатый ranker** | `rules_filter` + `ranker` | не жечь LLM на «Apple выпустила эмодзи»; до 5 вариантов для выбора |
| **EDITORIAL MEMORY** | `db.successful_posts` → `editor` | стиль обучается на том, что зашло (2-й moat) |
| **Feedback loop** | `db.theme_engagement` → `ranker` | ранкер понимает: 🇰🇿+AI ценно, generic AI слабо |
| **Богатые кнопки** | `telegram_bot` | обучаешь вкусу без единого промпта |
| **Баланс источников** | `rules_filter`, `sources.py` | 10 local + 10 global мест; Anthropic/Claude через Google News RSS |
| **3-дневное окно** | `core/db.py` | хорошие, но невыбранные истории могут вернуться, но устаревшие не копятся |
| **Newsroom-фрейминг** | везде | «редакция готовит историю», а не «AI пишет новости» |

## Структура

```
config/
  settings.py        env-конфиг
  sources.py         GLOBAL_SOURCES + KZ_SOURCES + мусорный денилист
  style_guide.py     🔑 ДНК: голос, термины, сатира + MEMORY/TASTE инъекция
core/
  db.py              news / posts / analytics / taste_feedback + память, темы
  llm.py             Anthropic API
agents/
  scout.py           сбор (global + KZ), хранит источник
  rules_filter.py    дешёвая ступень 0 (без LLM)
       ranker.py          batch scoring + до 5 финалистов для выбора главредом
  editor.py          KZ + сатира + память + вкус + модификаторы
  visual.py          промпт визуала (+хук генерации)
  publisher.py       LinkedIn + строка источника
approval/
       telegram_bot.py    выбор истории + Publish / Regenerate / Spicier / More KZ / Less satire / Edit / Reject
analytics/
  tracker.py         метрики + theme-report
orchestrator.py      дневной цикл
scheduler.py         scout 3ч / newsroom по cron в Asia/Almaty
```

## Быстрый старт

```bash
pip install -r requirements.txt
cp .env.example .env          # впиши ANTHROPIC_API_KEY (обязателен)
python orchestrator.py --dry  # весь цикл без публикации
```

`DRY_RUN=1` по умолчанию — собирает, фильтрует, ранжирует, пишет пост,
показывает финальный текст, но НЕ публикует. Идеально обкатать голос.

### Ключи

| Ключ | Для чего |
|---|---|
| `ANTHROPIC_API_KEY` | ранжирование + редактура (обязателен) |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | аппрув с кнопками |
| `TELEGRAM_CHANNEL_ID` | канал для публикации одобренных постов (`@name` или `-100...`) |
| `TELEGRAM_CHANNEL_ENABLED` | `1` публиковать в Telegram-канал, `0` пропускать |
| `LINKEDIN_ENABLED` | `1` публиковать в LinkedIn, `0` пропускать |
| `LINKEDIN_ACCESS_TOKEN` + `LINKEDIN_AUTHOR_URN` | реальная публикация |
| `LINKEDIN_VISIBILITY` | `PUBLIC` или `CONNECTIONS` для поста |
| `NEWSROOM_INTERVAL_HOURS` | `0` — 09:00 ежедневно; `6` — 09:00, 15:00, 21:00 Asia/Almaty |
| `CANDIDATE_MAX_AGE_DAYS` | сколько дней история остаётся в редакционном пуле; по умолчанию `3` |

## Режимы

```bash
python orchestrator.py          # с аппрувом в Telegram
python orchestrator.py --auto   # автономно (когда доверишься)
python orchestrator.py --dry    # ничего не публикует
python -m agents.scout          # только собрать
python -m agents.rules_filter   # только отфильтровать
python -m unittest discover -s tests  # smoke-тесты без внешних API
python linkedin_setup_check.py  # проверить LinkedIn token/author URN без публикации
python -m analytics.tracker     # theme-report + вкус главреда
python scheduler.py             # держать расписание
```

## Production

Recommended MVP mode while LinkedIn Page API access is pending:

```env
DRY_RUN=0
LINKEDIN_ENABLED=0
TELEGRAM_CHANNEL_ENABLED=1
SCOUT_MAX_ITEMS=8
MODEL_EDITOR=claude-sonnet-5
NEWSROOM_INTERVAL_HOURS=6  # 09:00, 15:00, 21:00 Asia/Almaty
CANDIDATE_MAX_AGE_DAYS=3
```

Run as an always-on worker:

```bash
python scheduler.py
```

Container hosts can use the included `Dockerfile`; the container starts `scheduler.py`.
Set secrets in the host dashboard, not in git. Keep a persistent disk/volume if you want
`kaztech.db` history to survive deploys and restarts.

## Как обучается вкус

Кнопки Telegram пишут сигналы в `taste_feedback`. Нажал 🔥 Spicier 20 раз —
`taste_directive()` добавит в промпт редактора: «этот главред любит смелую
сатиру». Стиль дрейфует под тебя без переписывания промптов.

## Дорожная карта

1. **Сейчас:** довести до автономной редакции, **цель — 30 дней = 30 постов**.
   После 30 постов понимания больше, чем после ещё месяца разработки.
2. **Phase 2 — казахстанский контент** (не картинки): наполнить `KZ_SOURCES`
   реальными фидами (Astana Hub, гос-AI, казнет), ловить истории, которые
   «никто пока не заметил» → эксклюзив.
3. **Phase 3:** feedback loop сам крутит веса; генерация картинок; email.

## Границы MVP (осознанные)

- **SQLite** — Postgres-совместимая схема, при росте меняется только `db.py`.
- **KZ RSS-URL** в `sources.py` — предположения, проверь их (scout переживёт
  нерабочий фид). Локальный деск — главный источник differentiation.
- Генерация картинок, загрузка картинок в LinkedIn и impressions LinkedIn — заглушки с чётким местом
  интеграции (Phase 2/3), не забытые куски.
