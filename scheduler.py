"""
Планировщик ньюсрума.

  scout            — каждые 3 часа (копим инбокс)
  дневной цикл     — 09:00 Asia/Almaty (фильтр→ранк→редактура→аппрув)

Запуск:  python scheduler.py   (держи процесс живым: screen/tmux/systemd)
"""
import logging
import sys

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
from apscheduler.schedulers.blocking import BlockingScheduler

from config import settings
from agents import scout
from orchestrator import run_daily

# Render (and most log collectors) capture stdout as a pipe, which Python
# block-buffers by default — print()s (including the whole 30-min Telegram
# approval wait) wouldn't reach live logs until the buffer fills or the
# process exits. Line-buffer instead so logs stay real-time.
sys.stdout.reconfigure(line_buffering=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scheduler")

# max_instances=1 (default) means a hung job silently blocks all future runs of
# itself — misfire_grace_time/coalesce keep a late run from being dropped instead
# of at least logged, and the listeners below make a stuck/hanging job visible.
sched = BlockingScheduler(
    timezone="Asia/Almaty",
    job_defaults={"misfire_grace_time": 3600, "coalesce": True, "max_instances": 1},
)


def _on_job_event(event):
    if event.code == EVENT_JOB_MISSED:
        logger.warning("Run time of job %r was missed (scheduled for %s)", event.job_id, event.scheduled_run_time)
    elif event.code == EVENT_JOB_ERROR:
        logger.error("Job %r raised an exception: %s", event.job_id, event.exception, exc_info=event.exception)


sched.add_listener(_on_job_event, EVENT_JOB_ERROR | EVENT_JOB_MISSED)


@sched.scheduled_job("interval", hours=settings.SCOUT_INTERVAL_HOURS, id="scout")
def scout_job():
    print(f"⏰ scout (каждые {settings.SCOUT_INTERVAL_HOURS} часа)")
    scout.run()


# "interval" trigger anchors to process start time, not wall-clock — it drifts on
# every restart. Use fixed cron hours (starting at 09:00) so runs stay pinned.
DAILY_HOURS = sorted({(9 + step) % 24 for step in range(0, 24, settings.NEWSROOM_INTERVAL_HOURS)}) \
    if settings.NEWSROOM_INTERVAL_HOURS else [9]


def daily_job():
    label = ", ".join(f"{hour:02d}:00" for hour in DAILY_HOURS) if settings.NEWSROOM_INTERVAL_HOURS else "09:00 Almaty"
    print(f"⏰ дневной цикл ({label})")
    run_daily(auto_publish=False)


for hour in DAILY_HOURS:
    sched.add_job(daily_job, "cron", hour=hour, minute=0,
                  id=f"daily_{hour}", replace_existing=True)


if __name__ == "__main__":
    print("Планировщик ньюсрума запущен. Ctrl+C — стоп.")
    print(f"  · scout — каждые {settings.SCOUT_INTERVAL_HOURS} часа")
    hours = ", ".join(f"{hour:02d}:00" for hour in DAILY_HOURS)
    print(f"  · история + аппрув — {hours} Asia/Almaty")
    sched.start()

