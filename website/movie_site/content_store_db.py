"""Compatibility shim for the canonical shared PostgreSQL content store.

The website runtime now reuses ``shared.content_store_db`` directly so the
database-backed read/write behavior lives in one implementation.
"""

from shared.content_store_db import (
    DEFAULT_TRAILER,
    DbContentReader,
    DbContentWriter,
    get_content_reader,
    get_content_writer,
)

__all__ = [
    'DEFAULT_TRAILER',
    'DbContentReader',
    'DbContentWriter',
    'get_content_reader',
    'get_content_writer',
]
