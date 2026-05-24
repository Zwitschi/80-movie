"""PostgreSQL onboarding repository implementation."""

from __future__ import annotations

from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from ..models import OnboardingConfig, OnboardingEvent, OnboardingRoleBinding
from .onboarding_repo_common import row_to_event


class PostgresOnboardingRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def get_config(self, guild_id: int) -> OnboardingConfig | None:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return None
            cursor.execute(
                """
                SELECT guild_id, welcome_copy, starter_channel_ids, updated_at
                FROM bot_onboarding_config
                WHERE guild_id = %s
                """,
                (guild_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            cursor.execute(
                """
                SELECT binding_key, role_id, label
                FROM bot_onboarding_role_binding
                WHERE guild_id = %s
                ORDER BY binding_key ASC
                """,
                (guild_id,),
            )
            bindings = tuple(
                OnboardingRoleBinding(
                    binding_key=str(r['binding_key']),
                    role_id=int(r['role_id']),
                    label=str(r['label']),
                )
                for r in (cursor.fetchall() or [])
            )
            return OnboardingConfig(
                guild_id=int(row['guild_id']),
                welcome_copy=str(row['welcome_copy'] or ''),
                starter_channel_ids=tuple(int(i) for i in (
                    row['starter_channel_ids'] or [])),
                role_bindings=bindings,
                updated_at=row.get('updated_at'),
            )
        finally:
            cursor.close()
            connection.close()

    def save_config(self, config: OnboardingConfig) -> OnboardingConfig:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError('Onboarding tables are not available')
            cursor.execute(
                """
                INSERT INTO bot_onboarding_config (guild_id, welcome_copy, starter_channel_ids)
                VALUES (%s, %s, %s)
                ON CONFLICT (guild_id) DO UPDATE SET
                    welcome_copy = EXCLUDED.welcome_copy,
                    starter_channel_ids = EXCLUDED.starter_channel_ids
                """,
                (config.guild_id, config.welcome_copy,
                 list(config.starter_channel_ids)),
            )
            cursor.execute(
                "DELETE FROM bot_onboarding_role_binding WHERE guild_id = %s",
                (config.guild_id,),
            )
            for binding in config.role_bindings:
                cursor.execute(
                    """
                    INSERT INTO bot_onboarding_role_binding (guild_id, binding_key, role_id, label)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (config.guild_id, binding.binding_key,
                     binding.role_id, binding.label),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()
        result = self.get_config(config.guild_id)
        if result is None:
            raise RuntimeError(
                'Onboarding config could not be reloaded after save')
        return result

    def append_event(self, event: OnboardingEvent) -> OnboardingEvent:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError('Onboarding tables are not available')
            cursor.execute(
                """
                INSERT INTO bot_onboarding_event (
                    id, guild_id, discord_user_id, display_name,
                    event_type, role_id, role_binding_key,
                    idempotency_key, actor_user_id, payload
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING created_at
                """,
                (
                    event.event_id,
                    event.guild_id,
                    event.discord_user_id,
                    event.display_name,
                    event.event_type,
                    event.role_id,
                    event.role_binding_key,
                    event.idempotency_key,
                    event.actor_user_id,
                    Json(event.metadata),
                ),
            )
            row = cursor.fetchone()
            connection.commit()
            return OnboardingEvent(
                event_id=event.event_id,
                guild_id=event.guild_id,
                discord_user_id=event.discord_user_id,
                display_name=event.display_name,
                event_type=event.event_type,
                role_id=event.role_id,
                role_binding_key=event.role_binding_key,
                idempotency_key=event.idempotency_key,
                actor_user_id=event.actor_user_id,
                metadata=event.metadata,
                created_at=row['created_at'] if row else event.created_at,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def has_event(self, idempotency_key: str) -> bool:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return False
            cursor.execute(
                "SELECT 1 FROM bot_onboarding_event WHERE idempotency_key = %s LIMIT 1",
                (idempotency_key,),
            )
            return cursor.fetchone() is not None
        finally:
            cursor.close()
            connection.close()

    def list_events(self, guild_id: int, *, limit: int = 50) -> tuple[OnboardingEvent, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return ()
            cursor.execute(
                """
                SELECT id, guild_id, discord_user_id, display_name,
                       event_type, role_id, role_binding_key,
                       idempotency_key, actor_user_id, payload, created_at
                FROM bot_onboarding_event
                WHERE guild_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (guild_id, limit),
            )
            return tuple(row_to_event(r) for r in (cursor.fetchall() or []))
        finally:
            cursor.close()
            connection.close()

    def get_event(self, event_id: str) -> OnboardingEvent | None:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return None
            cursor.execute(
                """
                SELECT id, guild_id, discord_user_id, display_name,
                       event_type, role_id, role_binding_key,
                       idempotency_key, actor_user_id, payload, created_at
                FROM bot_onboarding_event
                WHERE id = %s
                """,
                (event_id,),
            )
            row = cursor.fetchone()
            return row_to_event(row) if row else None
        finally:
            cursor.close()
            connection.close()

    def delete_user_events(self, guild_id: int, discord_user_id: str) -> int:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return 0
            cursor.execute(
                """
                DELETE FROM bot_onboarding_event
                WHERE guild_id = %s AND discord_user_id = %s
                """,
                (guild_id, discord_user_id),
            )
            deleted = cursor.rowcount
            connection.commit()
            return deleted
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def count_user_events(self, guild_id: int, discord_user_id: str) -> int:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return 0
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM bot_onboarding_event WHERE guild_id = %s AND discord_user_id = %s",
                (guild_id, discord_user_id),
            )
            row = cursor.fetchone()
            return int(row['cnt']) if row else 0
        finally:
            cursor.close()
            connection.close()

    def list_events_by_type(
        self, guild_id: int, event_type: str, *, limit: int = 50
    ) -> tuple[OnboardingEvent, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return ()
            cursor.execute(
                """
                SELECT id, guild_id, discord_user_id, display_name,
                       event_type, role_id, role_binding_key,
                       idempotency_key, actor_user_id, payload, created_at
                FROM bot_onboarding_event
                WHERE guild_id = %s AND event_type = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (guild_id, event_type, limit),
            )
            return tuple(row_to_event(r) for r in (cursor.fetchall() or []))
        finally:
            cursor.close()
            connection.close()

    def _tables_exist(self, cursor: Any) -> bool:
        cursor.execute(
            """
            SELECT
                to_regclass('public.bot_onboarding_config') AS config_table,
                to_regclass('public.bot_onboarding_event') AS event_table
            """
        )
        row = cursor.fetchone()
        return bool(row and row.get('config_table') and row.get('event_table'))


def build_postgres_onboarding_repository(database_url: str) -> PostgresOnboardingRepository:
    return PostgresOnboardingRepository(connection_factory=lambda: psycopg2.connect(dsn=database_url))
