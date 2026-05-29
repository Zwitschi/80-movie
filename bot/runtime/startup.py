"""Startup helpers for the Discord bot runtime."""

from __future__ import annotations

import asyncio
import logging
import os

from .client import BotRuntime


def _write_bot_worker_heartbeat(
    worker_id: str,
    state: str = "running",
    *,
    database_url: str | None = None,
) -> bool:
    """Write heartbeat row to shared bot_presence table. Returns True on success."""
    import psycopg2

    dsn = database_url or os.environ.get(
        'DATABASE_URL') or os.environ.get('OMO_DATABASE_URL')
    if not dsn:
        return False
    try:
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bot_presence (worker_id, state, started_at, last_seen_at)
                    VALUES (%s, %s, now(), now())
                    ON CONFLICT (worker_id) DO UPDATE SET
                        state = EXCLUDED.state,
                        last_seen_at = now()
                    """,
                    (worker_id, state),
                )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception:
        return False


async def _heartbeat_loop(
    worker_id: str,
    database_url: str | None,
    interval_seconds: int = 60,
    logger: logging.Logger | None = None,
) -> None:
    """Periodically write a heartbeat row while the event loop runs."""
    while True:
        ok = await asyncio.to_thread(
            _write_bot_worker_heartbeat, worker_id, "running", database_url=database_url
        )
        if logger:
            logger.debug("Worker heartbeat: worker=%s ok=%s", worker_id, ok)
        await asyncio.sleep(interval_seconds)


async def startup_runtime(runtime: BotRuntime, logger: logging.Logger) -> None:
    logger.info(
        "Starting Discord bot scaffold: guild=%s channels=%s syndication_sources=%s database=%s",
        runtime.config.guild_id,
        len(runtime.config.channel_map),
        len(runtime.config.syndication_sources),
        "configured" if runtime.config.database_url else "not-configured",
    )
    await runtime.start()

    # Start worker heartbeat
    worker_id = os.environ.get('OMO_BOT_WORKER_ID', 'default')
    asyncio.create_task(
        _heartbeat_loop(
            worker_id,
            database_url=runtime.config.database_url,
            logger=logger,
        )
    )
    logger.info("Bot worker heartbeat started: worker_id=%s", worker_id)
    logger.info("Bot runtime healthy: %s", runtime.health_snapshot())
