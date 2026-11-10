"""Neon PostgreSQL connection pool."""
from __future__ import annotations

import os
import psycopg2
from psycopg2 import pool

_pool: pool.SimpleConnectionPool | None = None


def _get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        url = os.environ["DATABASE_URL"]
        _pool = pool.SimpleConnectionPool(1, 10, url)
    return _pool


def get_conn():
    return _get_pool().getconn()


def put_conn(conn) -> None:
    _get_pool().putconn(conn)


class _Conn:
    """Context manager — borrows a connection from the pool and returns it."""
    def __enter__(self):
        self._conn = get_conn()
        return self._conn

    def __exit__(self, exc_type, *_):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        put_conn(self._conn)


def conn() -> _Conn:
    return _Conn()
