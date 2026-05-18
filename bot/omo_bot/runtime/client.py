"""Discord runtime placeholder used during the initial scaffold phase."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..jobs import SyndicationPollingJob
from ..config import BotConfig
from ..repositories import SyndicationSourceRepository
from ..services import SyndicationDeliverySink, SyndicationPlanningService


@dataclass
class BotRuntime:
    """Minimal runtime object for startup, shutdown, and health logging."""

    config: BotConfig
    logger: logging.Logger
    syndication_repository: SyndicationSourceRepository
    syndication_planning_service: SyndicationPlanningService
    syndication_polling_job: SyndicationPollingJob
    syndication_delivery_sink: SyndicationDeliverySink
    state: str = field(default="created", init=False)
    last_started_at: datetime | None = field(default=None, init=False)
    last_poll_started_at: datetime | None = field(default=None, init=False)
    last_poll_completed_at: datetime | None = field(default=None, init=False)
    last_poll_delivered_items: int = field(default=0, init=False)
    last_poll_sources: list[str] = field(default_factory=list, init=False)
    last_poll_failed_sources: list[str] = field(
        default_factory=list, init=False)
    last_poll_error: str | None = field(default=None, init=False)
    polling_task_state: str = field(default="idle", init=False)
    _stop_event: asyncio.Event = field(
        default_factory=asyncio.Event, init=False)
    _polling_task: asyncio.Task[None] | None = field(default=None, init=False)

    async def start(self) -> None:
        if self.state == "running":
            return

        self.last_started_at = datetime.now(timezone.utc)
        self.state = "running"
        self._stop_event = asyncio.Event()
        self.polling_task_state = "running"
        self._polling_task = asyncio.create_task(self._run_polling_loop())

    async def close(self) -> None:
        if self.state != "running":
            self.state = "stopped"
            self.polling_task_state = "stopped"
            return

        self._stop_event.set()
        polling_task = self._polling_task
        self._polling_task = None
        if polling_task is not None:
            try:
                await polling_task
            except asyncio.CancelledError:
                pass
        self.state = "stopped"
        self.polling_task_state = "stopped"

    def health_snapshot(self) -> dict[str, object]:
        return {
            "state": self.state,
            "guild_id": self.config.guild_id,
            "configured_channels": sorted(self.config.channel_map),
            "configured_roles": sorted(self.config.role_map),
            "syndication_sources": list(self.config.syndication_sources),
            "syndication_repository_backend": self.syndication_repository.__class__.__name__,
            "syndication_polling_job": self.syndication_polling_job.__class__.__name__,
            "syndication_delivery_backend": self.syndication_delivery_sink.__class__.__name__,
            "database_configured": bool(self.config.database_url),
            "last_started_at": self.last_started_at.isoformat() if self.last_started_at else None,
            "polling_task_state": self.polling_task_state,
            "last_poll_started_at": self.last_poll_started_at.isoformat() if self.last_poll_started_at else None,
            "last_poll_completed_at": self.last_poll_completed_at.isoformat() if self.last_poll_completed_at else None,
            "last_poll_delivered_items": self.last_poll_delivered_items,
            "last_poll_sources": list(self.last_poll_sources),
            "last_poll_failed_sources": list(self.last_poll_failed_sources),
            "last_poll_error": self.last_poll_error,
        }

    async def _run_polling_loop(self) -> None:
        while not self._stop_event.is_set():
            poll_started_at = datetime.now(timezone.utc)
            self.last_poll_started_at = poll_started_at
            self.polling_task_state = "polling"

            try:
                result = self.syndication_polling_job.run(now=poll_started_at)
                self.last_poll_completed_at = datetime.now(timezone.utc)
                self.last_poll_delivered_items = result.delivered_items
                self.last_poll_sources = list(result.polled_sources)
                self.last_poll_failed_sources = list(result.failed_sources)
                self.last_poll_error = None
                self.polling_task_state = "sleeping"
            except Exception as exc:
                self.last_poll_completed_at = datetime.now(timezone.utc)
                self.last_poll_delivered_items = 0
                self.last_poll_sources = []
                self.last_poll_failed_sources = []
                self.last_poll_error = str(exc)
                self.polling_task_state = "error"
                self.logger.exception("Syndication polling loop failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.config.syndication_poll_seconds,
                )
            except asyncio.TimeoutError:
                continue
