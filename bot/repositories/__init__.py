"""Persistence adapters for bot-owned data will live here."""

from .bot_config_repo_common import BotManagedRuntimeConfig
from .bot_config_repo_memory import InMemoryBotConfigRepository
from .bot_config_repo_postgres import PostgresBotConfigRepository, build_postgres_bot_config_repository
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
from .queue_repo_common import QueueRepository
from .queue_repo_memory import InMemoryQueueRepository
from .queue_repo_postgres import PostgresQueueRepository, build_postgres_queue_repository
from .mileage_repo_common import MileageRepository
from .mileage_repo_memory import InMemoryMileageRepository
from .mileage_repo_postgres import PostgresMileageRepository, build_postgres_mileage_repository
from .onboarding_repo_common import OnboardingRepository
from .onboarding_repo_memory import InMemoryOnboardingRepository
from .onboarding_repo_postgres import PostgresOnboardingRepository, build_postgres_onboarding_repository
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
