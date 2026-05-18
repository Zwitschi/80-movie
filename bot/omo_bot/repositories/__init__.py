"""Persistence adapters for bot-owned data will live here."""

from .bot_config_repo import (
    BotManagedRuntimeConfig,
    InMemoryBotConfigRepository,
    PostgresBotConfigRepository,
    build_postgres_bot_config_repository,
)
from .audit_repo import (
    BotAuditLogEntry,
    BotAuditLogRepository,
    InMemoryBotAuditLogRepository,
    PostgresBotAuditLogRepository,
    build_postgres_bot_audit_log_repository,
)
from .website_content_repo import (
    InMemoryWebsiteContentRepository,
    WebsiteContentRepository,
)
from .syndication_repo import (
    InMemorySyndicationSourceRepository,
    PostgresSyndicationSourceRepository,
    SyndicationSourceRepository,
    build_postgres_syndication_repository,
)

__all__ = [
    "BotAuditLogEntry",
    "BotAuditLogRepository",
    "InMemoryBotAuditLogRepository",
    "PostgresBotAuditLogRepository",
    "build_postgres_bot_audit_log_repository",
    "BotManagedRuntimeConfig",
    "InMemoryBotConfigRepository",
    "InMemoryWebsiteContentRepository",
    "PostgresBotConfigRepository",
    "build_postgres_bot_config_repository",
    "InMemorySyndicationSourceRepository",
    "PostgresSyndicationSourceRepository",
    "SyndicationSourceRepository",
    "WebsiteContentRepository",
    "build_postgres_syndication_repository",
]
