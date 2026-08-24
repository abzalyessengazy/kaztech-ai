"""
Оркестратор ньюсрума.

    scout → rules_filter → ranker(batch + judge) → editor(memory+taste)
          → visual → Telegram editor-in-chief → publisher → analytics

AI newsroom каждый день ищет, проверяет, выбирает и готовит ОДНУ историю.
Главред утверждает (или система публикует автономно в --auto). Если главред
явно жалт («Reject»), келесі үздік финалист автоматты түрде ұсынылады.
Ойланбай қалдырса («timeout»), бұл reject деп есептелмейді — цикл сол жерде
тоқтайды, история "rejected" емес "timeout" деп белгіленеді.

Флаги: --auto (без аппрува), --dry (ничего не публикует).
"""
import sys

from config import settings
from core import db
from agents import scout, rules_filter, ranker, editor, visual, publisher, telegram_channel
from approval import telegram_bot


def _next_finalist(exclude_ids: list[int]):
    """Следующий по editorial score финалист, ещё не предложенный сегодня."""
    placeholders = ",".join("?" for _ in exclude_ids) or "0"
    query = (f"SELECT * FROM news WHERE status='finalist' AND id NOT IN ({placeholders}) "
             "ORDER BY editorial DESC LIMIT 1")
    with db.connect() as conn:
        row = conn.execute(query, exclude_ids).fetchone()
        return dict(row) if row else None


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

    tried_ids: list[int] = []
    while story:
        tried_ids.append(story["id"])
        post = editor.run(story)         # 4. казахский пост + сатира (память+вкус)
        post = visual.run(post)          # 5. фирменный визуал
        post_id = db.save_post(post)     # 6. сохранить

        if auto_publish:                 # 7a. автономная публикация
            print("[orchestrator] AUTO — без ручного аппрува")
            db.set_approval(post_id, 1)
            urn = publisher.publish_post(post_id)
            channel_message_id = telegram_channel.publish_post(post_id)
            if urn or channel_message_id:
                db.set_status(story["id"], "published")
            break

        result = telegram_bot.review(story, post, post_id)  # 7b. интерактивный аппрув
        if result == "published":
            db.set_status(story["id"], "published")
            break
        if result == "timeout":
            # Молчание — вердикт емес: reject деп есептемей, цикл осында тоқтайды.
            db.set_status(story["id"], "timeout")
            break

        # Нақты Reject — келесі үздік финалистті ұсынамыз.
        db.set_status(story["id"], "rejected")
        story = _next_finalist(tried_ids)
        if story:
            print(f"[orchestrator] қабылданбады — келесі үздік ұсынылады: "
                  f"{story['original_title'][:60]}")
        else:
            print("[orchestrator] қабылданбады — бүгінге басқа финалист жоқ.")

    print("[orchestrator] цикл завершён.")


if __name__ == "__main__":
    if "--dry" in sys.argv:
        settings.DRY_RUN = True
    run_daily(auto_publish="--auto" in sys.argv)
