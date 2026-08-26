# 🇰🇿 Kazakh Tech Intelligence — қазақ тіліндегі AI редакциясы

Бұл **жаңалықтар порталы емес**. Бұл — редакция: AI newsroom жаңалықтарды іздейді,
тексереді, бағалайды және таңдауға **бес оқиғаға дейін** дайындайды. Бас редактор
(адам) біреуін таңдап, соңғы постты бекітеді.
*TechCrunch × The Onion × қазақ интернет-мәдениеті.*

Рөлдер: жүйе — **newsroom**, сіз — **бас редактор**.

---

## Пайплайн (2-кезең)

```
        INTERNET (Global desk + 🇰🇿 KZ desk)
                     │
              🛰️ SCOUT  ──────► News Inbox (дереккөз әрдайым сақталады)
                     │
              🧹 RULES FILTER ─► ~20 кандидат (LLM-сыз: керексізді сүзу, дедуп, local/global 50/50)
                     │
              🧠 RANKER ───────► топтап бағалау → 5 финалистке дейін → бас редактор 1 оқиғаны таңдайды
                     │              ▲ тақырыптар бойынша кері байланыс
              ✍️ EDITOR ───────► қазақша мәтін + сатира (+ MEMORY + бас редактор талғамы)
                     │
              🎨 VISUAL ───────► фирмалық визуал
                     │
              👨‍💼 TELEGRAM ────► ✅Publish ✏️Regenerate 🔥Spicier 🇰🇿MoreKZ 📰LessSatire ❌Reject
                     │
              🚀 PUBLISHER ────► LinkedIn (+ 🔗 Дереккөз: сілтеме)
                     │
              📊 ENGAGEMENT ───► MEMORY ──► RANKER-ге кері
```

## 2-кезеңдегі жаңалықтар

| Жақсарту | Қайда | Не үшін |
|---|---|---|
| **Дереккөз әрдайым бар** | `scout`, `publisher` | сенім және «AI ойдан шығарды» қатесінен қорғаныс; постта `🔗 Дереккөз:` көрсетіледі |
| **Екі сатылы ranker** | `rules_filter` + `ranker` | «Apple жаңа эмодзи шығарды» сияқты жаңалықтарға LLM токенін жұмсамау; таңдауға 5 нұсқаға дейін беру |
| **EDITORIAL MEMORY** | `db.successful_posts` → `editor` | стиль сәтті шыққан контенттен үйренеді |
| **Кері байланыс циклі** | `db.theme_engagement` → `ranker` | ранкер 🇰🇿+AI тақырыптарының құнын, ал жалпы AI жаңалықтарының әлсіздігін ескереді |
| **Толық Telegram басқаруы** | `telegram_bot` | промпт жазбай-ақ редакторлық талғамды үйрету |
| **Дереккөздер теңгерімі** | `rules_filter`, `sources.py` | 10 жергілікті + 10 жаһандық орын; Anthropic/Claude Google News RSS арқылы жиналады |
| **Үш күндік терезе** | `core/db.py` | жақсы, бірақ таңдалмаған оқиғалар қайта ұсынылады; ескіргендері жиналмайды |
| **Редакциялық тәсіл** | барлық жерде | «AI жаңалық жазады» емес, «редакция оқиғаны дайындайды» |

## Құрылымы

```
config/
  settings.py        env конфигурациясы
  sources.py         GLOBAL_SOURCES + KZ_SOURCES + керексіз контент сүзгісі
  style_guide.py     🔑 ДНҚ: дауыс, терминдер, сатира + MEMORY/TASTE енгізуі
core/
  db.py              news / posts / analytics / taste_feedback + жад, тақырыптар
  llm.py             Anthropic API
agents/
  scout.py           global + KZ жинау, дереккөзді сақтау
  rules_filter.py    LLM-сыз бастапқы арзан сүзгі
  ranker.py          топтап бағалау + бас редакторға 5 финалистке дейін ұсыну
  editor.py          қазақша мәтін + сатира + жад + талғам + модификаторлар
  visual.py          визуал промпты (+ генерацияға арналған хук)
  publisher.py       LinkedIn + дереккөз жолы
approval/
  telegram_bot.py    оқиғаны таңдау + Publish / Regenerate / Spicier / More KZ / Less satire / Edit / Reject
analytics/
  tracker.py         метрикалар + тақырыптар есебі
orchestrator.py      күнделікті цикл
scheduler.py         scout әр 3 сағатта / newsroom Asia/Almaty cron кестесімен
```

## Жылдам бастау

```bash
pip install -r requirements.txt
cp .env.example .env          # міндетті ANTHROPIC_API_KEY мәнін жазыңыз
python orchestrator.py --dry  # жариялаусыз толық цикл
```

Әдепкіде `DRY_RUN=1`: жүйе жинайды, сүзеді, бағалайды, пост жазады және соңғы
мәтінді көрсетеді, бірақ **жарияламайды**. Бұл дауысты қауіпсіз тексеруге ыңғайлы.

### Кілттер

| Кілт | Мақсаты |
|---|---|
| `ANTHROPIC_API_KEY` | бағалау және редакциялау үшін (міндетті) |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | батырмалар арқылы бекіту |
| `TELEGRAM_CHANNEL_ID` | бекітілген посттар жарияланатын арна (`@name` не `-100...`) |
| `TELEGRAM_CHANNEL_ENABLED` | `1` — Telegram арнасына жариялау, `0` — өткізіп жіберу |
| `LINKEDIN_ENABLED` | `1` — LinkedIn-ге жариялау, `0` — өткізіп жіберу |
| `LINKEDIN_ACCESS_TOKEN` + `LINKEDIN_AUTHOR_URN` | нақты LinkedIn жарияланымы |
| `LINKEDIN_VISIBILITY` | посттың `PUBLIC` не `CONNECTIONS` көрінуі |
| `NEWSROOM_INTERVAL_HOURS` | `0` — күн сайын 09:00; `6` — Asia/Almaty уақытымен 09:00, 15:00, 21:00 |
| `CANDIDATE_MAX_AGE_DAYS` | оқиғаның редакциялық пулда сақталу күні; әдепкіде `3` |

## Іске қосу режимдері

```bash
python orchestrator.py          # Telegram арқылы бекітумен
python orchestrator.py --auto   # автономды режим (жүйеге сенім артқанда)
python orchestrator.py --dry    # ештеңе жарияламайды
python -m agents.scout          # тек жинау
python -m agents.rules_filter   # тек сүзу
python -m unittest discover -s tests  # сыртқы API-сыз smoke тесттері
python linkedin_setup_check.py  # LinkedIn token/author URN мәндерін жариялаусыз тексеру
python -m analytics.tracker     # тақырыптар есебі + бас редактор талғамы
python scheduler.py             # кестені үздіксіз ұстау
```

## Өндірістік орта

LinkedIn Page API рұқсаты күтіліп тұрған кездегі ұсынылатын MVP режимі:

```env
DRY_RUN=0
LINKEDIN_ENABLED=0
TELEGRAM_CHANNEL_ENABLED=1
SCOUT_MAX_ITEMS=8
MODEL_EDITOR=claude-sonnet-5
NEWSROOM_INTERVAL_HOURS=6  # Asia/Almaty: 09:00, 15:00, 21:00
CANDIDATE_MAX_AGE_DAYS=3
```

Үздіксіз жұмыс істейтін воркерді іске қосу:

```bash
python scheduler.py
```

Контейнерлік хосттарда бірге берілген `Dockerfile` қолдануға болады: контейнер
`scheduler.py` файлын іске қосады. Құпиясөздер мен токендерді git-ке емес, хост
басқару панеліне жазыңыз. Қайта жүктеуден кейін `kaztech.db` тарихы сақталсын
десеңіз, тұрақты диск не volume қосыңыз.

## Талғам қалай үйренеді

Telegram батырмалары сигналдарды `taste_feedback` кестесіне жазады. Мысалы,
🔥 Spicier батырмасын 20 рет бассаңыз, `taste_directive()` редактор промптына
«бұл бас редактор батыл сатираны ұнатады» деген нұсқауды қосады. Стиль промптты
қайта жазбай-ақ сіздің талғамыңызға бейімделеді.

## Жол картасы

1. **Қазір:** жүйені автономды редакцияға жеткізу. **Мақсат — 30 күнде 30 пост.**
   30 посттан кейін алынатын түсінік тағы бір айлық әзірлеуден пайдалырақ.
2. **2-кезең — қазақстандық контент:** `KZ_SOURCES` тізімін нақты фидтермен
   (Astana Hub, мемлекеттік AI, қазақ интернеті) толықтырып, әлі ешкім байқамаған
   оқиғаларды ұстау.
3. **3-кезең:** кері байланыс циклі салмақтарды өзі баптайды; сурет генерациясы
   және email қосылады.

## MVP шектеулері

- **SQLite** — Postgres-пен үйлесімді схема; өсу кезінде тек `db.py` қабатын
  ауыстыру жеткілікті.
- `sources.py` ішіндегі **KZ RSS URL** мекенжайлары болжамды. Оларды тексеріп,
  жаңартып отырыңыз; бір фид істемесе, scout қалғанымен жұмысын жалғастырады.
- Сурет генерациясы, LinkedIn-ге сурет жүктеу және LinkedIn impressions деректері
  интеграцияға арналған анық нүктелері бар уақытша шешімдер.
