"""Startup helpers for the Discord bot runtime."""

from __future__ import annotations

import logging

from .client import BotRuntime


async def startup_runtime(runtime: BotRuntime, logger: logging.Logger) -> None:
    logger.info(
        "Starting Discord bot scaffold: guild=%s channels=%s syndication_sources=%s database=%s",
        runtime.config.guild_id,
        len(runtime.config.channel_map),
        len(runtime.config.syndication_sources),
        "configured" if runtime.config.database_url else "not-configured",
    )
    await runtime.start()
    logger.info("Bot runtime healthy: %s", runtime.health_snapshot())
