"""Discord runtime placeholder used during the initial scaffold phase."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..config import BotConfig


@dataclass
class BotRuntime:
    """Minimal runtime object for startup, shutdown, and health logging."""

    config: BotConfig
    logger: logging.Logger
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
            "database_configured": bool(self.config.database_url),
            "last_started_at": self.last_started_at.isoformat() if self.last_started_at else None,
        }
