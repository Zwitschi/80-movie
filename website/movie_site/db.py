import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from flask import current_app, g


def get_db_pool():
    if 'db_pool' not in g:
        g.db_pool = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=current_app.config['DATABASE_URL']
        )
    return g.db_pool


def get_conn():
    if 'db_conn' not in g:
        g.db_conn = get_db_pool().getconn()
    return g.db_conn


def get_dict_cursor():
    return get_conn().cursor(cursor_factory=RealDictCursor)


def close_conn(e=None):
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        get_db_pool().putconn(db_conn)


def init_app(app):
    app.teardown_appcontext(close_conn)
