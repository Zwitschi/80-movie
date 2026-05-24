"""Shutdown helpers for the Discord bot runtime."""

from __future__ import annotations

import logging

from .client import BotRuntime


async def shutdown_runtime(runtime: BotRuntime, logger: logging.Logger) -> None:
    await runtime.close()
    logger.info("Bot runtime stopped: %s", runtime.health_snapshot())
