"""Task table and related models, including the TaskStatus enum."""

from enum import Enum
from typing import TYPE_CHECKING
import uuid as uuid_pkg

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db import Base
from app.db import TimestampMixin


if TYPE_CHECKING:
    from app.user.models import User


class TaskStatus(str, Enum):
    """Enumeration for the status of a task."""

    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class Task(Base, TimestampMixin):
    """
    Task model representing the 'tasks' table in the database.

    Attributes:
        id (str): Primary key, a UUID string.
        title (str): The title of the task.
        description (str | None): A detailed description of the task.
        status (TaskStatus): The current status of the task (e.g., created).
        owner_id (int): Foreign key linking to the user who owns the task.
        owner (User): The SQLAlchemy relationship to the owning User object.
    """

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid_pkg.uuid4()),
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="taskstatus"),
        nullable=False,
        default=TaskStatus.CREATED,
        server_default="CREATED",
    )

    owner_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationship: many tasks → one user
    owner: Mapped["User"] = relationship(back_populates="tasks")
