"""Shared exceptions and helpers for queue service."""

from __future__ import annotations

from datetime import datetime, timezone

from ..models import QueueEntry, QueueSnapshot


class QueueError(RuntimeError):
    pass


class QueueNotFoundError(QueueError):
    pass


class QueuePausedError(QueueError):
    pass


class QueueConflictError(QueueError):
    pass


class QueueEntryNotFoundError(QueueError):
    pass


class QueueValidationError(QueueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _entry_payload(entry: QueueEntry) -> dict[str, object]:
    return {
        'entry_id': entry.entry_id,
        'queue_id': entry.queue_id,
        'discord_user_id': entry.discord_user_id,
        'display_name': entry.display_name,
        'state': entry.state,
        'position': entry.position,
        'note': entry.note,
        'joined_at': entry.joined_at.isoformat(),
        'started_at': entry.started_at.isoformat() if entry.started_at else None,
    }


def _assert_not_paused(snapshot: QueueSnapshot) -> None:
    if snapshot.summary.is_paused:
        raise QueuePausedError('Queue is currently paused')
