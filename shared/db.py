"""Database connection pool helpers.

Supports both Flask app context (via current_app.extensions) and standalone usage
(via explicit pool management). Services can use either pattern depending on their runtime.
"""

import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional


# Flask-specific key
DB_POOL_EXTENSION_KEY = 'shared.db_pool'

# Module-level pool for standalone usage
_standalone_pool: Optional[SimpleConnectionPool] = None
_standalone_dsn: Optional[str] = None


def _get_dsn() -> str:
    """Get database DSN from environment."""
    return os.environ.get('DATABASE_URL', os.environ.get('OMO_DATABASE_URL', ''))


def get_standalone_pool() -> SimpleConnectionPool:
    """Get or create a module-level connection pool for standalone usage."""
    global _standalone_pool, _standalone_dsn
    dsn = _get_dsn()
    if _standalone_pool is None or dsn != _standalone_dsn:
        if _standalone_pool is not None:
            _standalone_pool.closeall()
        _standalone_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=dsn
        )
        _standalone_dsn = dsn
    return _standalone_pool


def get_db_pool(flask_app=None):
    """Get connection pool from Flask app context or standalone pool."""
    if flask_app is not None:
        # Flask app context usage
        pool = flask_app.extensions.get(DB_POOL_EXTENSION_KEY)
        if pool is None:
            pool = SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=flask_app.config['DATABASE_URL']
            )
            flask_app.extensions[DB_POOL_EXTENSION_KEY] = pool
        return pool
    else:
        # Standalone usage
        return get_standalone_pool()


def get_conn(flask_app=None):
    """Get a connection from the pool.

    If flask_app is provided, uses that app's pool.
    If flask_app is None but Flask app context is active, uses current_app.
    Otherwise uses standalone pool.
    """
    if flask_app is not None:
        from flask import g
        if 'db_conn' not in g:
            g.db_conn = get_db_pool(flask_app).getconn()
        return g.db_conn
    else:
        # Try Flask app context
        try:
            from flask import current_app, g
            if current_app:
                if 'db_conn' not in g:
                    g.db_conn = get_db_pool(current_app).getconn()
                return g.db_conn
        except RuntimeError:
            pass
        # Standalone usage
        return get_standalone_pool().getconn()


def get_dict_cursor(flask_app=None):
    """Get a RealDictCursor from the current connection."""
    conn = get_conn(flask_app)
    return conn.cursor(cursor_factory=RealDictCursor)


def close_conn(e=None, flask_app=None):
    """Return connection to the pool.

    If flask_app is provided, uses that app's pool.
    If flask_app is None but Flask app context is active, uses current_app.
    """
    if flask_app is None:
        # Try Flask app context
        try:
            from flask import current_app
            flask_app = current_app
        except RuntimeError:
            return  # No app context, nothing to close

    from flask import g
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        db_pool = flask_app.extensions.get(DB_POOL_EXTENSION_KEY)
        if db_pool is not None:
            db_pool.putconn(db_conn)
        else:
            db_conn.close()


@contextmanager
def get_connection():
    """Context manager for standalone DB connections."""
    pool = get_standalone_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


@contextmanager
def get_dict_cursor_ctx():
    """Context manager for standalone dict cursor with auto-cleanup."""
    pool = get_standalone_pool()
    conn = pool.getconn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cursor, conn
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        pool.putconn(conn)


def init_app(app):
    """Initialize Flask app with DB connection teardown."""
    app.teardown_appcontext(close_conn)
