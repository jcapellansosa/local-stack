"""/api/* — JSON endpoints. All require an authenticated session."""

from __future__ import annotations

import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..auth import Session
from ..deps import get_pool, require_session

router = APIRouter(prefix="/api")


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None


@router.get("/me")
async def me(sess: Session = Depends(require_session)):
    return {"sub": sess.sub, "email": sess.email, "name": sess.name}


@router.get("/tasks")
async def list_tasks(
    pool: asyncpg.Pool = Depends(get_pool),
    sess: Session = Depends(require_session),
):
    tasks = await db.list_by_owner(pool, sess.sub)
    return [t.public() for t in tasks]


@router.post("/tasks", status_code=201)
async def create_task(
    body: TaskCreate,
    pool: asyncpg.Pool = Depends(get_pool),
    sess: Session = Depends(require_session),
):
    t = await db.create(pool, sess.sub, body.title.strip())
    return t.public()


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    body: TaskPatch,
    pool: asyncpg.Pool = Depends(get_pool),
    sess: Session = Depends(require_session),
):
    t = await db.update(pool, sess.sub, task_id, title=body.title, done=body.done)
    if t is None:
        raise HTTPException(status_code=404, detail="not found")
    return t.public()


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID,
    pool: asyncpg.Pool = Depends(get_pool),
    sess: Session = Depends(require_session),
):
    if not await db.delete(pool, sess.sub, task_id):
        raise HTTPException(status_code=404, detail="not found")
