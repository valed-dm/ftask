"""
User Repository: Data Access Layer for user-related database operations.

This module provides functions to interact directly with the 'users' table.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.user.models import User


async def get_all(db: AsyncSession, limit: int, offset: int) -> list[User]:
    """
    Retrieve all users with pagination.

    Args:
        db: The SQLAlchemy asynchronous session.
        limit: The maximum number of users to return.
        offset: The number of users to skip.

    Returns:
        A list of user model instances.
    """
    stmt = select(User).order_by(User.id).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    """
    Retrieve a single user by their primary key ID.

    Args:
        db: The SQLAlchemy asynchronous session.
        user_id: The ID of the user to retrieve.

    Returns:
        The user model instance if found, otherwise None.
    """
    return await db.get(User, user_id)


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    """
    Retrieve a user by their username.

    Args:
        db: The SQLAlchemy asynchronous session.
        username: The username to search for.

    Returns:
        The user model instance if found, otherwise None.
    """
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_by_username_or_email(
    db: AsyncSession, username: str, email: Optional[str]
) -> Optional[User]:
    """
    Retrieve a user by username or email.

    Args:
        db: The SQLAlchemy asynchronous session.
        username: The username to search for.
        email: The optional email to search for.

    Returns:
        The user model instance if a match is found, otherwise None.
    """
    clauses = [User.username == username]
    if email is not None:
        clauses.append(User.email == email)

    statement = select(User).where(or_(*clauses))
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def add_user(db: AsyncSession, user: User) -> User:
    """
    Add a new user object to the database.

    Args:
        db: The SQLAlchemy asynchronous session.
        user: The user model instance to add.

    Returns:
        The newly created user instance with its database-generated ID.
    """
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user
