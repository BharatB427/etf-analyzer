"""
Scheduler module — runs the analysis pipeline daily on weekdays.

Uses APScheduler's CronTrigger so the job fires at a configurable
hour (default 07:00) Monday through Friday.
"""

import logging
import signal
import sys
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import SchedulerConfig

logger = logging.getLogger(__name__)


class DailyScheduler:
    """Wraps APScheduler to run a job on weekday mornings."""

    def __init__(
        self,
        job_func: Callable,
        config: Optional[SchedulerConfig] = None,
    ) -> None:
        self.job_func = job_func
        self.cfg = config or SchedulerConfig()
        self.scheduler = BlockingScheduler()

        # Graceful shutdown on SIGINT / SIGTERM
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def start(self) -> None:
        """Start the scheduler (blocking call)."""
        trigger = CronTrigger(
            day_of_week="mon-fri",
            hour=self.cfg.run_hour,
            minute=self.cfg.run_minute,
            timezone=self.cfg.timezone,
        )

        self.scheduler.add_job(
            self._run_with_logging,
            trigger,
            id="etf_daily_analysis",
            name="Daily ETF Analysis",
            replace_existing=True,
        )

        logger.info(
            "Scheduler started — analysis will run Mon-Fri at %02d:%02d (%s).",
            self.cfg.run_hour,
            self.cfg.run_minute,
            self.cfg.timezone,
        )
        logger.info("Press Ctrl+C to stop.")

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")

    def _run_with_logging(self) -> None:
        """Execute the job and log timing."""
        start = datetime.now()
        logger.info("═" * 60)
        logger.info("Daily analysis run started at %s", start.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            self.job_func()
        except Exception as exc:
            logger.error("Analysis run failed: %s", exc, exc_info=True)
        elapsed = (datetime.now() - start).total_seconds()
        logger.info("Run completed in %.1f seconds.", elapsed)
        logger.info("═" * 60)

    def _shutdown(self, signum: int, frame) -> None:
        logger.info("Shutdown signal received — stopping scheduler …")
        self.scheduler.shutdown(wait=False)
        sys.exit(0)
