"""Queue domain models for current state and append-only history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class QueueEntry:
    entry_id: str
    queue_id: str
    discord_user_id: str
    display_name: str
    state: str
    position: int
    note: str
    joined_at: datetime
    started_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class QueueEvent:
    event_id: str
    queue_id: str
    event_type: str
    actor_user_id: str | None
    entry_id: str | None
    payload: dict[str, object]
    created_at: datetime


@dataclass(frozen=True)
class QueueSummary:
    queue_id: str
    guild_id: int
    label: str
    is_paused: bool
    paused_reason: str
    active_entry_id: str | None
    waiting_count: int
    total_entries: int
    updated_at: datetime | None = None


@dataclass(frozen=True)
class QueueSnapshot:
    summary: QueueSummary
    entries: tuple[QueueEntry, ...]
    last_event: QueueEvent | None = None
