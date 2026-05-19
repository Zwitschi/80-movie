"""Repository seams for mileage ledger, totals, and tier policy."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Protocol

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from ..models import MileageEvent, MileageTier, MileageTotal


class MileageRepository(Protocol):
    def list_tiers(self, guild_id: int) -> tuple[MileageTier, ...]:
        ...

    def upsert_tier(self, tier: MileageTier) -> MileageTier:
        ...

    def list_user_totals(
        self,
        guild_id: int,
        *,
        search: str = '',
        tier_id: str | None = None,
    ) -> tuple[MileageTotal, ...]:
        ...

    def get_user_total(self, guild_id: int, discord_user_id: str) -> MileageTotal | None:
        ...

    def save_user_total(self, total: MileageTotal) -> MileageTotal:
        ...

    def append_event(self, event: MileageEvent) -> MileageEvent:
        ...

    def get_event(self, event_id: str) -> MileageEvent | None:
        ...

    def list_user_events(
        self,
        guild_id: int,
        discord_user_id: str,
        *,
        limit: int = 50,
    ) -> tuple[MileageEvent, ...]:
        ...

    def has_reversal_for(self, event_id: str) -> bool:
        ...


class InMemoryMileageRepository:
    def __init__(self) -> None:
        self._tiers: dict[int, dict[str, MileageTier]] = {}
        self._totals: dict[tuple[int, str], MileageTotal] = {}
        self._events: dict[str, MileageEvent] = {}
        self._events_by_user: dict[tuple[int, str], list[str]] = {}

    def list_tiers(self, guild_id: int) -> tuple[MileageTier, ...]:
        tiers = self._tiers.get(guild_id, {}).values()
        return tuple(
            replace(tier)
            for tier in sorted(tiers, key=lambda item: (item.points_required, item.sort_order, item.name.lower(), item.tier_id))
        )

    def upsert_tier(self, tier: MileageTier) -> MileageTier:
        stored = replace(tier)
        self._tiers.setdefault(tier.guild_id, {})[tier.tier_id] = stored
        return replace(stored)

    def list_user_totals(
        self,
        guild_id: int,
        *,
        search: str = '',
        tier_id: str | None = None,
    ) -> tuple[MileageTotal, ...]:
        normalized_search = search.strip().lower()
        totals = [
            replace(total)
            for (stored_guild_id, _), total in self._totals.items()
            if stored_guild_id == guild_id
        ]
        if normalized_search:
            totals = [
                total
                for total in totals
                if normalized_search in total.display_name.lower()
                or normalized_search in total.discord_user_id.lower()
            ]
        if tier_id:
            totals = [
                total for total in totals if total.current_tier_id == tier_id]
        totals.sort(
            key=lambda item: (
                -item.total_points,
                item.display_name.lower(),
                item.discord_user_id,
            )
        )
        return tuple(totals)

    def get_user_total(self, guild_id: int, discord_user_id: str) -> MileageTotal | None:
        total = self._totals.get((guild_id, discord_user_id))
        return replace(total) if total is not None else None

    def save_user_total(self, total: MileageTotal) -> MileageTotal:
        stored = replace(total)
        self._totals[(total.guild_id, total.discord_user_id)] = stored
        return replace(stored)

    def append_event(self, event: MileageEvent) -> MileageEvent:
        stored = replace(event)
        self._events[event.event_id] = stored
        self._events_by_user.setdefault(
            (event.guild_id, event.discord_user_id), []).insert(0, event.event_id)
        return replace(stored)

    def get_event(self, event_id: str) -> MileageEvent | None:
        event = self._events.get(event_id)
        return replace(event) if event is not None else None

    def list_user_events(
        self,
        guild_id: int,
        discord_user_id: str,
        *,
        limit: int = 50,
    ) -> tuple[MileageEvent, ...]:
        event_ids = self._events_by_user.get(
            (guild_id, discord_user_id), [])[:limit]
        return tuple(replace(self._events[event_id]) for event_id in event_ids)

    def has_reversal_for(self, event_id: str) -> bool:
        return any(event.reversed_event_id == event_id for event in self._events.values())


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
            return tuple(self._row_to_tier(row) for row in cursor.fetchall() or [])
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
            return self._row_to_tier(row) if row else replace(tier)
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
            return tuple(self._row_to_total(row) for row in cursor.fetchall() or [])
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
            return self._row_to_total(row) if row else None
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
            return self._row_to_total(row) if row else replace(total)
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
            return self._row_to_event(row) if row else None
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
            return tuple(self._row_to_event(row) for row in cursor.fetchall() or [])
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

    @staticmethod
    def _row_to_tier(row: dict[str, Any]) -> MileageTier:
        return MileageTier(
            tier_id=str(row['id']),
            guild_id=int(row['guild_id']),
            name=str(row['name']),
            points_required=int(row['points_required']),
            role_id=int(row['role_id']) if row.get(
                'role_id') is not None else None,
            sort_order=int(row['sort_order']),
            updated_at=row.get('updated_at'),
        )

    @staticmethod
    def _row_to_total(row: dict[str, Any]) -> MileageTotal:
        return MileageTotal(
            guild_id=int(row['guild_id']),
            discord_user_id=str(row['discord_user_id']),
            display_name=str(row['display_name']),
            total_points=int(row['total_points']),
            current_tier_id=str(row['current_tier_id']) if row.get(
                'current_tier_id') else None,
            current_tier_name=str(row['current_tier_name']) if row.get(
                'current_tier_name') else None,
            last_event_id=str(row['last_event_id']) if row.get(
                'last_event_id') else None,
            last_event_at=row.get('last_event_at'),
            updated_at=row.get('updated_at'),
        )

    @staticmethod
    def _row_to_event(row: dict[str, Any]) -> MileageEvent:
        metadata = row.get('metadata') or {}
        if not isinstance(metadata, dict):
            metadata = {}
        return MileageEvent(
            event_id=str(row['id']),
            guild_id=int(row['guild_id']),
            discord_user_id=str(row['discord_user_id']),
            display_name=str(row['display_name']),
            event_type=str(row['event_type']),
            points_delta=int(row['points_delta']),
            reason=str(row.get('reason') or ''),
            actor_user_id=str(row['actor_user_id']) if row.get(
                'actor_user_id') else None,
            correlation_id=str(row['correlation_id']) if row.get(
                'correlation_id') else None,
            reversed_event_id=str(row['reversed_event_id']) if row.get(
                'reversed_event_id') else None,
            metadata=metadata,
            created_at=row['created_at'],
        )


def build_postgres_mileage_repository(database_url: str) -> PostgresMileageRepository:
    return PostgresMileageRepository(connection_factory=lambda: psycopg2.connect(dsn=database_url))
