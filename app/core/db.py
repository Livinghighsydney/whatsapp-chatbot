from __future__ import annotations
import os
import psycopg2
from psycopg2 import pool

_pool: pool.SimpleConnectionPool | None = None


def _get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        _pool = pool.SimpleConnectionPool(1, 10, os.environ["DATABASE_URL"])
    return _pool


def get_conn():
    return _get_pool().getconn()


def put_conn(conn) -> None:
    _get_pool().putconn(conn)


class _Conn:
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
