"""
Оркестратор ньюсрума.

    scout → rules_filter → ranker(batch scoring, топ-5)
          → Telegram: главред таңдайды 1-уін → editor(memory+taste)
          → visual → Telegram editor-in-chief → publisher → analytics

AI newsroom каждый день ищет, проверяет и готовит топ-5 финалистов.
Главред таңдайды біреуін Telegram-да (немесе --auto режимінде жүйе ең
жоғары score-ты автоматты алады). Таңдалған история әдеттегі
Publish/Regenerate/Edit/Reject циклінен өтеді. Reject болса — қалған
финалисттерден главред қайта таңдайды (автоматты «келесі үздік» жоқ).
Ойланбай қалдырса («timeout»), бұл reject деп есептелмейді.

Флаги: --auto (без аппрува, ең жоғары score автоматты), --dry (ничего не публикует).
"""
import sys

from config import settings
from core import db
from agents import scout, rules_filter, ranker, editor, visual, publisher, telegram_channel
from approval import telegram_bot


def run_daily(auto_publish: bool = False):
    db.init_db()
    print("=" * 60)
    print("KAZAKH TECH INTELLIGENCE — ньюсрум, дневной цикл")
    print("=" * 60)

    scout.run()                      # 1. что произошло (global + KZ)
    rules_filter.run()               # 2. дешёвый фильтр: ~20 кандидатов
    finalists = ranker.run()         # 3. batch scoring → топ-5 финалистов
    if not finalists:
        print("[orchestrator] нет финалистов выше порога. Сегодня пропускаем "
              "(это норма — не RSS-помойка).")
        return

    if auto_publish:
        story = finalists[0]         # ең жоғары editorial score — judge жоқ
    else:
        story = telegram_bot.choose_story(finalists)   # 4. главред таңдайды
        if not story:
            print("[orchestrator] главред таңдамады — бүгін өткіздік.")
            return
    db.set_status(story["id"], "chosen")

    tried_ids: list[int] = []
    while story:
        tried_ids.append(story["id"])
        post = editor.run(story)         # 5. казахский пост + сатира (память+вкус)
        post = visual.run(post)          # 6. фирменный визуал
        post_id = db.save_post(post)     # 7. сохранить

        if auto_publish:                 # 8a. автономная публикация
            print("[orchestrator] AUTO — без ручного аппрува")
            db.set_approval(post_id, 1)
            urn = publisher.publish_post(post_id)
            channel_message_id = telegram_channel.publish_post(post_id)
            if urn or channel_message_id:
                db.set_status(story["id"], "published")
            break

        result = telegram_bot.review(story, post, post_id)  # 8b. интерактивный аппрув
        if result == "published":
            db.set_status(story["id"], "published")
            break
        if result == "timeout":
            # Молчание — вердикт емес: reject деп есептемей, цикл осында тоқтайды.
            db.set_status(story["id"], "timeout")
            break

        # Нақты Reject — қалған финалисттерден главред қайта таңдайды.
        db.set_status(story["id"], "rejected")
        remaining = [f for f in finalists if f["id"] not in tried_ids]
        if not remaining:
            print("[orchestrator] қабылданбады — бүгінге басқа финалист жоқ.")
            break
        story = telegram_bot.choose_story(remaining)
        if story:
            db.set_status(story["id"], "chosen")
            print(f"[orchestrator] жаңа тарих таңдалды: {story['original_title'][:60]}")
        else:
            print("[orchestrator] жаңа тарих таңдалмады — бүгін өткіздік.")

    print("[orchestrator] цикл завершён.")


if __name__ == "__main__":
    if "--dry" in sys.argv:
        settings.DRY_RUN = True
    run_daily(auto_publish="--auto" in sys.argv)
