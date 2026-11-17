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
    p = _get_pool()
    c = p.getconn()
    try:
        c.cursor().execute("SELECT 1")
    except Exception:
        # Connection is dead — replace it with a fresh one
        try:
            p.putconn(c, close=True)
        except Exception:
            pass
        c = psycopg2.connect(os.environ["DATABASE_URL"])
    return c


def put_conn(conn) -> None:
    try:
        _get_pool().putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


class _Conn:
    def __enter__(self):
        self._conn = get_conn()
        return self._conn

    def __exit__(self, exc_type, *_):
        try:
            if exc_type:
                self._conn.rollback()
            else:
                self._conn.commit()
        except Exception:
            pass
        put_conn(self._conn)


def conn() -> _Conn:
    return _Conn()
