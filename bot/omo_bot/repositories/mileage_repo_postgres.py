"""PostgreSQL mileage repository implementation."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from ..models import MileageEvent, MileageTier, MileageTotal
from .mileage_repo_common import row_to_event, row_to_tier, row_to_total


class PostgresMileageRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def list_tiers(self, guild_id: int) -> tuple[MileageTier, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return ()
            cursor.execute(
                """
                SELECT id, guild_id, name, points_required, role_id, sort_order, updated_at
                FROM bot_mileage_tier
                WHERE guild_id = %s
                ORDER BY points_required ASC, sort_order ASC, name ASC, id ASC
                """,
                (guild_id,),
            )
            return tuple(row_to_tier(row) for row in cursor.fetchall() or [])
        finally:
            cursor.close()
            connection.close()

    def upsert_tier(self, tier: MileageTier) -> MileageTier:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError('Mileage tables are not available')
            cursor.execute(
                """
                INSERT INTO bot_mileage_tier (id, guild_id, name, points_required, role_id, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id)
                DO UPDATE SET
                    guild_id = EXCLUDED.guild_id,
                    name = EXCLUDED.name,
                    points_required = EXCLUDED.points_required,
                    role_id = EXCLUDED.role_id,
                    sort_order = EXCLUDED.sort_order
                RETURNING id, guild_id, name, points_required, role_id, sort_order, updated_at
                """,
                (tier.tier_id, tier.guild_id, tier.name,
                 tier.points_required, tier.role_id, tier.sort_order),
            )
            row = cursor.fetchone()
            connection.commit()
            return row_to_tier(row) if row else replace(tier)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def list_user_totals(
        self,
        guild_id: int,
        *,
        search: str = '',
        tier_id: str | None = None,
    ) -> tuple[MileageTotal, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        clauses = ['guild_id = %s']
        params: list[object] = [guild_id]
        normalized_search = search.strip().lower()
        if normalized_search:
            clauses.append(
                '(LOWER(display_name) LIKE %s OR LOWER(discord_user_id) LIKE %s)')
            params.extend([f'%{normalized_search}%', f'%{normalized_search}%'])
        if tier_id:
            clauses.append('current_tier_id = %s')
            params.append(tier_id)
        where_clause = ' AND '.join(clauses)
        try:
            if not self._tables_exist(cursor):
                return ()
            cursor.execute(
                f"""
                SELECT guild_id, discord_user_id, display_name, total_points,
                       current_tier_id, current_tier_name, last_event_id,
                       last_event_at, updated_at
                FROM bot_mileage_total
                WHERE {where_clause}
                ORDER BY total_points DESC, display_name ASC, discord_user_id ASC
                """,
                tuple(params),
            )
            return tuple(row_to_total(row) for row in cursor.fetchall() or [])
        finally:
            cursor.close()
            connection.close()

    def get_user_total(self, guild_id: int, discord_user_id: str) -> MileageTotal | None:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return None
            cursor.execute(
                """
                SELECT guild_id, discord_user_id, display_name, total_points,
                       current_tier_id, current_tier_name, last_event_id,
                       last_event_at, updated_at
                FROM bot_mileage_total
                WHERE guild_id = %s AND discord_user_id = %s
                """,
                (guild_id, discord_user_id),
            )
            row = cursor.fetchone()
            return row_to_total(row) if row else None
        finally:
            cursor.close()
            connection.close()

    def save_user_total(self, total: MileageTotal) -> MileageTotal:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError('Mileage tables are not available')
            cursor.execute(
                """
                INSERT INTO bot_mileage_total (
                    guild_id,
                    discord_user_id,
                    display_name,
                    total_points,
                    current_tier_id,
                    current_tier_name,
                    last_event_id,
                    last_event_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (guild_id, discord_user_id)
                DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    total_points = EXCLUDED.total_points,
                    current_tier_id = EXCLUDED.current_tier_id,
                    current_tier_name = EXCLUDED.current_tier_name,
                    last_event_id = EXCLUDED.last_event_id,
                    last_event_at = EXCLUDED.last_event_at
                RETURNING guild_id, discord_user_id, display_name, total_points,
                          current_tier_id, current_tier_name, last_event_id,
                          last_event_at, updated_at
                """,
                (
                    total.guild_id,
                    total.discord_user_id,
                    total.display_name,
                    total.total_points,
                    total.current_tier_id,
                    total.current_tier_name,
                    total.last_event_id,
                    total.last_event_at,
                ),
            )
            row = cursor.fetchone()
            connection.commit()
            return row_to_total(row) if row else replace(total)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def append_event(self, event: MileageEvent) -> MileageEvent:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError('Mileage tables are not available')
            cursor.execute(
                """
                INSERT INTO bot_mileage_event (
                    id, guild_id, discord_user_id, display_name, event_type,
                    points_delta, reason, actor_user_id, correlation_id,
                    reversed_event_id, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING created_at
                """,
                (
                    event.event_id,
                    event.guild_id,
                    event.discord_user_id,
                    event.display_name,
                    event.event_type,
                    event.points_delta,
                    event.reason,
                    event.actor_user_id,
                    event.correlation_id,
                    event.reversed_event_id,
                    Json(event.metadata),
                ),
            )
            row = cursor.fetchone()
            connection.commit()
            return replace(event, created_at=row['created_at'] if row else event.created_at)
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def get_event(self, event_id: str) -> MileageEvent | None:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return None
            cursor.execute(
                """
                SELECT id, guild_id, discord_user_id, display_name, event_type,
                       points_delta, reason, actor_user_id, correlation_id,
                       reversed_event_id, metadata, created_at
                FROM bot_mileage_event
                WHERE id = %s
                """,
                (event_id,),
            )
            row = cursor.fetchone()
            return row_to_event(row) if row else None
        finally:
            cursor.close()
            connection.close()

    def list_user_events(
        self,
        guild_id: int,
        discord_user_id: str,
        *,
        limit: int = 50,
    ) -> tuple[MileageEvent, ...]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return ()
            cursor.execute(
                """
                SELECT id, guild_id, discord_user_id, display_name, event_type,
                       points_delta, reason, actor_user_id, correlation_id,
                       reversed_event_id, metadata, created_at
                FROM bot_mileage_event
                WHERE guild_id = %s AND discord_user_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (guild_id, discord_user_id, limit),
            )
            return tuple(row_to_event(row) for row in cursor.fetchall() or [])
        finally:
            cursor.close()
            connection.close()

    def has_reversal_for(self, event_id: str) -> bool:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return False
            cursor.execute(
                """
                SELECT 1
                FROM bot_mileage_event
                WHERE reversed_event_id = %s
                LIMIT 1
                """,
                (event_id,),
            )
            return bool(cursor.fetchone())
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
                    to_regclass('public.bot_mileage_event') AS event_table,
                    to_regclass('public.bot_mileage_total') AS total_table,
                    to_regclass('public.bot_mileage_tier') AS tier_table
                """
            )
            row = cursor.fetchone()
            return bool(row and row.get('event_table') and row.get('total_table') and row.get('tier_table'))
        finally:
            if owns_cursor:
                cursor.close()
                assert connection is not None
                connection.close()


def build_postgres_mileage_repository(database_url: str) -> PostgresMileageRepository:
    return PostgresMileageRepository(connection_factory=lambda: psycopg2.connect(dsn=database_url))
