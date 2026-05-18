import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from flask import current_app, g


DB_POOL_EXTENSION_KEY = 'movie_site.db_pool'


def get_db_pool():
    pool = current_app.extensions.get(DB_POOL_EXTENSION_KEY)
    if pool is None:
        pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=current_app.config['DATABASE_URL']
        )
        current_app.extensions[DB_POOL_EXTENSION_KEY] = pool
    return pool


def get_conn():
    if 'db_conn' not in g:
        g.db_conn = get_db_pool().getconn()
    return g.db_conn


def get_dict_cursor():
    return get_conn().cursor(cursor_factory=RealDictCursor)


def close_conn(e=None):
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        db_pool = current_app.extensions.get(DB_POOL_EXTENSION_KEY)
        if db_pool is not None:
            db_pool.putconn(db_conn)
        else:
            db_conn.close()


def init_app(app):
    app.teardown_appcontext(close_conn)
