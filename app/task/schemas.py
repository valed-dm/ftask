"""
Pydantic Schemas for Task Management.

This module defines the data structures for creating, reading, updating,
and paginating task data, ensuring type validation and serialization.
"""

from datetime import datetime
from typing import Annotated
from typing import Optional

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.task.models import TaskStatus


class TaskBase(BaseModel):
    """Base Pydantic model for a Task, containing shared fields."""

    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.CREATED

    model_config = ConfigDict(from_attributes=True)


class TaskCreate(TaskBase):
    """Schema for creating a new task. Inherits all fields from TaskBase."""

    pass


class TaskUpdate(BaseModel):
    """Schema for partially updating an existing task. All fields are optional."""

    title: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: str | None = None
    status: TaskStatus | None = None

    model_config = ConfigDict(from_attributes=True)


class TaskOut(BaseModel):
    """Schema for returning a task to the client. Includes all database fields."""

    id: str
    title: str
    description: str | None
    status: TaskStatus
    owner_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedTasks(BaseModel):
    """Schema for a paginated response of tasks."""

    items: list[TaskOut]
    total: int
    limit: int
    offset: int
