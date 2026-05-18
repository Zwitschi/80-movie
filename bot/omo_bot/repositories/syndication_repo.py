"""Repository seams for bot syndication source state."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Protocol

import psycopg2
from psycopg2.extras import RealDictCursor

from ..models import SyndicationSourceState


class SyndicationSourceRepository(Protocol):
    """Common repository contract for syndication source state."""

    def get_by_source_key(self, source_key: str) -> SyndicationSourceState | None:
        ...

    def save(self, state: SyndicationSourceState) -> SyndicationSourceState:
        ...


class InMemorySyndicationSourceRepository:
    """Simple repository used to exercise syndication state without a DB."""

    def __init__(self, initial_states: list[SyndicationSourceState] | None = None) -> None:
        self._states = {
            state.source_key: replace(state)
            for state in (initial_states or [])
        }

    def get_by_source_key(self, source_key: str) -> SyndicationSourceState | None:
        state = self._states.get(source_key)
        return replace(state) if state is not None else None

    def save(self, state: SyndicationSourceState) -> SyndicationSourceState:
        stored_state = replace(state)
        self._states[state.source_key] = stored_state
        return replace(stored_state)


class PostgresSyndicationSourceRepository:
    """PostgreSQL-backed repository for syndication source and checkpoint state."""

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def get_by_source_key(self, source_key: str) -> SyndicationSourceState | None:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return None

            cursor.execute(
                """
                SELECT
                    s.source_key,
                    s.is_enabled,
                    c.checkpoint,
                    c.last_polled_at,
                    c.last_succeeded_at,
                    c.last_failed_at
                FROM bot_syndication_source AS s
                LEFT JOIN bot_syndication_checkpoint AS c
                    ON c.source_key = s.source_key
                WHERE s.source_key = %s
                """,
                (source_key,),
            )
            row = cursor.fetchone()
            return self._row_to_state(row) if row else None
        finally:
            cursor.close()
            connection.close()

    def save(self, state: SyndicationSourceState) -> SyndicationSourceState:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            cursor.execute(
                """
                INSERT INTO bot_syndication_source (source_key, is_enabled)
                VALUES (%s, %s)
                ON CONFLICT (source_key)
                DO UPDATE SET is_enabled = EXCLUDED.is_enabled
                """,
                (state.source_key, state.enabled),
            )
            cursor.execute(
                """
                INSERT INTO bot_syndication_checkpoint (
                    source_key,
                    checkpoint,
                    last_polled_at,
                    last_succeeded_at,
                    last_failed_at
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_key)
                DO UPDATE SET
                    checkpoint = EXCLUDED.checkpoint,
                    last_polled_at = EXCLUDED.last_polled_at,
                    last_succeeded_at = EXCLUDED.last_succeeded_at,
                    last_failed_at = EXCLUDED.last_failed_at
                """,
                (
                    state.source_key,
                    state.checkpoint,
                    state.last_polled_at,
                    state.last_succeeded_at,
                    state.last_failed_at,
                ),
            )
            connection.commit()
            return replace(state)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def _tables_exist(cursor: Any) -> bool:
        cursor.execute(
            """
            SELECT
                to_regclass('public.bot_syndication_source') AS source_table,
                to_regclass('public.bot_syndication_checkpoint') AS checkpoint_table
            """
        )
        row = cursor.fetchone()
        return bool(row and row.get("source_table") and row.get("checkpoint_table"))

    @staticmethod
    def _row_to_state(row: dict[str, Any]) -> SyndicationSourceState:
        return SyndicationSourceState(
            source_key=row["source_key"],
            enabled=bool(row["is_enabled"]),
            checkpoint=row.get("checkpoint"),
            last_polled_at=row.get("last_polled_at"),
            last_succeeded_at=row.get("last_succeeded_at"),
            last_failed_at=row.get("last_failed_at"),
        )


def build_postgres_syndication_repository(
    database_url: str,
) -> PostgresSyndicationSourceRepository:
    """Create the PostgreSQL-backed syndication repository for bot storage."""

    return PostgresSyndicationSourceRepository(
        connection_factory=lambda: psycopg2.connect(dsn=database_url)
    )
