"""Typed domain models for bot syndication workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class SyndicationSourceState:
    """Current checkpoint and scheduling state for one syndication source."""

    source_key: str
    enabled: bool = True
    checkpoint: str | None = None
    last_polled_at: datetime | None = None
    last_succeeded_at: datetime | None = None
    last_failed_at: datetime | None = None

    def is_due(self, *, now: datetime, poll_interval_seconds: int) -> bool:
        if not self.enabled:
            return False

        if self.last_polled_at is None:
            return True

        return self.last_polled_at + timedelta(seconds=poll_interval_seconds) <= now

    def with_poll_started(self, *, polled_at: datetime) -> "SyndicationSourceState":
        normalized_time = polled_at.astimezone(timezone.utc)
        return SyndicationSourceState(
            source_key=self.source_key,
            enabled=self.enabled,
            checkpoint=self.checkpoint,
            last_polled_at=normalized_time,
            last_succeeded_at=self.last_succeeded_at,
            last_failed_at=self.last_failed_at,
        )

    def with_poll_succeeded(
        self,
        *,
        polled_at: datetime,
        checkpoint: str | None,
    ) -> "SyndicationSourceState":
        normalized_time = polled_at.astimezone(timezone.utc)
        return SyndicationSourceState(
            source_key=self.source_key,
            enabled=self.enabled,
            checkpoint=checkpoint,
            last_polled_at=normalized_time,
            last_succeeded_at=normalized_time,
            last_failed_at=None,
        )

    def with_poll_failed(self, *, polled_at: datetime) -> "SyndicationSourceState":
        normalized_time = polled_at.astimezone(timezone.utc)
        return SyndicationSourceState(
            source_key=self.source_key,
            enabled=self.enabled,
            checkpoint=self.checkpoint,
            last_polled_at=normalized_time,
            last_succeeded_at=self.last_succeeded_at,
            last_failed_at=normalized_time,
        )
