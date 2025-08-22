"""
API Router for Task Management.

Defines the API endpoints for creating, retrieving, updating, and deleting tasks.
"""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Security
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user
from app.db.db_manager import get_db
from app.task.models import Task
from app.task.schemas import TaskCreate
from app.task.schemas import TaskOut
from app.task.schemas import TaskUpdate
from app.task.service import create_new_task
from app.task.service import delete_task_by_id
from app.task.service import get_all_tasks_for_user
from app.task.service import get_task_by_id
from app.task.service import update_existing_task
from app.user.models import User


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("/", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_in: TaskCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Security(get_current_active_user, scopes=["user"])],
) -> Task:
    """Create a new task for the current user."""
    return await create_new_task(db, task_in, current_user.id)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: str,  # to match uuid 36 chars
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Security(get_current_active_user, scopes=["user"])],
) -> Task:
    """Retrieve a specific task owned by the current user."""
    return await get_task_by_id(db, task_id, current_user.id)


@router.get("/", response_model=list[TaskOut])
async def get_tasks(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Security(get_current_active_user, scopes=["user"])],
) -> list[Task]:
    """Retrieve all tasks for the current user."""
    return await get_all_tasks_for_user(db, current_user.id)


@router.put("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    task_in: TaskUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Security(get_current_active_user, scopes=["user"])],
) -> Task:
    """Update a task owned by the current user."""
    return await update_existing_task(db, task_id, task_in, current_user.id)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User,
        Security(get_current_active_user, scopes=["admin", "user"]),
    ],
) -> None:
    """Delete a task. Admins can delete any task; users delete their own."""
    await delete_task_by_id(db, task_id, current_user)
