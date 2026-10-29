"""Durable event and key-value storage.

Local development uses SQLite. When ``REDIS_URL`` is set, the same interface
writes to Redis so sessions and price history survive restarts and more than
one app process. Production without Redis stays in memory and does not create
local files on a read-only host.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_EVENTS = 400


class EventLog:
    def append(self, namespace: str, key: str, row: dict) -> None:
        raise NotImplementedError

    def read(self, namespace: str, key: str) -> list[dict]:
        raise NotImplementedError

    def close(self) -> None:
        return None


class MemoryEventLog(EventLog):
    def __init__(self, max_rows: int = _MAX_EVENTS):
        self.max_rows = max_rows
        self._rows: dict[tuple[str, str], list[dict]] = {}
        self._lock = threading.RLock()

    def append(self, namespace: str, key: str, row: dict) -> None:
        with self._lock:
            bucket = self._rows.setdefault((namespace, key), [])
            bucket.append(dict(row))
            if len(bucket) > self.max_rows:
                self._rows[(namespace, key)] = bucket[-self.max_rows :]

    def read(self, namespace: str, key: str) -> list[dict]:
        with self._lock:
            return [dict(row) for row in self._rows.get((namespace, key), [])]


class SqliteEventLog(EventLog):
    def __init__(self, path: Path, max_rows: int = _MAX_EVENTS):
        self.max_rows = max_rows
        self.path = path
        self._lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL,
                item_key TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_key ON events(namespace, item_key, id)"
        )
        self._connection.commit()

    def append(self, namespace: str, key: str, row: dict) -> None:
        payload = json.dumps(row, ensure_ascii=False)
        with self._lock:
            self._connection.execute(
                "INSERT INTO events(namespace, item_key, payload) VALUES (?, ?, ?)",
                (namespace, key, payload),
            )
            self._connection.execute(
                """
                DELETE FROM events
                WHERE namespace = ? AND item_key = ? AND id NOT IN (
                    SELECT id FROM events
                    WHERE namespace = ? AND item_key = ?
                    ORDER BY id DESC LIMIT ?
                )
                """,
                (namespace, key, namespace, key, self.max_rows),
            )
            self._connection.commit()

    def read(self, namespace: str, key: str) -> list[dict]:
        with self._lock:
            fetched = self._connection.execute(
                "SELECT payload FROM events WHERE namespace = ? AND item_key = ? ORDER BY id ASC",
                (namespace, key),
            ).fetchall()
        return [json.loads(row[0]) for row in fetched]

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class RedisEventLog(EventLog):
    def __init__(self, client, max_rows: int = _MAX_EVENTS):
        self.client = client
        self.max_rows = max_rows

    def append(self, namespace: str, key: str, row: dict) -> None:
        redis_key = f"sabad:{namespace}:{key}"
        self.client.rpush(redis_key, json.dumps(row, ensure_ascii=False))
        self.client.ltrim(redis_key, -self.max_rows, -1)

    def read(self, namespace: str, key: str) -> list[dict]:
        raw = self.client.lrange(f"sabad:{namespace}:{key}", 0, -1) or []
        return [json.loads(item) for item in raw]


class RedisKv:
    """Small JSON map for store-login sessions."""

    def __init__(self, client):
        self.client = client

    def get(self, key: str) -> Optional[dict]:
        raw = self.client.get(f"sabad:kv:{key}")
        if not raw:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None

    def set(self, key: str, value: dict) -> None:
        self.client.set(f"sabad:kv:{key}", json.dumps(value, ensure_ascii=False))

    def delete(self, key: str) -> None:
        self.client.delete(f"sabad:kv:{key}")


def redis_client():
    """Return a Redis client when ``REDIS_URL`` is set and the package is installed."""
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    try:
        import redis
    except ImportError:
        logger.warning("REDIS_URL is set but the redis package is not installed")
        return None
    return redis.Redis.from_url(url, decode_responses=True, socket_timeout=2.0)


def _serverless() -> bool:
    return bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_VERSION"))


def _production_without_disk() -> bool:
    return os.getenv("SABAD_ENV", "").lower() == "production" or _serverless()


def open_event_log(filename: str, path: Optional[str] = None) -> EventLog:
    if path:
        return SqliteEventLog(Path(path))
    client = redis_client()
    if client is not None:
        return RedisEventLog(client)
    if _production_without_disk():
        logger.warning(
            "Using in-memory %s because REDIS_URL is not configured on this host",
            filename,
        )
        return MemoryEventLog()
    data_dir = Path(__file__).resolve().parent.parent / ".data"
    return SqliteEventLog(data_dir / filename)


def open_session_kv() -> Optional[RedisKv]:
    client = redis_client()
    if client is None:
        return None
    return RedisKv(client)
