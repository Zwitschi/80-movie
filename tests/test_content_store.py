import pytest

from website.app import create_app
from website.movie_site import db


class FakeConnection:
    def cursor(self, cursor_factory=None):
        return object()

    def close(self):
        pass


class FakePool:
    def __init__(self):
        self.connection = FakeConnection()
        self.getconn_calls = 0
        self.putconn_calls = []

    def getconn(self):
        self.getconn_calls += 1
        return self.connection

    def putconn(self, connection):
        self.putconn_calls.append(connection)


def test_db_pool_is_app_scoped_and_releases_connections(monkeypatch):
    fake_pool = FakePool()

    def build_pool(minconn, maxconn, dsn):
        assert minconn == 1
        assert maxconn == 10
        assert dsn
        return fake_pool

    # Patch both shared.db and website.movie_site.db to cover all import paths
    monkeypatch.setattr('shared.db.SimpleConnectionPool', build_pool)
    monkeypatch.setattr(
        'website.movie_site.db.SimpleConnectionPool', build_pool)

    app = create_app()
    app.config['TESTING'] = True

    with app.app_context():
        # Clear any cached pool from previous tests
        app.extensions.pop(db.DB_POOL_EXTENSION_KEY, None)
        pool = db.get_db_pool()
        assert pool is fake_pool
        assert db.get_db_pool() is fake_pool
        assert db.get_conn() is fake_pool.connection

    assert fake_pool.getconn_calls == 1
    assert fake_pool.putconn_calls == [fake_pool.connection]

    with app.app_context():
        assert db.get_db_pool() is fake_pool

