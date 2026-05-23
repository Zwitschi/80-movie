"""Shared dataclass and protocol for bot config repositories."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BotManagedRuntimeConfig:
    guild_id: int | None
    channel_map: dict[str, int]
    role_map: dict[str, int]
    managed_by_repository: bool
