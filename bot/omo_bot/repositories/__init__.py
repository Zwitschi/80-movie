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
from .queue_repo import (
    InMemoryQueueRepository,
    PostgresQueueRepository,
    QueueRepository,
    build_postgres_queue_repository,
)
from .mileage_repo import (
    InMemoryMileageRepository,
    MileageRepository,
    PostgresMileageRepository,
    build_postgres_mileage_repository,
)
from .onboarding_repo import (
    InMemoryOnboardingRepository,
    OnboardingRepository,
    PostgresOnboardingRepository,
    build_postgres_onboarding_repository,
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
    "InMemoryMileageRepository",
    "InMemoryQueueRepository",
    "InMemoryWebsiteContentRepository",
    "MileageRepository",
    "PostgresBotConfigRepository",
    "PostgresMileageRepository",
    "PostgresQueueRepository",
    "build_postgres_bot_config_repository",
    "build_postgres_mileage_repository",
    "build_postgres_queue_repository",
    "InMemoryOnboardingRepository",
    "InMemorySyndicationSourceRepository",
    "OnboardingRepository",
    "PostgresOnboardingRepository",
    "PostgresSyndicationSourceRepository",
    "QueueRepository",
    "SyndicationSourceRepository",
    "WebsiteContentRepository",
    "build_postgres_onboarding_repository",
    "build_postgres_syndication_repository",
]
