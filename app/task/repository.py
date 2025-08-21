"""
Task Repository: Data Access Layer for task-related operations.

This module provides functions to interact directly with the 'tasks' table,
ensuring that related data (like the owner) is eagerly loaded.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.task.models import Task
from app.user.models import User


async def get_by_id(db: AsyncSession, task_id: str) -> Task | None:
    """

    Retrieve a single task by its UUID, eagerly loading the owner.

    Args:
        db: The SQLAlchemy asynchronous session.
        task_id: The string UUID of the task to retrieve.

    Returns:
        The Task model instance if found, otherwise None.
    """
    stmt = select(Task).where(Task.id == task_id).options(selectinload(Task.owner))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_for_owner(db: AsyncSession, owner: User) -> list[Task]:
    """
    Retrieve all tasks for a specific owner, eagerly loading relationships.

    Args:
        db: The SQLAlchemy asynchronous session.
        owner: The User model instance to filter tasks by.

    Returns:
        A list of Task model instances owned by the user.
    """
    stmt = (
        select(Task)
        .where(Task.owner_id == owner.id)
        .options(selectinload(Task.owner))
        .order_by(Task.id)  # Order by ID for consistent pagination
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create(db: AsyncSession, task: Task) -> Task:
    """

    Adds a new task to the database and returns the complete object.

    Flushes the new task to get its ID, then re-fetches it with the
    owner relationship eagerly loaded to prepare it for serialization.

    Args:
        db: The SQLAlchemy asynchronous session.
        task: The new Task model instance to add.

    Returns:
        The newly created Task instance, fully loaded.
    """
    db.add(task)
    await db.flush()

    stmt = select(Task).where(Task.id == task.id).options(selectinload(Task.owner))
    result = await db.execute(stmt)
    created_task_with_owner = result.scalar_one()

    return created_task_with_owner


async def delete(db: AsyncSession, task: Task) -> None:
    """
    Deletes a task from the database.

    Args:
        db: The SQLAlchemy asynchronous session.
        task: The Task model instance to delete.
    """
    await db.delete(task)
    await db.flush()
