"""Query (read-only) operations for queue service."""

from __future__ import annotations

from ..models import QueueEntry, QueueEvent, QueueSnapshot, QueueSummary
from ..repositories import QueueRepository
from .queue_service_core import QueueNotFoundError


class QueueQueryMixin:
    _repository: QueueRepository

    def list_queues(self) -> tuple[QueueSummary, ...]:
        return self._repository.list_queues()

    def get_queue(self, queue_id: str) -> QueueSnapshot:
        snapshot = self._repository.get_queue(queue_id)
        if snapshot is None:
            raise QueueNotFoundError(f"Queue '{queue_id}' was not found")
        return snapshot

    def list_events(self, queue_id: str, *, limit: int = 50) -> tuple[QueueEvent, ...]:
        if self._repository.get_queue(queue_id) is None:
            raise QueueNotFoundError(f"Queue '{queue_id}' was not found")
        return self._repository.list_events(queue_id, limit=limit)

    @staticmethod
    def _active_entry(entries: tuple[QueueEntry, ...]) -> QueueEntry | None:
        return next((entry for entry in entries if entry.state == 'active'), None)

    @staticmethod
    def _waiting_entries(entries: tuple[QueueEntry, ...]) -> tuple[QueueEntry, ...]:
        return tuple(entry for entry in entries if entry.state == 'waiting')

    @staticmethod
    def _sort_entries(entries: tuple[QueueEntry, ...]) -> tuple[QueueEntry, ...]:
        return tuple(sorted(entries, key=lambda entry: (entry.position, entry.joined_at, entry.entry_id)))
