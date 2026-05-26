"""DB-backed structured logging for all OMO services.

Provides:
- `DbLogHandler` — logging.Handler subclass that writes to `app_log` table
- `write_log(service_name, level, message, metadata=None)` — direct write
- `query_logs(...)` — read back for viewer

Usage:
    import logging
    from shared.logging_db import DbLogHandler

    logger = logging.getLogger(__name__)
    logger.addHandler(DbLogHandler())

Tables: app_log (created by migration 011_add_app_log.sql)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .db import get_standalone_pool


def _get_pool():
    """Get DB pool, return None if unavailable."""
    try:
        return get_standalone_pool()
    except Exception:
        return None


_SERVICE_NAME: str | None = None


def set_service_name(name: str) -> None:
    """Set service name for this process. Called once at startup."""
    global _SERVICE_NAME
    _SERVICE_NAME = name


def _resolve_service_name() -> str:
    if _SERVICE_NAME:
        return _SERVICE_NAME
    import os
    return os.environ.get('OMO_SERVICE_NAME', 'unknown')


class DbLogHandler(logging.Handler):
    """Logging handler that writes records to app_log table."""

    def __init__(self, level: int = logging.NOTSET) -> None:
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            metadata: dict[str, Any] = {}
            if record.exc_info and record.exc_info[0]:
                metadata['exc_type'] = record.exc_info[0].__name__
                metadata['exc_message'] = str(record.exc_info[1])
            if hasattr(record, 'extra_metadata') and isinstance(record.extra_metadata, dict):
                metadata.update(record.extra_metadata)

            pool = _get_pool()
            if pool is None:
                return
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO app_log (id, timestamp, service_name, log_level, message, metadata)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (
                            str(uuid.uuid4()),
                            datetime.fromtimestamp(record.created, tz=timezone.utc),
                            _resolve_service_name(),
                            record.levelname,
                            record.getMessage(),
                            json.dumps(metadata) if metadata else None,
                        ),
                    )
                conn.commit()
            finally:
                pool.putconn(conn)
        except Exception:
            self.handleError(record)


def write_log(
    service_name: str,
    level: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write a log entry directly to app_log table."""
    pool = _get_pool()
    if pool is None:
        return
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO app_log (id, timestamp, service_name, log_level, message, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    str(uuid.uuid4()),
                    datetime.now(timezone.utc),
                    service_name,
                    level.upper(),
                    message,
                    json.dumps(metadata) if metadata else None,
                ),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        pool.putconn(conn)


def query_logs(
    *,
    service_name: str | None = None,
    log_level: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query app_log table. Returns list of dicts ordered by timestamp DESC."""
    pool = _get_pool()
    if pool is None:
        return []

    conditions: list[str] = []
    params: list[Any] = []

    if service_name:
        conditions.append("service_name = %s")
        params.append(service_name)
    if log_level:
        conditions.append("log_level = %s")
        params.append(log_level.upper())

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT id, timestamp, service_name, log_level, message, metadata
                    FROM app_log
                    WHERE {where_clause}
                    ORDER BY timestamp DESC
                    LIMIT %s OFFSET %s""",
                (*params, limit, offset),
            )
            rows = cur.fetchall()
            from psycopg2.extras import RealDictCursor
            cur.close()
            # Re-execute with RealDictCursor for named columns
            with conn.cursor(cursor_factory=RealDictCursor) as dict_cur:
                dict_cur.execute(
                    f"""SELECT id, timestamp, service_name, log_level, message, metadata
                        FROM app_log
                        WHERE {where_clause}
                        ORDER BY timestamp DESC
                        LIMIT %s OFFSET %s""",
                    (*params, limit, offset),
                )
                return [dict(row) for row in dict_cur.fetchall()]
    except Exception:
        return []
    finally:
        pool.putconn(conn)


def get_log_count(
    *,
    service_name: str | None = None,
    log_level: str | None = None,
) -> int:
    """Count log entries matching filters."""
    pool = _get_pool()
    if pool is None:
        return 0

    conditions: list[str] = []
    params: list[Any] = []

    if service_name:
        conditions.append("service_name = %s")
        params.append(service_name)
    if log_level:
        conditions.append("log_level = %s")
        params.append(log_level.upper())

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM app_log WHERE {where_clause}",
                params,
            )
            return cur.fetchone()[0]
    except Exception:
        return 0
    finally:
        pool.putconn(conn)


__all__ = [
    "DbLogHandler",
    "write_log",
    "query_logs",
    "get_log_count",
    "set_service_name",
]