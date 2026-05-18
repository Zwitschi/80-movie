"""Planning helpers for bot syndication polling."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import BotConfig
from ..models import SyndicationSourceState
from ..repositories import InMemorySyndicationSourceRepository


class SyndicationPlanningService:
    """Build due polling work from config and persisted source checkpoints."""

    def __init__(
        self,
        *,
        config: BotConfig,
        repository: InMemorySyndicationSourceRepository,
    ) -> None:
        self._config = config
        self._repository = repository

    def list_due_sources(
        self,
        *,
        now: datetime | None = None,
    ) -> list[SyndicationSourceState]:
        resolved_now = now.astimezone(
            timezone.utc) if now else datetime.now(timezone.utc)
        due_sources: list[SyndicationSourceState] = []

        for source_key in self._config.syndication_sources:
            state = self._repository.get_by_source_key(source_key)
            if state is None:
                state = SyndicationSourceState(source_key=source_key)
                self._repository.save(state)

            if state.is_due(
                now=resolved_now,
                poll_interval_seconds=self._config.syndication_poll_seconds,
            ):
                due_sources.append(state)

        return due_sources
