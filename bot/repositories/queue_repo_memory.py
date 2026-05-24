"""In-memory queue repository implementation."""

from __future__ import annotations

from dataclasses import replace

from ..models import QueueEntry, QueueEvent, QueueSnapshot, QueueSummary


class InMemoryQueueRepository:
    def __init__(self) -> None:
        self._queues: dict[str, QueueSummary] = {}
        self._entries: dict[str, tuple[QueueEntry, ...]] = {}
        self._events: dict[str, list[QueueEvent]] = {}

    def list_queues(self) -> tuple[QueueSummary, ...]:
        return tuple(
            replace(summary)
            for summary in sorted(
                self._queues.values(),
                key=lambda item: (item.label.lower(), item.queue_id),
            )
        )

    def get_queue(self, queue_id: str) -> QueueSnapshot | None:
        summary = self._queues.get(queue_id)
        if summary is None:
            return None
        entries = self._entries.get(queue_id, ())
        events = self._events.get(queue_id, [])
        last_event = replace(events[0]) if events else None
        return QueueSnapshot(
            summary=replace(summary),
            entries=tuple(replace(entry) for entry in entries),
            last_event=last_event,
        )

    def save_queue(
        self,
        *,
        summary: QueueSummary,
        entries: tuple[QueueEntry, ...],
    ) -> QueueSnapshot:
        stored_summary = replace(summary)
        stored_entries = tuple(replace(entry) for entry in entries)
        self._queues[summary.queue_id] = stored_summary
        self._entries[summary.queue_id] = stored_entries
        events = self._events.get(summary.queue_id, [])
        return QueueSnapshot(
            summary=replace(stored_summary),
            entries=tuple(replace(entry) for entry in stored_entries),
            last_event=replace(events[0]) if events else None,
        )

    def append_event(self, event: QueueEvent) -> QueueEvent:
        stored_event = replace(event)
        self._events.setdefault(event.queue_id, []).insert(0, stored_event)
        return replace(stored_event)

    def list_events(self, queue_id: str, *, limit: int = 50) -> tuple[QueueEvent, ...]:
        return tuple(replace(event) for event in self._events.get(queue_id, [])[:limit])
