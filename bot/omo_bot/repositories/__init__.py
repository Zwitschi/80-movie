"""Persistence adapters for bot-owned data will live here."""

from .bot_config_repo import (
    BotManagedRuntimeConfig,
    InMemoryBotConfigRepository,
    PostgresBotConfigRepository,
    build_postgres_bot_config_repository,
)
from .syndication_repo import (
    InMemorySyndicationSourceRepository,
    PostgresSyndicationSourceRepository,
    SyndicationSourceRepository,
    build_postgres_syndication_repository,
)

__all__ = [
    "BotManagedRuntimeConfig",
    "InMemoryBotConfigRepository",
    "PostgresBotConfigRepository",
    "build_postgres_bot_config_repository",
    "InMemorySyndicationSourceRepository",
    "PostgresSyndicationSourceRepository",
    "SyndicationSourceRepository",
    "build_postgres_syndication_repository",
]
