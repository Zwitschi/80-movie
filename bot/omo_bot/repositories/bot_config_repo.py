"""Repository seams for bot runtime configuration state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import psycopg2
from psycopg2.extras import RealDictCursor


@dataclass(frozen=True)
class BotManagedRuntimeConfig:
    guild_id: int | None
    channel_map: dict[str, int]
    role_map: dict[str, int]
    managed_by_repository: bool


class InMemoryBotConfigRepository:
    def __init__(
        self,
        *,
        guild_id: int | None = None,
        channel_map: dict[str, int] | None = None,
        role_map: dict[str, int] | None = None,
    ) -> None:
        self._guild_id = guild_id
        self._channel_map = dict(channel_map or {})
        self._role_map = dict(role_map or {})

    def load_runtime_config(
        self,
        *,
        default_guild_id: int | None,
        default_channel_map: dict[str, int],
        default_role_map: dict[str, int],
    ) -> BotManagedRuntimeConfig:
        return BotManagedRuntimeConfig(
            guild_id=self._guild_id if self._guild_id is not None else default_guild_id,
            channel_map=dict(self._channel_map or default_channel_map),
            role_map=dict(self._role_map or default_role_map),
            managed_by_repository=True,
        )

    def get_active_guild_id(self) -> int | None:
        return self._guild_id

    def set_active_guild_id(self, guild_id: int) -> int:
        self._guild_id = guild_id
        return guild_id

    def list_channel_bindings(self, guild_id: int | None = None) -> list[dict[str, int | str]]:
        resolved_guild_id = guild_id if guild_id is not None else self._guild_id
        if resolved_guild_id is None:
            return []
        return [
            {
                "guild_id": resolved_guild_id,
                "binding_key": binding_key,
                "channel_id": channel_id,
            }
            for binding_key, channel_id in sorted(self._channel_map.items())
        ]

    def upsert_channel_binding(
        self,
        *,
        guild_id: int,
        binding_key: str,
        channel_id: int,
    ) -> dict[str, int | str]:
        self._guild_id = guild_id
        self._channel_map[binding_key] = channel_id
        return {
            "guild_id": guild_id,
            "binding_key": binding_key,
            "channel_id": channel_id,
        }

    def delete_channel_binding(self, *, guild_id: int, binding_key: str) -> bool:
        if self._guild_id != guild_id or binding_key not in self._channel_map:
            return False
        del self._channel_map[binding_key]
        return True

    def list_role_bindings(self, guild_id: int | None = None) -> list[dict[str, int | str]]:
        resolved_guild_id = guild_id if guild_id is not None else self._guild_id
        if resolved_guild_id is None:
            return []
        return [
            {
                "guild_id": resolved_guild_id,
                "binding_key": binding_key,
                "role_id": role_id,
            }
            for binding_key, role_id in sorted(self._role_map.items())
        ]

    def upsert_role_binding(
        self,
        *,
        guild_id: int,
        binding_key: str,
        role_id: int,
    ) -> dict[str, int | str]:
        self._guild_id = guild_id
        self._role_map[binding_key] = role_id
        return {
            "guild_id": guild_id,
            "binding_key": binding_key,
            "role_id": role_id,
        }

    def delete_role_binding(self, *, guild_id: int, binding_key: str) -> bool:
        if self._guild_id != guild_id or binding_key not in self._role_map:
            return False
        del self._role_map[binding_key]
        return True


class PostgresBotConfigRepository:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def load_runtime_config(
        self,
        *,
        default_guild_id: int | None,
        default_channel_map: dict[str, int],
        default_role_map: dict[str, int],
    ) -> BotManagedRuntimeConfig:
        guild_id = self.get_active_guild_id()
        if guild_id is None:
            return BotManagedRuntimeConfig(
                guild_id=default_guild_id,
                channel_map=dict(default_channel_map),
                role_map=dict(default_role_map),
                managed_by_repository=self._tables_exist(),
            )

        return BotManagedRuntimeConfig(
            guild_id=guild_id,
            channel_map={
                str(binding["binding_key"]): int(binding["channel_id"])
                for binding in self.list_channel_bindings(guild_id)
            }
            or dict(default_channel_map),
            role_map={
                str(binding["binding_key"]): int(binding["role_id"])
                for binding in self.list_role_bindings(guild_id)
            }
            or dict(default_role_map),
            managed_by_repository=True,
        )

    def get_active_guild_id(self) -> int | None:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return None
            cursor.execute(
                """
                SELECT guild_id
                FROM bot_guild_config
                WHERE is_active = true
                ORDER BY updated_at DESC, guild_id ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            return int(row["guild_id"]) if row else None
        finally:
            cursor.close()
            connection.close()

    def set_active_guild_id(self, guild_id: int) -> int:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError(
                    "Bot configuration tables are not available")
            cursor.execute(
                "UPDATE bot_guild_config SET is_active = false WHERE guild_id <> %s",
                (guild_id,),
            )
            cursor.execute(
                """
                INSERT INTO bot_guild_config (guild_id, is_active)
                VALUES (%s, true)
                ON CONFLICT (guild_id)
                DO UPDATE SET is_active = true
                """,
                (guild_id,),
            )
            connection.commit()
            return guild_id
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def list_channel_bindings(self, guild_id: int | None = None) -> list[dict[str, int | str]]:
        resolved_guild_id = guild_id if guild_id is not None else self.get_active_guild_id()
        if resolved_guild_id is None:
            return []

        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return []
            cursor.execute(
                """
                SELECT guild_id, binding_key, channel_id
                FROM bot_channel_binding
                WHERE guild_id = %s
                ORDER BY binding_key ASC
                """,
                (resolved_guild_id,),
            )
            return [dict(row) for row in cursor.fetchall() or []]
        finally:
            cursor.close()
            connection.close()

    def upsert_channel_binding(
        self,
        *,
        guild_id: int,
        binding_key: str,
        channel_id: int,
    ) -> dict[str, int | str]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError(
                    "Bot configuration tables are not available")
            self._ensure_guild_row(cursor, guild_id)
            cursor.execute(
                """
                INSERT INTO bot_channel_binding (guild_id, binding_key, channel_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (guild_id, binding_key)
                DO UPDATE SET channel_id = EXCLUDED.channel_id
                RETURNING guild_id, binding_key, channel_id
                """,
                (guild_id, binding_key, channel_id),
            )
            row = cursor.fetchone()
            connection.commit()
            return dict(row) if row else {
                "guild_id": guild_id,
                "binding_key": binding_key,
                "channel_id": channel_id,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def delete_channel_binding(self, *, guild_id: int, binding_key: str) -> bool:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError(
                    "Bot configuration tables are not available")
            cursor.execute(
                "DELETE FROM bot_channel_binding WHERE guild_id = %s AND binding_key = %s",
                (guild_id, binding_key),
            )
            deleted = cursor.rowcount > 0
            connection.commit()
            return deleted
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def list_role_bindings(self, guild_id: int | None = None) -> list[dict[str, int | str]]:
        resolved_guild_id = guild_id if guild_id is not None else self.get_active_guild_id()
        if resolved_guild_id is None:
            return []

        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                return []
            cursor.execute(
                """
                SELECT guild_id, binding_key, role_id
                FROM bot_role_binding
                WHERE guild_id = %s
                ORDER BY binding_key ASC
                """,
                (resolved_guild_id,),
            )
            return [dict(row) for row in cursor.fetchall() or []]
        finally:
            cursor.close()
            connection.close()

    def upsert_role_binding(
        self,
        *,
        guild_id: int,
        binding_key: str,
        role_id: int,
    ) -> dict[str, int | str]:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError(
                    "Bot configuration tables are not available")
            self._ensure_guild_row(cursor, guild_id)
            cursor.execute(
                """
                INSERT INTO bot_role_binding (guild_id, binding_key, role_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (guild_id, binding_key)
                DO UPDATE SET role_id = EXCLUDED.role_id
                RETURNING guild_id, binding_key, role_id
                """,
                (guild_id, binding_key, role_id),
            )
            row = cursor.fetchone()
            connection.commit()
            return dict(row) if row else {
                "guild_id": guild_id,
                "binding_key": binding_key,
                "role_id": role_id,
            }
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def delete_role_binding(self, *, guild_id: int, binding_key: str) -> bool:
        connection = self._connection_factory()
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        try:
            if not self._tables_exist(cursor):
                raise RuntimeError(
                    "Bot configuration tables are not available")
            cursor.execute(
                "DELETE FROM bot_role_binding WHERE guild_id = %s AND binding_key = %s",
                (guild_id, binding_key),
            )
            deleted = cursor.rowcount > 0
            connection.commit()
            return deleted
        except Exception:
            connection.rollback()
            raise
        finally:
            cursor.close()
            connection.close()

    def _tables_exist(self, cursor: Any | None = None) -> bool:
        active_cursor = cursor
        active_connection = None
        if active_cursor is None:
            active_connection = self._connection_factory()
            active_cursor = active_connection.cursor(
                cursor_factory=RealDictCursor)

        try:
            active_cursor.execute(
                """
                SELECT
                    to_regclass('public.bot_guild_config') AS guild_table,
                    to_regclass('public.bot_channel_binding') AS channel_table,
                    to_regclass('public.bot_role_binding') AS role_table
                """
            )
            row = active_cursor.fetchone()
            return bool(row and row.get("guild_table") and row.get("channel_table") and row.get("role_table"))
        finally:
            if active_connection is not None:
                active_cursor.close()
                active_connection.close()

    @staticmethod
    def _ensure_guild_row(cursor: Any, guild_id: int) -> None:
        cursor.execute(
            """
            INSERT INTO bot_guild_config (guild_id, is_active)
            VALUES (%s, true)
            ON CONFLICT (guild_id)
            DO NOTHING
            """,
            (guild_id,),
        )


def build_postgres_bot_config_repository(database_url: str) -> PostgresBotConfigRepository:
    return PostgresBotConfigRepository(
        connection_factory=lambda: psycopg2.connect(dsn=database_url)
    )
