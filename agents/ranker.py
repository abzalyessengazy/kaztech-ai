"""
🧠 RANKER — двухступенчатый.

    ~20 кандидатов
         ↓  batch LLM scoring (один вызов, дёшево)
    5 финалистов
         ↓  editorial judge (один вызов)
    1 история дня  + theme

Feedback loop: ранкеру передаётся theme_engagement() — какие темы уже
дают вовлечённость. Через 100–200 постов появляется собственная
editorial intelligence (Kazakhstan relevance = очень ценно, generic AI = слабо).
"""
import json
import re

from config import settings, sources
from core import db, llm
from agents import rules_filter

WEIGHTS = {
    "importance": 0.20, "novelty": 0.15, "kz_relevance": 0.25,
    "ai_relevance": 0.15, "virality": 0.15, "satire_potential": 0.10,
}
N_FINALISTS = 5


def _theme_hint() -> str:
    rows = db.theme_engagement()
    if not rows:
        return "Тарихи мәлімет жоқ (әлі жаңа). Локалдық және бизнес-әсер тақырыптарын жоғары баста."
    top = ", ".join(f"{r['theme']} (~{round(r['score'],1)})" for r in rows[:5])
    return f"Осы уақытқа дейін ең жақсы тартқан тақырыптар: {top}. Соларды жоғарырақ баста."


def _editorial(s: dict, source_weight: float) -> float:
    base = sum(s[k] * WEIGHTS[k] for k in WEIGHTS)
    return round(min(10.0, base * (0.9 + 0.1 * source_weight)), 2)


SCORE_SYSTEM = f"""Сен — қазақстандық AI/Tech ньюсрумның редакциялық аналитигісің.
Аудитория: IT, data, AI, бизнес, кәсіпкерлер, ҚР мамандары мен басшылары.
Локалдық белгілер (болса kz_relevance жоғары): {", ".join(sources.KAZAKH_RELEVANCE_HINTS[:8])}.

Әр жаңалыққа баға бер (0–10) және JSON МАССИВІН қайтар, элемент:
{{"id": <id>, "importance":0-10, "novelty":0-10, "kz_relevance":0-10,
 "ai_relevance":0-10, "virality":0-10, "satire_potential":0-10,
 "theme":"қысқа тег: kz-local|startup|new-model|business-impact|ai-tooling|research|culture",
 "reason":"қысқа себеп, макс 10 сөз"}}
Маңызды: "reason" өрісін қысқа ұста (10 сөзден аспасын) — JSON толық аяқталуы керек, кесілмеу керек."""


def _score_batch(candidates: list[dict]) -> list[dict]:
    listing = "\n".join(
        f'id={c["id"]} | {c["original_title"]} | {c.get("original_summary","")[:160]} '
        f'| дереккөз: {c["source_name"]}{" | ЛОКАЛ" if c["is_local"] else ""}'
        for c in candidates
    )
    user = f"{_theme_hint()}\n\nКандидаттар:\n{listing}"
    # ~180 tokens/candidate is a safe ceiling for id+scores+short reason; floor at 4000
    # so a truncated response (and a silent empty-list fallback) doesn't happen.
    max_tokens = max(4000, len(candidates) * 180)
    resp = llm.call_text(
        SCORE_SYSTEM + "\n\nТек JSON массив қайтар.", user,
        model=settings.MODEL_RANKER, max_tokens=max_tokens, temperature=0.2,
    )
    resp = resp.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(resp)
    except json.JSONDecodeError:
        pass

    m = re.search(r"\[.*\]", resp, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Бір объект бүлінген болса (мыс. моделдің кездейсоқ типо-глитчі), бүкіл
    # batch-ты тастамай, объект бойынша жеке парстаймыз — жарамдылары
    # сақталады, тек бүлінгені ғана жоғалады.
    salvaged = []
    for obj in re.finditer(r"\{[^{}]*\}", resp):
        try:
            salvaged.append(json.loads(obj.group(0)))
        except json.JSONDecodeError:
            continue
    if salvaged:
        print(f"[rank] ⚠️ batch JSON ішінара бүлінген — {len(salvaged)} объект сақталды "
              f"(жалпы ұзындық {len(resp)} белгі).")
        return salvaged

    print(f"[rank] ⚠️ batch scoring JSON парсинг сәтсіз (ұзындығы {len(resp)} белгі, "
          f"соңы: ...{resp[-120:]!r}) — 0 кандидат бағаланды.")
    return []


JUDGE_SYSTEM = """Сен — бас редактордың орынбасарысың. Финалистерден БІР ғана
бүгінгі басты история таңда. Критерий: қазақстандық аудиторияға құндылық,
бизнес-әсер, сатира әлеуеті, жаңалық. Тек JSON: {"winner_id": <id>, "theme": "тег", "why": "1-2 сөйлем"}"""


def _judge(finalists: list[dict]) -> dict:
    listing = "\n".join(
        f'id={f["id"]} | score={f["editorial"]} | theme={f["theme"]} | {f["original_title"]} | {f["rank_reason"]}'
        for f in finalists
    )
    return llm.call_json(JUDGE_SYSTEM, listing, model=settings.MODEL_EDITOR, max_tokens=400)


def run():
    """Возвращает выбранную историю (dict) или None."""
    used_tokens = rules_filter._used_tokens()
    candidates = [
        c for c in db.get_candidates(limit=settings.SCOUT_MAX_ITEMS)
        if not rules_filter._is_used_duplicate(c["original_title"], used_tokens)
    ]
    if not candidates:
        print("[rank] нет кандидатов (сначала фильтр).")
        return None

    # Ступень 1 — batch scoring.
    by_id = {c["id"]: c for c in candidates}
    scored = _score_batch(candidates)
    scored_ids = set()
    for s in scored:
        cid = int(s.get("id", -1))
        if cid not in by_id:
            continue
        scored_ids.add(cid)
        for k in WEIGHTS:
            s[k] = float(s.get(k, 0))
        s["editorial"] = _editorial(s, by_id[cid].get("source_weight", 1.0))
        db.save_ranking(cid, s)
    print(f"[rank] оценено {len(scored)} кандидатов (1 batch-вызов)")

    # LLM-нен өткен жоқ (парсинг сәтсіз болғандар) — 'candidate' күйінде
    # мәңгі қалып, әр келесі ranker.run() шақыруында қайта-қайта жіберілмесін.
    missed = set(by_id) - scored_ids
    if missed:
        for cid in missed:
            db.set_status(cid, "dropped")
        print(f"[rank] LLM пропустил {len(missed)} кандидатов — помечены dropped "
              "(иначе зависли бы в 'candidate' навсегда)")

    # Ступень 2 — editorial judge среди финалистов.
    finalists = db.get_finalists(N_FINALISTS, settings.MIN_EDITORIAL_SCORE)
    if not finalists:
        print(f"[rank] нет финалистов выше порога {settings.MIN_EDITORIAL_SCORE}.")
        return None
    for f in finalists:
        db.set_status(f["id"], "finalist")
    print("[rank] финалисты:")
    for f in finalists:
        print(f"   {f['editorial']:>4}  [{f['theme']}]  {f['original_title'][:55]}")

    verdict = _judge(finalists)
    winner = db.get_news(int(verdict.get("winner_id", finalists[0]["id"])))
    if not winner:
        winner = finalists[0]
    if verdict.get("theme"):
        winner["theme"] = verdict["theme"]
    winner["selection_reason"] = verdict.get("why", "")
    db.set_status(winner["id"], "chosen")
    print(f"[rank] 🏆 история дня: {winner['original_title'][:60]}")
    print(f"       почему: {verdict.get('why','')}")
    return winner


if __name__ == "__main__":
    run()
