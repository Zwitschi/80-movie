"""Database connection pool helpers — delegates to shared.db."""

from psycopg2.pool import SimpleConnectionPool

from shared.db import (
    DB_POOL_EXTENSION_KEY,
    get_db_pool,
    get_conn,
    get_dict_cursor,
    close_conn,
    init_app,
)

__all__ = [
    'DB_POOL_EXTENSION_KEY',
    'SimpleConnectionPool',
    'get_db_pool',
    'get_conn',
    'get_dict_cursor',
    'close_conn',
    'init_app',
]
