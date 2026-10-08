"""SQLite reference adapter; tombstones are logical deletion, not media erasure."""

from pathlib import Path
import sqlite3

from .model import Memory, ValidationError, identifier, seconds

SCHEMA_VERSION = 1


class SQLiteStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path))
        self._connection.row_factory = sqlite3.Row
        version = self._connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, SCHEMA_VERSION):
            self.close()
            raise ValidationError(f"unsupported SQLite schema version: {version}")
        with self._connection:
            self._connection.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    tenant_id TEXT NOT NULL, memory_id TEXT NOT NULL,
                    subject TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                    recorded_at INTEGER NOT NULL, effective_at INTEGER NOT NULL,
                    expires_at INTEGER, source TEXT NOT NULL,
                    deleted INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1)),
                    PRIMARY KEY (tenant_id, memory_id)
                )
            """)
            self._connection.execute("""
                CREATE INDEX IF NOT EXISTS memory_lookup
                ON memories (tenant_id, subject, key)
            """)
            self._connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @staticmethod
    def _memory(row: sqlite3.Row) -> Memory:
        return Memory(**{name: row[name] for name in Memory.__dataclass_fields__})

    def put(self, memory: Memory) -> bool:
        memory.validate()
        with self._connection:
            row = self._connection.execute(
                "SELECT * FROM memories WHERE tenant_id = ? AND memory_id = ?",
                (memory.tenant_id, memory.memory_id),
            ).fetchone()
            if row is not None:
                if self._memory(row) != memory:
                    raise ValidationError("memory_id reuse with different content is forbidden")
                # An identical replay does not clear an existing tombstone.
                return False
            self._connection.execute(
                """INSERT INTO memories
                (tenant_id, memory_id, subject, key, value, recorded_at,
                 effective_at, expires_at, source) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(getattr(memory, name) for name in Memory.__dataclass_fields__),
            )
        return True

    def delete(self, tenant_id: str, memory_id: str) -> bool:
        identifier(tenant_id, "tenant_id")
        identifier(memory_id, "memory_id")
        with self._connection:
            cursor = self._connection.execute(
                """UPDATE memories SET deleted = 1
                WHERE tenant_id = ? AND memory_id = ? AND deleted = 0""",
                (tenant_id, memory_id),
            )
        return cursor.rowcount == 1

    def search(self, tenant_id: str, subject: str, key: str, at: int) -> tuple[Memory, ...]:
        identifier(tenant_id, "tenant_id")
        identifier(subject, "subject")
        identifier(key, "key")
        seconds(at, "at")
        rows = self._connection.execute(
            """SELECT * FROM memories WHERE tenant_id = ? AND subject = ? AND key = ?
            AND deleted = 0 AND effective_at <= ?
            AND (expires_at IS NULL OR expires_at > ?) ORDER BY memory_id""",
            (tenant_id, subject, key, at, at),
        ).fetchall()
        return tuple(self._memory(row) for row in rows)

    def get(self, tenant_id: str, memory_id: str, at: int) -> Memory | None:
        identifier(tenant_id, "tenant_id")
        identifier(memory_id, "memory_id")
        seconds(at, "at")
        row = self._connection.execute(
            """SELECT * FROM memories WHERE tenant_id = ? AND memory_id = ?
            AND deleted = 0 AND effective_at <= ?
            AND (expires_at IS NULL OR expires_at > ?)""",
            (tenant_id, memory_id, at, at),
        ).fetchone()
        return self._memory(row) if row is not None else None

    def close(self) -> None:
        self._connection.close()
