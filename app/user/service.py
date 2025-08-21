"""
Service Layer: Encapsulates all business logic for user operations.

This module provides a clean interface for user-related actions, handling
data validation, error handling, and interaction with the repository layer.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi import status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import auth
from app.core.logging import log
from app.user import repository
from app.user.models import User
from app.user.schemas import UserBaseUpdate
from app.user.schemas import UserCreate
from app.user.schemas import UserFullUpdate
from app.user.schemas import UserOut


def _apply_update_to_user(user: User, update_data: BaseModel) -> User:
    """
    Applies partial updates from a Pydantic model to a SQLAlchemy User model.
    """
    update_data_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_data_dict.items():
        setattr(user, key, value)
    return user


async def create_user(db: AsyncSession, user_data: UserCreate) -> UserOut:
    """
    Handles the business logic for creating a new user.

    This function includes checks for existing users to prevent duplicates
    and handles potential race conditions during database insertion.
    """
    existing_user = await repository.get_by_username_or_email(
        db, user_data.username, user_data.email
    )
    if existing_user:
        detail = (
            "Username already exists."
            if existing_user.username == user_data.username
            else "Email already exists."
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    hashed_password = auth.get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        disabled=user_data.disabled,
        scopes=user_data.scopes or "user",
    )

    try:
        created_user = await repository.add_user(db, db_user)
        return UserOut.model_validate(created_user)
    except IntegrityError as e:
        log.warning(
            "IntegrityError creating user '{}' (likely race condition): {}",
            user_data.username,
            e,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that username or email already exists.",
        ) from e


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    """Authenticates a user by verifying their username and password."""
    user = await repository.get_by_username(db, username)
    if not user or not auth.verify_password(password, user.hashed_password):
        return None
    return user


async def list_all_users(db: AsyncSession, limit: int, offset: int) -> list[User]:
    """Lists all users with pagination."""
    return await repository.get_all(db, limit=limit, offset=offset)


async def update_user_by_id(
    db: AsyncSession, user_id: int, update_data: UserFullUpdate
) -> User:
    """
    Updates a user's profile information (admin operation) within an
    explicit, atomic transaction.
    """
    async with db.begin():
        user = await repository.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found.",
            )

        user = _apply_update_to_user(user, update_data)

        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user


async def update_own_profile(
    db: AsyncSession, user: User, update_data: UserBaseUpdate
) -> User:
    """
    Updates the currently authenticated user's own profile within an
    explicit, atomic transaction.
    """
    async with db.begin():
        user = _apply_update_to_user(user, update_data)

        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user
