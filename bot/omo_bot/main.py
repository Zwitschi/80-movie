"""Bootstrap entrypoint for the Discord bot runtime."""

from __future__ import annotations

import asyncio
import logging

from .adapters import SyndicationAdapter, YouTubeSyndicationAdapter
from .config import BotConfig
from .jobs import SyndicationPollingJob
from .repositories import (
    InMemorySyndicationSourceRepository,
    SyndicationSourceRepository,
    build_postgres_syndication_repository,
)
from .runtime.client import BotRuntime
from .runtime.shutdown import shutdown_runtime
from .runtime.startup import startup_runtime
from .services import NullSyndicationDeliverySink, SyndicationPlanningService


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


def build_syndication_adapters(config: BotConfig) -> dict[str, SyndicationAdapter]:
    adapters: dict[str, SyndicationAdapter] = {}

    if "youtube" in config.syndication_sources:
        adapters["youtube"] = YouTubeSyndicationAdapter(
            payload_loader=lambda: {"items": []})

    return adapters


def build_runtime(config: BotConfig, logger: logging.Logger) -> BotRuntime:
    syndication_repository = build_syndication_repository(config)
    syndication_planning_service = SyndicationPlanningService(
        config=config,
        repository=syndication_repository,
    )
    syndication_delivery_sink = NullSyndicationDeliverySink()
    syndication_polling_job = SyndicationPollingJob(
        planning_service=syndication_planning_service,
        repository=syndication_repository,
        adapters=build_syndication_adapters(config),
        delivery_sink=syndication_delivery_sink,
    )
    return BotRuntime(
        config=config,
        logger=logger,
        syndication_repository=syndication_repository,
        syndication_planning_service=syndication_planning_service,
        syndication_polling_job=syndication_polling_job,
        syndication_delivery_sink=syndication_delivery_sink,
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
