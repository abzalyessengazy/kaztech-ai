"""
🩺 POLISH — қазақ тілі сапасын тексеретін арзан QA қадамы.

Editor (MODEL_EDITOR, әдетте Opus/Sonnet) жазады, LANGUAGE_QUALITY блогы
кальканы болдырмауға тырысады — бірақ бір LLM шақыруында бәрін бірдей
ұстау қиын. Бұл агент арзан, жылдам модельмен (MODEL_CHECKER, Haiku)
ЖАЗБАЙДЫ — ТЕК ТҮЗЕТЕДІ: мазмұн мен құрылым сақталады, тек тіл дәлденеді.

editor.run() соңында автоматты түрде шақырылады — бастапқы пост үшін де,
Telegram модификаторлары/Edit арқылы регенерация үшін де.
"""
from config import settings
from core import llm

SYSTEM = """Сен — қазақ тілі бойынша қатаң редактор-корректорсың. Мәтінді
ЖАЗБАЙСЫҢ, ТЕК ТҮЗЕТЕСІҢ. Мақсат — табиғи, тірі қазақ тілі, аудармашы
иісі жоқ мәтін.

ІЗДЕ ЖӘНЕ ТҮЗЕТ:
1. КАЛЬКА — орыс/ағылшын синтаксисі тікелей қазақшаға ауыстырылған
   сөйлемдер (сөз тәртібі, септік, байланыстырғыш дұрыс емес). Қазақша
   ойлау тәртібімен қайта құр.
2. Артық ағылшын калька-терминдер немесе термин саясатына қайшы сөздер.
3. Шаблонды/қайталанатын конструкциялар, "AI-generated корпоративтік
   қазақша" сезілетін тіркестер.
4. Ағылшын брендтеріне күштеп жалғанған "пе/ме/ма/ба" сияқты шылаулар.

ЕРЕЖЕ: Фактілерді, мазмұнды, тон режимін (straight/lightly ironic/full
satire), CTA мағынасын САҚТА. Тек тілді дәлдейсің. Егер мәтін бәрібір
жақсы болса — өзгертпе, "changed": false қайтар.

Тек JSON қайтар: {"title": "...", "body": "...", "cta": "...",
"changed": true/false}"""

USER_TEMPLATE = """ТАҚЫРЫП: {title}

МӘТІН:
{body}

CTA: {cta}"""


def run(post: dict) -> dict:
    user = USER_TEMPLATE.format(
        title=post.get("title", ""), body=post.get("body", ""), cta=post.get("cta", ""),
    )
    try:
        fixed = llm.call_json(SYSTEM, user, model=settings.MODEL_CHECKER, max_tokens=900)
    except Exception as exc:
        print(f"[polish] түзету сәтсіз аяқталды, түпнұсқа сақталды: {exc}")
        return post

    for field in ("title", "body", "cta"):
        if fixed.get(field):
            post[field] = fixed[field]
    tag = "түзетілді" if fixed.get("changed") else "өзгеріссіз"
    print(f"[polish] қазақ тілі тексерілді ({tag})")
    return post


if __name__ == "__main__":
    import json
    demo = {"title": "OpenAI тағы да жаңалық шығарды",
            "body": "Бұл жаңа модель бұрынғыдан жылдамырақ жұмыс істейді дейді компания өкілдері.",
            "cta": "Сен қалай ойлайсың?"}
    print(json.dumps(run(demo), ensure_ascii=False, indent=2))
