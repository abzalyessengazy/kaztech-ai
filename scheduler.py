"""
Планировщик ньюсрума.

  scout            — каждые 3 часа (копим инбокс)
  дневной цикл     — 09:00 Asia/Almaty (фильтр→ранк→редактура→аппрув)

Запуск:  python scheduler.py   (держи процесс живым: screen/tmux/systemd)
"""
from apscheduler.schedulers.blocking import BlockingScheduler

from config import settings
from agents import scout
from orchestrator import run_daily

sched = BlockingScheduler(timezone="Asia/Almaty")


@sched.scheduled_job("interval", hours=settings.SCOUT_INTERVAL_HOURS, id="scout")
def scout_job():
    print(f"⏰ scout (каждые {settings.SCOUT_INTERVAL_HOURS} часа)")
    scout.run()


def daily_job():
    label = (f"каждые {settings.NEWSROOM_INTERVAL_HOURS} часа"
             if settings.NEWSROOM_INTERVAL_HOURS else "09:00 Almaty")
    print(f"⏰ дневной цикл ({label})")
    run_daily(auto_publish=False)


if settings.NEWSROOM_INTERVAL_HOURS:
    sched.add_job(daily_job, "interval", hours=settings.NEWSROOM_INTERVAL_HOURS,
                  id="daily", replace_existing=True)
else:
    sched.add_job(daily_job, "cron", hour=9, minute=0, id="daily", replace_existing=True)


if __name__ == "__main__":
    print("Планировщик ньюсрума запущен. Ctrl+C — стоп.")
    print(f"  · scout — каждые {settings.SCOUT_INTERVAL_HOURS} часа")
    if settings.NEWSROOM_INTERVAL_HOURS:
        print(f"  · история + аппрув — каждые {settings.NEWSROOM_INTERVAL_HOURS} часа")
    else:
        print("  · история дня + аппрув — 09:00 Asia/Almaty")
    sched.start()
