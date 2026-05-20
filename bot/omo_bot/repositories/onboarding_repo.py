"""Repository seams for onboarding user state."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from ..models.onboarding import OnboardingStatus, OnboardingUserState


class OnboardingRepository(Protocol):
    def get_user_state(self, guild_id: int, discord_user_id: str) -> OnboardingUserState | None:
        ...

    def save_user_state(self, state: OnboardingUserState) -> OnboardingUserState:
        ...

    def list_pending_users(self, guild_id: int, limit: int = 50) -> tuple[OnboardingUserState, ...]:
        ...


class InMemoryOnboardingRepository:
    def __init__(self) -> None:
        self._states: dict[tuple[int, str], OnboardingUserState] = {}

    def get_user_state(self, guild_id: int, discord_user_id: str) -> OnboardingUserState | None:
        state = self._states.get((guild_id, discord_user_id))
        return replace(state) if state else None

    def save_user_state(self, state: OnboardingUserState) -> OnboardingUserState:
        stored = replace(state)
        self._states[(state.guild_id, state.discord_user_id)] = stored
        return replace(stored)

    def list_pending_users(self, guild_id: int, limit: int = 50) -> tuple[OnboardingUserState, ...]:
        pending = [
            replace(s) for s in self._states.values()
            if s.guild_id == guild_id and s.status == OnboardingStatus.PENDING
        ]
        pending.sort(key=lambda x: x.joined_at)
        return tuple(pending[:limit])


class PostgresOnboardingRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def get_user_state(self, guild_id: int, discord_user_id: str) -> OnboardingUserState | None:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return None
            cursor.execute(
                """
                SELECT guild_id, discord_user_id, status, joined_at, onboarded_at, metadata
                FROM bot_onboarding_user_state
                WHERE guild_id = %s AND discord_user_id = %s
                """,
                (guild_id, discord_user_id),
            )
            row = cursor.fetchone()
            return self._row_to_state(row) if row else None
        finally:
            cursor.close()
            connection.close()

    def save_user_state(self, state: OnboardingUserState) -> OnboardingUserState:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError("Onboarding tables are not available")
            cursor.execute(
                """
                INSERT INTO bot_onboarding_user_state (
                    guild_id, discord_user_id, status, joined_at, onboarded_at, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (guild_id, discord_user_id)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    onboarded_at = EXCLUDED.onboarded_at,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                RETURNING guild_id, discord_user_id, status, joined_at, onboarded_at, metadata
                """,
                (
                    state.guild_id,
                    state.discord_user_id,
                    state.status.value,
                    state.joined_at,
                    state.onboarded_at,
                    Json(state.metadata),
                ),
            )
            row = cursor.fetchone()
            connection.commit()
            if not row:
                raise RuntimeError("Failed to save onboarding user state")
            return self._row_to_state(row)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def list_pending_users(self, guild_id: int, limit: int = 50) -> tuple[OnboardingUserState, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return ()
            cursor.execute(
                """
                SELECT guild_id, discord_user_id, status, joined_at, onboarded_at, metadata
                FROM bot_onboarding_user_state
                WHERE guild_id = %s AND status = 'pending'
                ORDER BY joined_at ASC
                LIMIT %s
                """,
                (guild_id, limit),
            )
            return tuple(self._row_to_state(row) for row in cursor.fetchall() or [])
        finally:
            cursor.close()
            connection.close()

    def _tables_exist(self, cursor: Any) -> bool:
        cursor.execute(
            "SELECT to_regclass('public.bot_onboarding_user_state') AS onboarding_table"
        )
        row = cursor.fetchone()
        return bool(row and row.get("onboarding_table"))

    @staticmethod
    def _row_to_state(row: dict[str, Any]) -> OnboardingUserState:
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        return OnboardingUserState(
            guild_id=int(row["guild_id"]),
            discord_user_id=str(row["discord_user_id"]),
            status=OnboardingStatus(row["status"]),
            joined_at=row["joined_at"],
            onboarded_at=row.get("onboarded_at"),
            metadata=metadata,
        )


def build_postgres_onboarding_repository(database_url: str) -> PostgresOnboardingRepository:
    return PostgresOnboardingRepository(
        connection_factory=lambda: psycopg2.connect(dsn=database_url)
    )
