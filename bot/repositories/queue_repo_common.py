"""Shared protocol and row-mapping utilities for queue repositories."""

from __future__ import annotations

from typing import Any, Protocol

from ..models import QueueEntry, QueueEvent, QueueSnapshot, QueueSummary


class QueueRepository(Protocol):
    def list_queues(self) -> tuple[QueueSummary, ...]:
        ...

    def get_queue(self, queue_id: str) -> QueueSnapshot | None:
        ...

    def save_queue(
        self,
        *,
        summary: QueueSummary,
        entries: tuple[QueueEntry, ...],
    ) -> QueueSnapshot:
        ...

    def append_event(self, event: QueueEvent) -> QueueEvent:
        ...

    def list_events(self, queue_id: str, *, limit: int = 50) -> tuple[QueueEvent, ...]:
        ...


def row_to_summary(row: dict[str, Any]) -> QueueSummary:
    return QueueSummary(
        queue_id=str(row["queue_id"]),
        guild_id=int(row["guild_id"]),
        label=str(row["label"]),
        is_paused=bool(row["is_paused"]),
        paused_reason=str(row.get("paused_reason") or ""),
        active_entry_id=str(row["active_entry_id"]) if row.get(
            "active_entry_id") else None,
        waiting_count=int(row.get("waiting_count") or 0),
        total_entries=int(row.get("total_entries") or 0),
        updated_at=row.get("updated_at"),
    )


def row_to_entry(row: dict[str, Any]) -> QueueEntry:
    return QueueEntry(
        entry_id=str(row["id"]),
        queue_id=str(row["queue_id"]),
        discord_user_id=str(row["discord_user_id"]),
        display_name=str(row["display_name"]),
        state=str(row["state"]),
        position=int(row["position"]),
        note=str(row.get("note") or ""),
        joined_at=row["joined_at"],
        started_at=row.get("started_at"),
        updated_at=row.get("updated_at"),
    )


def row_to_event(row: dict[str, Any]) -> QueueEvent:
    payload = row.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    return QueueEvent(
        event_id=str(row["id"]),
        queue_id=str(row["queue_id"]),
        event_type=str(row["event_type"]),
        actor_user_id=str(row["actor_user_id"]) if row.get(
            "actor_user_id") else None,
        entry_id=str(row["entry_id"]) if row.get("entry_id") else None,
        payload=payload,
        created_at=row["created_at"],
    )
