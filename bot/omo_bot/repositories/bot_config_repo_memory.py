"""In-memory bot config repository implementation."""

from __future__ import annotations

from .bot_config_repo_common import BotManagedRuntimeConfig


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
