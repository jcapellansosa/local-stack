"""Postgres access via asyncpg.

A single connection pool is created at startup (see main.lifespan) and
shared across request handlers. Queries are written as plain SQL — no ORM —
because the schema is two columns of interest and the demo benefits from
showing the actual SQL.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import asyncpg

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id         UUID PRIMARY KEY,
    title      TEXT NOT NULL,
    done       BOOLEAN NOT NULL DEFAULT false,
    owner_sub  TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_sub);
"""


@dataclass
class Task:
    id: uuid.UUID
    title: str
    done: bool
    owner_sub: str
    created_at: datetime
    updated_at: datetime

    def public(self) -> dict[str, Any]:
        """Serializable dict for the API (drops owner_sub)."""
        d = asdict(self)
        d.pop("owner_sub")
        d["id"] = str(self.id)
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        return d


async def open_pool(url: str) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)
    return pool


async def list_by_owner(pool: asyncpg.Pool, sub: str) -> list[Task]:
    rows = await pool.fetch(
        """
        SELECT id, title, done, owner_sub, created_at, updated_at
        FROM tasks WHERE owner_sub = $1
        ORDER BY created_at DESC
        """,
        sub,
    )
    return [Task(**dict(r)) for r in rows]


async def create(pool: asyncpg.Pool, sub: str, title: str) -> Task:
    row = await pool.fetchrow(
        """
        INSERT INTO tasks (id, title, owner_sub)
        VALUES ($1, $2, $3)
        RETURNING id, title, done, owner_sub, created_at, updated_at
        """,
        uuid.uuid4(),
        title,
        sub,
    )
    return Task(**dict(row))


async def update(
    pool: asyncpg.Pool,
    sub: str,
    task_id: uuid.UUID,
    *,
    title: str | None = None,
    done: bool | None = None,
) -> Task | None:
    row = await pool.fetchrow(
        """
        UPDATE tasks
        SET title      = COALESCE($3, title),
            done       = COALESCE($4, done),
            updated_at = now()
        WHERE id = $1 AND owner_sub = $2
        RETURNING id, title, done, owner_sub, created_at, updated_at
        """,
        task_id,
        sub,
        title,
        done,
    )
    return Task(**dict(row)) if row else None


async def delete(pool: asyncpg.Pool, sub: str, task_id: uuid.UUID) -> bool:
    result = await pool.execute(
        "DELETE FROM tasks WHERE id = $1 AND owner_sub = $2",
        task_id,
        sub,
    )
    # asyncpg returns "DELETE <n>" — non-zero <n> means a row was removed.
    return result.endswith(" 0") is False
