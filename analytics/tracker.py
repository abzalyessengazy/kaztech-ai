"""
📊 ANALYTICS + FEEDBACK LOOP

Собирает вовлечённость постов и подсказывает ранкеру, какие ТЕМЫ заходят.
Через 100–200 постов появляется editorial intelligence:
  🇰🇿 Kazakhstan relevance = очень ценно, 🤖 generic AI release = слабо.

collect() — место интеграции LinkedIn socialActions (заглушка нулями).
theme_report() уже работает на данных БД.
"""
from core import db


def collect(post_id: int, urn: str):
    """TODO: GET /v2/socialActions/{urn} → likes/comments; org stats → impressions."""
    likes, comments, impressions = 0, 0, 0
    db.save_analytics(post_id, urn, likes, comments, impressions)
    print(f"[analytics] метрики поста {post_id} сохранены (заглушка)")


def theme_report() -> dict:
    """Feedback loop: рейтинг тем + вкус главреда."""
    themes = db.theme_engagement()
    taste = db.taste_counts()
    if not themes:
        report = {"note": "мало данных — публикуй ещё (цель: 30 дней = 30 постов)"}
    else:
        report = {
            "best_theme": themes[0]["theme"],
            "weak_theme": themes[-1]["theme"],
            "themes": themes,
            "hint": f"Тема «{themes[0]['theme']}» заходит лучше всего — ранкер уже "
                    "поднимает её через theme_engagement().",
        }
    report["editor_taste"] = taste
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(theme_report(), ensure_ascii=False, indent=2))
