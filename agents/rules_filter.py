"""
🧹 RULES FILTER — дешёвая ступень 0 (без LLM).

    100 статей → правила → ~20 кандидатов

Зачем: не жечь LLM-токены на «Apple выпустила новый эмодзи». Отсекает
мусор по денилисту, схлопывает дубликаты одной истории из разных
источников, приоритезирует локальные истории.

    inbox → candidate  (прошло)
    inbox → dropped    (мусор/дубль)
"""
from config import sources
from core import db

MAX_CANDIDATES = 20
USED_DUPLICATE_THRESHOLD = 0.55


def _is_junk(title: str) -> bool:
    t = title.lower()
    return any(p in t for p in sources.JUNK_PATTERNS)


def _is_local(item: dict) -> bool:
    if item.get("is_local"):
        return True
    blob = f"{item['original_title']} {item.get('original_summary','')}".lower()
    return any(h in blob for h in sources.KAZAKH_RELEVANCE_HINTS)


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _used_tokens() -> list[set]:
    return [
        set(db.normalize_title(item["original_title"]).split())
        for item in db.get_used_news()
        if item.get("original_title")
    ]


def _is_used_duplicate(title: str, used_tokens: list[set]) -> bool:
    tokens = set(db.normalize_title(title).split())
    return any(_jaccard(tokens, used) > USED_DUPLICATE_THRESHOLD for used in used_tokens)


def _cheap_score(item: dict, local: bool) -> float:
    """Грубый приоритет для отбора топ-N без LLM."""
    score = item.get("source_weight", 1.0)
    if local:
        score += 1.5                     # локальность — главный дифференциатор
    if len(item["original_title"]) > 40:
        score += 0.2                     # не заголовок-обрубок
    return score


def run() -> dict:
    inbox = db.get_inbox(limit=200)
    dropped_junk, dropped_used, kept = 0, 0, []
    used_tokens = _used_tokens()

    for item in inbox:
        title = item["original_title"]
        if _is_junk(title):
            db.set_status(item["id"], "dropped")
            dropped_junk += 1
            continue

        if _is_used_duplicate(title, used_tokens):
            db.set_status(item["id"], "dropped")
            dropped_used += 1
            continue

        # Дедуп: та же история из другого источника — оставляем сильнейший источник.
        tokens = set(db.normalize_title(title).split())
        dup_of = next((k for k in kept if _jaccard(tokens, k["tokens"]) > 0.6), None)
        if dup_of:
            if item.get("source_weight", 1) > dup_of["item"].get("source_weight", 1):
                db.set_status(dup_of["item"]["id"], "dropped")
                dup_of["item"], dup_of["tokens"] = item, tokens
            else:
                db.set_status(item["id"], "dropped")
            continue

        local = _is_local(item)
        kept.append({"item": item, "tokens": tokens,
                     "score": _cheap_score(item, local), "local": local})

    # Топ-N кандидатов, локальные — вперёд.
    kept.sort(key=lambda k: (k["local"], k["score"]), reverse=True)
    promoted = kept[:MAX_CANDIDATES]
    for k in promoted:
        db.set_status(k["item"]["id"], "candidate")
    for k in kept[MAX_CANDIDATES:]:
        db.set_status(k["item"]["id"], "dropped")

    n_local = sum(1 for k in promoted if k["local"])
    print(f"[filter] инбокс {len(inbox)} → кандидатов {len(promoted)} "
          f"(локальных {n_local}), мусор {dropped_junk}, уже было {dropped_used}")
    return {"inbox": len(inbox), "candidates": len(promoted), "local": n_local,
            "used_duplicates": dropped_used}


if __name__ == "__main__":
    run()
