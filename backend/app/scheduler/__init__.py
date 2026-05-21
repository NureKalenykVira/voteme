"""APScheduler wire-up for VoteMe.

Single AsyncIOScheduler instance is created lazily and used by the
FastAPI lifespan to run the voting lifecycle tick().
"""
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def reset_scheduler() -> None:
    """Used by tests to discard the singleton instance."""
    global _scheduler
    _scheduler = None
