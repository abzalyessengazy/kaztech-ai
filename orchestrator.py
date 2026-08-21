"""
Оркестратор ньюсрума.

    scout → rules_filter → ranker(batch + judge) → editor(memory+taste)
          → visual → Telegram editor-in-chief → publisher → analytics

AI newsroom каждый день ищет, проверяет, выбирает и готовит ОДНУ историю.
Главред утверждает (или система публикует автономно в --auto).

Флаги: --auto (без аппрува), --dry (ничего не публикует).
"""
import sys

from config import settings
from core import db
from agents import scout, rules_filter, ranker, editor, visual, publisher
from approval import telegram_bot


def run_daily(auto_publish: bool = False):
    db.init_db()
    print("=" * 60)
    print("KAZAKH TECH INTELLIGENCE — ньюсрум, дневной цикл")
    print("=" * 60)

    scout.run()                      # 1. что произошло (global + KZ)
    rules_filter.run()               # 2. дешёвый фильтр: ~20 кандидатов
    story = ranker.run()             # 3. batch scoring + editorial judge → 1 история
    if not story:
        print("[orchestrator] нет истории выше порога. Сегодня пропускаем "
              "(это норма — не RSS-помойка).")
        return

    post = editor.run(story)         # 4. казахский пост + сатира (память+вкус)
    post = visual.run(post)          # 5. фирменный визуал
    post_id = db.save_post(post)     # 6. сохранить

    if auto_publish:                 # 7a. автономная публикация
        print("[orchestrator] AUTO — без ручного аппрува")
        db.set_approval(post_id, 1)
        urn = publisher.publish_post(post_id)
        if urn:
            db.set_status(story["id"], "published")
    else:                            # 7b. интерактивный аппрув в Telegram
        result = telegram_bot.review(story, post, post_id)
        db.set_status(story["id"], "published" if result == "published" else "rejected")

    print("[orchestrator] цикл завершён.")


if __name__ == "__main__":
    if "--dry" in sys.argv:
        settings.DRY_RUN = True
    run_daily(auto_publish="--auto" in sys.argv)
