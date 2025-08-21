"""Users table and related models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.db.timestamp import TimestampMixin


if TYPE_CHECKING:
    from app.task.models import Task


class User(Base, TimestampMixin):
    """
    User model representing the 'users' table in the database.

    Attributes:
        id (int): Primary key.
        username (str): Unique username.
        email (str | None): Unique email address.
        hashed_password (str): Hashed password for the user.
        full_name (str | None): User's full name.
        disabled (bool): Flag to indicate if the user account is active.
        scopes (str): Space-separated string of authorization scopes.
        tasks (list["Task"]): A list of tasks associated with the user.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    # Increased email length to standard recommendation
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scopes: Mapped[str] = mapped_column(String(255), default="", nullable=False)

    # Relationship: one user → many tasks
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="owner",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
