"""Repository seams for queue current state and history."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Protocol

import psycopg2
from psycopg2.extras import Json, RealDictCursor

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


class PostgresQueueRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def list_queues(self) -> tuple[QueueSummary, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return ()
            cursor.execute(
                """
                SELECT
                    q.queue_id,
                    q.guild_id,
                    q.label,
                    q.is_paused,
                    q.paused_reason,
                    q.active_entry_id,
                    q.updated_at,
                    COUNT(e.id) FILTER (WHERE e.state = 'waiting') AS waiting_count,
                    COUNT(e.id) AS total_entries
                FROM bot_queue AS q
                LEFT JOIN bot_queue_entry AS e ON e.queue_id = q.queue_id
                GROUP BY q.queue_id, q.guild_id, q.label, q.is_paused, q.paused_reason, q.active_entry_id, q.updated_at
                ORDER BY q.label ASC, q.queue_id ASC
                """
            )
            return tuple(self._row_to_summary(row) for row in cursor.fetchall() or [])
        finally:
            cursor.close()
            connection.close()

    def get_queue(self, queue_id: str) -> QueueSnapshot | None:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return None
            cursor.execute(
                """
                SELECT
                    q.queue_id,
                    q.guild_id,
                    q.label,
                    q.is_paused,
                    q.paused_reason,
                    q.active_entry_id,
                    q.updated_at,
                    COUNT(e.id) FILTER (WHERE e.state = 'waiting') AS waiting_count,
                    COUNT(e.id) AS total_entries
                FROM bot_queue AS q
                LEFT JOIN bot_queue_entry AS e ON e.queue_id = q.queue_id
                WHERE q.queue_id = %s
                GROUP BY q.queue_id, q.guild_id, q.label, q.is_paused, q.paused_reason, q.active_entry_id, q.updated_at
                """,
                (queue_id,),
            )
            summary_row = cursor.fetchone()
            if not summary_row:
                return None
            cursor.execute(
                """
                SELECT
                    id,
                    queue_id,
                    discord_user_id,
                    display_name,
                    state,
                    position,
                    note,
                    joined_at,
                    started_at,
                    updated_at
                FROM bot_queue_entry
                WHERE queue_id = %s
                ORDER BY position ASC, joined_at ASC, id ASC
                """,
                (queue_id,),
            )
            entry_rows = cursor.fetchall() or []
            events = self.list_events(queue_id, limit=1)
            return QueueSnapshot(
                summary=self._row_to_summary(summary_row),
                entries=tuple(self._row_to_entry(row) for row in entry_rows),
                last_event=events[0] if events else None,
            )
        finally:
            cursor.close()
            connection.close()

    def save_queue(
        self,
        *,
        summary: QueueSummary,
        entries: tuple[QueueEntry, ...],
    ) -> QueueSnapshot:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError("Queue tables are not available")

            cursor.execute(
                """
                INSERT INTO bot_queue (
                    queue_id,
                    guild_id,
                    label,
                    is_paused,
                    paused_reason,
                    active_entry_id
                )
                VALUES (%s, %s, %s, %s, %s, NULL)
                ON CONFLICT (queue_id)
                DO UPDATE SET
                    guild_id = EXCLUDED.guild_id,
                    label = EXCLUDED.label,
                    is_paused = EXCLUDED.is_paused,
                    paused_reason = EXCLUDED.paused_reason,
                    active_entry_id = NULL
                """,
                (
                    summary.queue_id,
                    summary.guild_id,
                    summary.label,
                    summary.is_paused,
                    summary.paused_reason,
                ),
            )
            cursor.execute(
                "DELETE FROM bot_queue_entry WHERE queue_id = %s",
                (summary.queue_id,),
            )
            for entry in entries:
                cursor.execute(
                    """
                    INSERT INTO bot_queue_entry (
                        id,
                        queue_id,
                        discord_user_id,
                        display_name,
                        state,
                        position,
                        note,
                        joined_at,
                        started_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        entry.entry_id,
                        entry.queue_id,
                        entry.discord_user_id,
                        entry.display_name,
                        entry.state,
                        entry.position,
                        entry.note,
                        entry.joined_at,
                        entry.started_at,
                    ),
                )
            cursor.execute(
                """
                UPDATE bot_queue
                SET active_entry_id = %s
                WHERE queue_id = %s
                """,
                (summary.active_entry_id, summary.queue_id),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

        snapshot = self.get_queue(summary.queue_id)
        if snapshot is None:
            raise RuntimeError(
                "Queue snapshot could not be reloaded after save")
        return snapshot

    def append_event(self, event: QueueEvent) -> QueueEvent:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError("Queue tables are not available")
            cursor.execute(
                """
                INSERT INTO bot_queue_event (
                    id,
                    queue_id,
                    entry_id,
                    event_type,
                    actor_user_id,
                    payload
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING created_at
                """,
                (
                    event.event_id,
                    event.queue_id,
                    event.entry_id,
                    event.event_type,
                    event.actor_user_id,
                    Json(event.payload),
                ),
            )
            row = cursor.fetchone()
            connection.commit()
            return QueueEvent(
                event_id=event.event_id,
                queue_id=event.queue_id,
                event_type=event.event_type,
                actor_user_id=event.actor_user_id,
                entry_id=event.entry_id,
                payload=event.payload,
                created_at=row["created_at"] if row else event.created_at,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def list_events(self, queue_id: str, *, limit: int = 50) -> tuple[QueueEvent, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return ()
            cursor.execute(
                """
                SELECT id, queue_id, entry_id, event_type, actor_user_id, payload, created_at
                FROM bot_queue_event
                WHERE queue_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (queue_id, limit),
            )
            return tuple(self._row_to_event(row) for row in cursor.fetchall() or [])
        finally:
            cursor.close()
            connection.close()

    def _tables_exist(self, cursor: Any | None = None) -> bool:
        owns_cursor = cursor is None
        connection = None
        if owns_cursor:
            connection = self._connection_factory()
            cursor = connection.cursor(cursor_factory=RealDictCursor)
        assert cursor is not None
        try:
            cursor.execute(
                """
                SELECT
                    to_regclass('public.bot_queue') AS queue_table,
                    to_regclass('public.bot_queue_entry') AS entry_table,
                    to_regclass('public.bot_queue_event') AS event_table
                """
            )
            row = cursor.fetchone()
            return bool(row and row.get("queue_table") and row.get("entry_table") and row.get("event_table"))
        finally:
            if owns_cursor:
                cursor.close()
                assert connection is not None
                connection.close()

    @staticmethod
    def _row_to_summary(row: dict[str, Any]) -> QueueSummary:
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

    @staticmethod
    def _row_to_entry(row: dict[str, Any]) -> QueueEntry:
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

    @staticmethod
    def _row_to_event(row: dict[str, Any]) -> QueueEvent:
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


def build_postgres_queue_repository(database_url: str) -> PostgresQueueRepository:
    return PostgresQueueRepository(connection_factory=lambda: psycopg2.connect(dsn=database_url))
