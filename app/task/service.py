"""
Service Layer: Encapsulates all business logic for task operations.

This module provides a clean interface for task-related actions, handling
business rules, authorization checks, and database transaction management.
"""

from fastapi import HTTPException
from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log
from app.task import repository
from app.task.models import Task
from app.task.schemas import TaskCreate
from app.task.schemas import TaskUpdate
from app.user.models import User as DBUser


async def create_new_task(
    db: AsyncSession,
    task_data: TaskCreate,
    owner_id: int,
) -> Task:
    """
    Creates a new task for a user, ensuring the operation is atomic
    and returns the fully loaded task object.
    """
    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        status=task_data.status,
        owner_id=owner_id,
    )

    try:
        async with db.begin_nested():
            saved_task = await repository.save(db, new_task)

        task_for_response = await repository.get_by_id_with_owner(db, saved_task.id)

        if not task_for_response:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve created task."
            )

        return task_for_response

    except IntegrityError as e:
        log.warning("IntegrityError creating task: {}", e)
        raise HTTPException(status_code=409, detail="Task could not be created.") from e


async def get_task_by_id(db: AsyncSession, task_id: str, owner_id: int) -> Task:
    """
    Retrieves a single task by its ID, ensuring the requester is the owner.

    Args:
        db: The SQLAlchemy asynchronous session.
        task_id: The string UUID of the task to retrieve.
        owner_id: The ID of the owner of the task.

    Raises:
        HTTPException (404): If the task is not found or not owned by the user.

    Returns:
        The requested Task object.
    """
    task = await repository.get_by_id(db, task_id)
    if not task or task.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return task


async def get_all_tasks_for_user(db: AsyncSession, owner_id: int) -> list[Task]:
    """
    Retrieves all tasks owned by a specific user.

    Args:
        db: The SQLAlchemy asynchronous session.
        owner_id: The ID of the owner of the task.

    Returns:
        A list of Task objects.
    """
    return list(await repository.get_all_for_owner(db, owner_id))


async def update_existing_task(
    db: AsyncSession,
    task_id: str,
    task_data: TaskUpdate,
    owner_id: int,
) -> Task:
    """
    Updates a task, ensuring ownership and performing the update atomically.
    """
    async with db.begin():
        task_to_update = await repository.get_by_id(db, task_id)

        if not task_to_update or task_to_update.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        update_data_dict = task_data.model_dump(exclude_unset=True)
        for key, value in update_data_dict.items():
            setattr(task_to_update, key, value)

        updated_task = await repository.save(db, task_to_update)

    return updated_task


async def delete_task_by_id(
    db: AsyncSession,
    task_id: str,
    current_user: DBUser,
) -> None:
    """
    Deletes a task, allowing admins to delete any task and users their own.

    Args:
        db: The SQLAlchemy asynchronous session.
        task_id: The string UUID of the task to delete.
        current_user: The User model instance of the authenticated user.

    Raises:
        HTTPException (404): If the task is not found.
        HTTPException (403): If the user does not have permission to delete.
    """
    async with db.begin():
        task_to_delete = await repository.get_by_id(db, task_id)
        if not task_to_delete:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )
        # Complex permission check now lives cleanly in the service layer
        user_scopes = set(current_user.scopes.split())
        is_admin = "admin" in user_scopes
        is_owner = task_to_delete.owner_id == current_user.id

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
            )

        await repository.delete(db, task_to_delete)
