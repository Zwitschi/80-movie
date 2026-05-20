"""Bootstrap entrypoint for the Discord bot runtime."""

from __future__ import annotations

import asyncio
import logging

from .adapters import SyndicationAdapter, YouTubeSyndicationAdapter
from .config import BotConfig
from .jobs import SyndicationPollingJob
from .repositories import (
    build_postgres_bot_config_repository,
    InMemorySyndicationSourceRepository,
    SyndicationSourceRepository,
    build_postgres_syndication_repository,
    InMemoryQueueRepository,
    QueueRepository,
    build_postgres_queue_repository,
    InMemoryMileageRepository,
    MileageRepository,
    build_postgres_mileage_repository,
    BotAuditLogRepository,
    InMemoryBotAuditLogRepository,
    build_postgres_bot_audit_log_repository,
    InMemoryOnboardingRepository,
    OnboardingRepository,
    build_postgres_onboarding_repository,
)
from .runtime.client import BotRuntime
from .runtime.shutdown import shutdown_runtime
from .runtime.startup import startup_runtime
from .services import (
    DiscordApiSyndicationDeliverySink,
    NullSyndicationDeliverySink,
    SyndicationPlanningService,
    QueueService,
    MileageService,
    BotAuditService,
    OnboardingService,
)


def configure_logging(level: str = "INFO") -> logging.Logger:
    resolved_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=resolved_level,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )

    logger = logging.getLogger("omo_bot")
    logger.setLevel(resolved_level)
    return logger


def build_syndication_repository(config: BotConfig) -> SyndicationSourceRepository:
    if config.database_url:
        return build_postgres_syndication_repository(config.database_url)

    return InMemorySyndicationSourceRepository()


def build_queue_repository(config: BotConfig) -> QueueRepository:
    if config.database_url:
        return build_postgres_queue_repository(config.database_url)

    return InMemoryQueueRepository()


def build_mileage_repository(config: BotConfig) -> MileageRepository:
    if config.database_url:
        return build_postgres_mileage_repository(config.database_url)

    return InMemoryMileageRepository()


def build_audit_repository(config: BotConfig) -> BotAuditLogRepository:
    if config.database_url:
        return build_postgres_bot_audit_log_repository(config.database_url)

    return InMemoryBotAuditLogRepository()


def build_onboarding_repository(config: BotConfig) -> OnboardingRepository:
    if config.database_url:
        return build_postgres_onboarding_repository(config.database_url)

    return InMemoryOnboardingRepository()


def build_syndication_adapters(config: BotConfig) -> dict[str, SyndicationAdapter]:
    adapters: dict[str, SyndicationAdapter] = {}

    if "youtube" in config.syndication_sources:
        adapters["youtube"] = YouTubeSyndicationAdapter(
            payload_loader=lambda: {"items": []})

    return adapters


def build_syndication_delivery_sink(config: BotConfig):
    if config.channel_map:
        return DiscordApiSyndicationDeliverySink(
            bot_token=config.discord_token,
            channel_map=config.channel_map,
        )

    return NullSyndicationDeliverySink()


def build_effective_bot_config(config: BotConfig) -> BotConfig:
    if not config.database_url:
        return config

    try:
        managed_config = build_postgres_bot_config_repository(
            config.database_url,
        ).load_runtime_config(
            default_guild_id=config.guild_id,
            default_channel_map=config.channel_map,
            default_role_map=config.role_map,
        )
    except Exception:
        logging.getLogger("omo_bot").warning(
            "Falling back to env-backed bot config because managed config could not be loaded",
            exc_info=True,
        )
        return config

    return BotConfig(
        discord_token=config.discord_token,
        guild_id=managed_config.guild_id,
        channel_map=managed_config.channel_map,
        database_url=config.database_url,
        syndication_sources=config.syndication_sources,
        syndication_poll_seconds=config.syndication_poll_seconds,
        role_map=managed_config.role_map,
        log_level=config.log_level,
        onboarding_welcome_copy=managed_config.onboarding_welcome_copy or config.onboarding_welcome_copy,
        onboarding_starter_channels=managed_config.onboarding_starter_channels or config.onboarding_starter_channels,
    )


def build_runtime(config: BotConfig, logger: logging.Logger) -> BotRuntime:
    effective_config = build_effective_bot_config(config)
    syndication_repository = build_syndication_repository(effective_config)
    syndication_planning_service = SyndicationPlanningService(
        config=effective_config,
        repository=syndication_repository,
    )
    syndication_delivery_sink = build_syndication_delivery_sink(
        effective_config)
    syndication_polling_job = SyndicationPollingJob(
        planning_service=syndication_planning_service,
        repository=syndication_repository,
        adapters=build_syndication_adapters(effective_config),
        delivery_sink=syndication_delivery_sink,
    )
    queue_repository = build_queue_repository(effective_config)
    queue_service = QueueService(repository=queue_repository)

    mileage_repository = build_mileage_repository(effective_config)
    mileage_service = MileageService(repository=mileage_repository)

    audit_repository = build_audit_repository(effective_config)
    audit_service = BotAuditService(repository=audit_repository)

    onboarding_repository = build_onboarding_repository(effective_config)
    onboarding_service = OnboardingService(
        repository=onboarding_repository, logger=logger)

    return BotRuntime(
        config=effective_config,
        logger=logger,
        syndication_repository=syndication_repository,
        syndication_planning_service=syndication_planning_service,
        syndication_polling_job=syndication_polling_job,
        syndication_delivery_sink=syndication_delivery_sink,
        queue_repository=queue_repository,
        queue_service=queue_service,
        mileage_repository=mileage_repository,
        mileage_service=mileage_service,
        audit_repository=audit_repository,
        audit_service=audit_service,
        onboarding_repository=onboarding_repository,
        onboarding_service=onboarding_service,
    )


async def run(
    config: BotConfig | None = None,
    runtime: BotRuntime | None = None,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    config = config or BotConfig.from_env()
    logger = configure_logging(config.log_level)
    runtime = runtime or build_runtime(config, logger)
    shutdown_event = shutdown_event or asyncio.Event()

    try:
        await startup_runtime(runtime, logger)
        await shutdown_event.wait()
    finally:
        await shutdown_runtime(runtime, logger)


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        configure_logging().info("Shutdown requested by operator")


if __name__ == "__main__":
    main()
