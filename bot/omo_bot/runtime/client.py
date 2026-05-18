"""Discord runtime placeholder used during the initial scaffold phase."""

from __future__ import annotations

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

    async def start(self) -> None:
        if self.state == "running":
            return

        self.last_started_at = datetime.now(timezone.utc)
        self.state = "running"

    async def close(self) -> None:
        if self.state != "running":
            self.state = "stopped"
            return

        self.state = "stopped"

    def health_snapshot(self) -> dict[str, object]:
        return {
            "state": self.state,
            "guild_id": self.config.guild_id,
            "configured_channels": sorted(self.config.channel_map),
            "syndication_sources": list(self.config.syndication_sources),
            "syndication_repository_backend": self.syndication_repository.__class__.__name__,
            "syndication_polling_job": self.syndication_polling_job.__class__.__name__,
            "syndication_delivery_backend": self.syndication_delivery_sink.__class__.__name__,
            "database_configured": bool(self.config.database_url),
            "last_started_at": self.last_started_at.isoformat() if self.last_started_at else None,
        }
