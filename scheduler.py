"""
scheduler.py - APScheduler-based job trigger for the Job Finder system.

Schedule (all times local):
  Monday – Friday : 09:00, 11:30, 16:30
  Sunday          : 20:00

Usage:
  python scheduler.py           # Start scheduler in foreground (Ctrl-C to stop)
  python scheduler.py --once    # Run the pipeline once immediately then exit
  python scheduler.py --next    # Print the next scheduled run time and exit

The scheduler runs as a persistent foreground daemon. For production deployment
consider wrapping it with systemd, supervisord, or launchd (macOS).
"""

import argparse
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path

# Load .env before importing config so that env vars are available
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).parent / ".env"
    if _env_file.exists():
        load_dotenv(str(_env_file))
        print(f"Loaded environment from {_env_file}")
except ImportError:
    pass   # python-dotenv not installed; rely on real environment variables

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from config import SCHEDULE
from orchestrator import run_once

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).parent / "execution_log.txt",
            mode="a",
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger("scheduler")


# ---------------------------------------------------------------------------
# Scheduler event listeners
# ---------------------------------------------------------------------------

def _on_job_executed(event) -> None:
    logger.info(
        "Scheduled run completed successfully at %s.",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


def _on_job_error(event) -> None:
    logger.error(
        "Scheduled run raised an exception: %s",
        event.exception,
        exc_info=event.traceback,
    )


# ---------------------------------------------------------------------------
# Build and configure the scheduler
# ---------------------------------------------------------------------------

def build_scheduler() -> BlockingScheduler:
    """
    Construct a BlockingScheduler with all configured cron triggers.

    The SCHEDULE list from config.py drives the trigger times:
      [("mon-fri", 9, 0), ("mon-fri", 11, 30), ("mon-fri", 16, 30), ("sun", 20, 0)]
    """
    scheduler = BlockingScheduler(timezone="America/Chicago")  # change to your local tz

    # Register event listeners
    scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    for day_of_week, hour, minute in SCHEDULE:
        trigger = CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
        )
        job_id = f"job_finder_{day_of_week}_{hour:02d}{minute:02d}"

        scheduler.add_job(
            func=run_once,
            trigger=trigger,
            id=job_id,
            name=f"Job Finder ({day_of_week} {hour:02d}:{minute:02d})",
            misfire_grace_time=300,    # Allow up to 5 min late start
            coalesce=True,             # Collapse multiple missed runs into one
            max_instances=1,           # Prevent overlapping executions
        )

        logger.info(
            "Registered trigger: id=%s  day=%s  time=%02d:%02d",
            job_id, day_of_week, hour, minute,
        )

    return scheduler


# ---------------------------------------------------------------------------
# Next-run preview helper
# ---------------------------------------------------------------------------

def print_next_runs(scheduler: BlockingScheduler, count: int = 5) -> None:
    """Print the next N scheduled run times."""
    print(f"\nNext {count} scheduled runs:")
    jobs = scheduler.get_jobs()

    if not jobs:
        print("  No jobs scheduled.")
        return

    upcoming: list[tuple] = []
    for job in jobs:
        # Compute next fire time for this job's trigger
        try:
            next_run = job.trigger.get_next_fire_time(None, datetime.now())
            if next_run:
                upcoming.append((next_run, job.name))
        except Exception:
            # Fallback: just show the job name
            upcoming.append((None, job.name))

    # Sort by run time
    upcoming_sorted = sorted([u for u in upcoming if u[0] is not None], key=lambda x: x[0])

    for i, (run_time, name) in enumerate(upcoming_sorted[:count]):
        print(f"  {run_time.strftime('%Y-%m-%d %H:%M %Z'):30s}  {name}")

    print()


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_scheduler_ref = None


def _handle_signal(signum, frame) -> None:
    """Handle SIGINT / SIGTERM for graceful shutdown."""
    logger.info("Shutdown signal received – stopping scheduler...")
    if _scheduler_ref and _scheduler_ref.running:
        _scheduler_ref.shutdown(wait=False)
    sys.exit(0)


signal.signal(signal.SIGINT,  _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global _scheduler_ref

    parser = argparse.ArgumentParser(
        description="Job Finder Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scheduler.py            # Start the scheduler (runs forever)
  python scheduler.py --once     # Run the pipeline immediately and exit
  python scheduler.py --next     # Show upcoming run times and exit
        """,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the pipeline once immediately then exit (ignores schedule).",
    )
    parser.add_argument(
        "--next",
        action="store_true",
        help="Print the next scheduled run times and exit.",
    )
    args = parser.parse_args()

    if args.once:
        logger.info("--once flag: running pipeline immediately.")
        run_once()
        return

    scheduler = build_scheduler()
    _scheduler_ref = scheduler

    if args.next:
        print_next_runs(scheduler)
        return

    logger.info(
        "Job Finder Scheduler starting up at %s.",
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    print_next_runs(scheduler)

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    scheduler.start()   # Blocks until shutdown


if __name__ == "__main__":
    main()
