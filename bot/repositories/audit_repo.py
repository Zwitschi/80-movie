"""Repository seams for append-only bot audit logs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Protocol

import psycopg2
from psycopg2.extras import Json, RealDictCursor


@dataclass(frozen=True)
class BotAuditLogEntry:
    actor_user_id: str | None
    actor_session_id: str | None
    action_key: str
    target_type: str
    target_key: str
    request_id: str | None
    before_state: dict[str, object] | None
    after_state: dict[str, object] | None
    created_at: datetime | None = None


class BotAuditLogRepository(Protocol):
    def append(self, entry: BotAuditLogEntry) -> BotAuditLogEntry:
        ...


class InMemoryBotAuditLogRepository:
    def __init__(self) -> None:
        self.entries: list[BotAuditLogEntry] = []

    def append(self, entry: BotAuditLogEntry) -> BotAuditLogEntry:
        self.entries.append(entry)
        return entry


class PostgresBotAuditLogRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def append(self, entry: BotAuditLogEntry) -> BotAuditLogEntry:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._table_exists(cursor):
                raise RuntimeError("Bot audit log table is not available")

            cursor.execute(
                """
                INSERT INTO bot_audit_log (
                    actor_user_id,
                    actor_session_id,
                    action_key,
                    target_type,
                    target_key,
                    request_id,
                    before_state,
                    after_state
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING created_at
                """,
                (
                    entry.actor_user_id,
                    entry.actor_session_id,
                    entry.action_key,
                    entry.target_type,
                    entry.target_key,
                    entry.request_id,
                    Json(entry.before_state) if entry.before_state is not None else None,
                    Json(entry.after_state) if entry.after_state is not None else None,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
            return BotAuditLogEntry(
                actor_user_id=entry.actor_user_id,
                actor_session_id=entry.actor_session_id,
                action_key=entry.action_key,
                target_type=entry.target_type,
                target_key=entry.target_key,
                request_id=entry.request_id,
                before_state=entry.before_state,
                after_state=entry.after_state,
                created_at=row.get("created_at") if row else None,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _table_exists(cursor: Any) -> bool:
        cursor.execute(
            "SELECT to_regclass('public.bot_audit_log') AS table_name")
        row = cursor.fetchone()
        return bool(row and row.get("table_name"))


def build_postgres_bot_audit_log_repository(
    database_url: str,
) -> PostgresBotAuditLogRepository:
    return PostgresBotAuditLogRepository(
        connection_factory=lambda: psycopg2.connect(dsn=database_url)
    )
