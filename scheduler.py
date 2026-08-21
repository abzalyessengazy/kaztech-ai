"""
Планировщик ньюсрума.

  scout            — каждые 3 часа (копим инбокс)
  дневной цикл     — 09:00 Asia/Almaty (фильтр→ранк→редактура→аппрув)

Запуск:  python scheduler.py   (держи процесс живым: screen/tmux/systemd)
"""
from apscheduler.schedulers.blocking import BlockingScheduler

from agents import scout
from orchestrator import run_daily

sched = BlockingScheduler(timezone="Asia/Almaty")


@sched.scheduled_job("interval", hours=3, id="scout")
def scout_job():
    print("⏰ scout (каждые 3 часа)")
    scout.run()


@sched.scheduled_job("cron", hour=9, minute=0, id="daily")
def daily_job():
    print("⏰ дневной цикл (09:00 Almaty)")
    run_daily(auto_publish=False)


if __name__ == "__main__":
    print("Планировщик ньюсрума запущен. Ctrl+C — стоп.")
    print("  · scout — каждые 3 часа")
    print("  · история дня + аппрув — 09:00 Asia/Almaty")
    sched.start()
