"""
✍️ EDITOR — казахский пост + сатира, с памятью и вкусом главреда.

Перед письмом получает:
  · MEMORY  — посты, которые зашли (обучаемый стиль, не статический prompt);
  · RECENT  — недавние темы (чтобы не повторяться);
  · TASTE   — накопленный вкус главреда из кнопок Telegram.

Поддерживает модификаторы (spicier / more_kazakh / less_satire / regenerate)
и произвольную ручную инструкцию главреда (кнопка Edit в Telegram) —
так главред обучает редактора вкусу, не написав ни одного промпта.
"""
import json
import re

from config import settings
from config import style_guide
from core import llm, db

USER_TEMPLATE = """Бүгінгі басты история:

БАСЫ: {title}
ҚЫСҚАША: {summary}
ДЕРЕККӨЗ: {source_name}
ТЕМА: {theme}

Осыдан қысқа, таза құрылымды LinkedIn посты жаса. Тек JSON қайтар:
{{
    "title": "табиғи қазақша қысқа тақырып, орысша калькасыз, эмодзисіз",
    "body": "POST ҚҰРЫЛЫМЫН сақта: 3-4 қысқа абзац, ~90-140 сөз, табиғи қазақша, орысша сөйлем/тіркес қоспа",
  "image_prompt": "Visual Agent үшін ағылшынша сурет идеясы",
    "satire_note": "таңдалған тон режимі (straight/lightly ironic/full satire) және неге, 1 қысқа сөйлеммен",
    "cta": "LinkedIn-ге лайық қазақша 1 қысқа сұрақ; түйме/сілтеме туралы айтпа",
  "theme": "{theme}"
}}
Міндетті тексеріс: body LinkedIn-де оқуға жеңіл болуы керек; әр абзац бөлек ой айтсын.
Тілдік тексеріс: ағылшын брендтеріне "пе/ме/ма/ба" сияқты шылауларды күштеп жалғама; күмән болса сөйлемді қайта құр.
{modifier}"""


BRAND_PARTICLE_FIXES = {
    "ChatGPT пе": "ChatGPT ме",
    "ChatGPT па": "ChatGPT ме",
    "Gemini пе": "Gemini ме",
    "Claude па": "Claude ма",
    "OpenAI ма": "OpenAI ме",
}


def _polish_known_kazakh_issues(text: str) -> str:
    for bad, good in BRAND_PARTICLE_FIXES.items():
        text = re.sub(rf"\b{re.escape(bad)}\b", good, text)
    return text


def _polish_post(post: dict) -> dict:
    for key in ("title", "body", "cta", "satire_note"):
        if isinstance(post.get(key), str):
            post[key] = _polish_known_kazakh_issues(post[key])
    return post


def _system() -> str:
    return style_guide.build_editor_system_prompt(
        memory=db.successful_posts(3),
        recent=db.recent_published(5),
        taste=style_guide.taste_directive(db.taste_counts()),
    )


def run(story: dict, modifier: str | None = None, custom_instruction: str | None = None) -> dict:
    """story — строка news (dict). modifier — ключ из MODIFIER_DIRECTIVES.
    custom_instruction — свободный текст главреда (кнопка Edit в Telegram)."""
    mod_line = ""
    if modifier and modifier in style_guide.MODIFIER_DIRECTIVES:
        mod_line = "\nМАҢЫЗДЫ ТҮЗЕТУ: " + style_guide.MODIFIER_DIRECTIVES[modifier]
    if custom_instruction:
        mod_line += f"\nГЛАВРЕДТІҢ НАҚТЫ СҰРАНЫСЫ (міндетті түрде орында): {custom_instruction}"

    user = USER_TEMPLATE.format(
        title=story.get("original_title") or story.get("title", ""),
        summary=story.get("original_summary") or story.get("summary", ""),
        source_name=story.get("source_name", ""),
        theme=story.get("theme", ""),
        modifier=mod_line,
    )

    # A truncated/short LLM response can otherwise silently ship a post with
    # a title but no body — retry a couple of times before accepting it.
    post = None
    candidate = {}
    for attempt in range(3):
        candidate = llm.call_json(_system(), user, model=settings.MODEL_EDITOR, max_tokens=2400)
        candidate = _polish_post(candidate)
        if len((candidate.get("body") or "").strip()) >= 40 and (candidate.get("title") or "").strip():
            post = candidate
            break
        print(f"[editor] бос/тым қысқа нәтиже (попытка {attempt + 1}/3), қайта сұраймыз...")
    post = post or candidate

    post["news_id"] = story["id"]
    post["source_name"] = story.get("source_name", "")
    post["source_url"] = story.get("source_url", "")
    post.setdefault("theme", story.get("theme", ""))
    for k in ("title", "body", "image_prompt", "satire_note", "cta"):
        post.setdefault(k, "")
    tag = f" ({modifier})" if modifier else (" (custom edit)" if custom_instruction else "")
    print(f"[editor]{tag} пост готов: {post['title'][:55]}")
    return post


if __name__ == "__main__":
    demo = {"id": 0, "original_title": "OpenAI releases a new coding model",
            "original_summary": "Beats junior devs on benchmarks.",
            "source_name": "OpenAI", "source_url": "https://x", "theme": "new-model"}
    print(json.dumps(run(demo), ensure_ascii=False, indent=2))
