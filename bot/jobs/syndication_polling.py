"""Polling job for syndication sources and downstream delivery seam."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

from ..adapters import SyndicationAdapter
from ..models import SyndicationSourceState
from ..services import (
    SyndicationDeliveryBatch,
    SyndicationDeliverySink,
    SyndicationPlanningService,
)


@dataclass(frozen=True)
class SyndicationPollingRunResult:
    """Summary of one polling pass across due syndication sources."""

    polled_sources: tuple[str, ...]
    delivered_items: int
    failed_sources: tuple[str, ...]


class SyndicationPollingJob:
    """Poll due syndication sources, deliver items, persist checkpoints."""

    def __init__(
        self,
        *,
        planning_service: SyndicationPlanningService,
        repository,
        adapters: Mapping[str, SyndicationAdapter],
        delivery_sink: SyndicationDeliverySink,
    ) -> None:
        self._planning_service = planning_service
        self._repository = repository
        self._adapters = dict(adapters)
        self._delivery_sink = delivery_sink

    def run(self, *, now: datetime | None = None) -> SyndicationPollingRunResult:
        resolved_now = now.astimezone(
            timezone.utc) if now else datetime.now(timezone.utc)
        due_sources = self._planning_service.list_due_sources(now=resolved_now)
        polled_sources: list[str] = []
        failed_sources: list[str] = []
        delivered_items = 0

        for source_state in due_sources:
            polled_sources.append(source_state.source_key)
            delivered_items += self._poll_source(
                source_state, now=resolved_now)

        return SyndicationPollingRunResult(
            polled_sources=tuple(polled_sources),
            delivered_items=delivered_items,
            failed_sources=tuple(failed_sources),
        )

    def run_source_key(
        self,
        source_key: str,
        *,
        now: datetime | None = None,
    ) -> SyndicationPollingRunResult:
        resolved_now = now.astimezone(
            timezone.utc) if now else datetime.now(timezone.utc)
        source_state = self._repository.get_by_source_key(source_key)
        if source_state is None:
            source_state = SyndicationSourceState(source_key=source_key)
            self._repository.save(source_state)

        delivered_items = self._poll_source(source_state, now=resolved_now)
        return SyndicationPollingRunResult(
            polled_sources=(source_key,),
            delivered_items=delivered_items,
            failed_sources=(),
        )

    def _poll_source(self, source_state: SyndicationSourceState, *, now: datetime) -> int:
        started_state = source_state.with_poll_started(polled_at=now)
        self._repository.save(started_state)

        try:
            adapter = self._adapters[source_state.source_key]
            fetch_result = adapter.fetch_since(
                checkpoint=source_state.checkpoint)
            if fetch_result.items:
                self._delivery_sink.deliver(
                    SyndicationDeliveryBatch(
                        source_key=source_state.source_key,
                        items=fetch_result.items,
                    )
                )
            self._repository.save(
                started_state.with_poll_succeeded(
                    polled_at=now,
                    checkpoint=fetch_result.next_checkpoint or started_state.checkpoint,
                )
            )
            return len(fetch_result.items)
        except Exception:
            self._repository.save(
                started_state.with_poll_failed(polled_at=now))
            raise
