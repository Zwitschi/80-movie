"""Bootstrap entrypoint for the Discord bot runtime."""

from __future__ import annotations

import asyncio
import logging

from .config import BotConfig
from .runtime.client import BotRuntime
from .runtime.shutdown import shutdown_runtime
from .runtime.startup import startup_runtime


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


async def run(
    config: BotConfig | None = None,
    runtime: BotRuntime | None = None,
    shutdown_event: asyncio.Event | None = None,
) -> None:
    config = config or BotConfig.from_env()
    logger = configure_logging(config.log_level)
    runtime = runtime or BotRuntime(config=config, logger=logger)
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
