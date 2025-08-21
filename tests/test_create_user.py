from _pytest.monkeypatch import MonkeyPatch
from fastapi import HTTPException
from fastapi import status
from pydantic import ValidationError
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.user.models import User as DBUser
from app.user.schemas import UserCreate
from app.user.service import create_user


async def test_create_user_success(db_session: AsyncSession) -> None:
    """
    Tests successful user creation.
    """
    user_in = UserCreate(
        username="newuser",
        email="new@example.com",
        password="secret123",
        full_name="New User",
        scopes=settings.TEST_SCOPE,
    )

    user_out = await create_user(db_session, user_in)

    assert user_out.username == "newuser"
    assert user_out.email == "new@example.com"
    assert hasattr(user_out, "id")


async def test_create_user_username_exists(
    db_session: AsyncSession, existing_user: DBUser
) -> None:
    """
    Tests that creating a user with an existing username fails.
    """
    user_in = UserCreate(
        username=existing_user.username,
        email="unique@example.com",
        password="secret123",
        scopes=settings.TEST_SCOPE,
    )

    with pytest.raises(HTTPException) as exc:
        await create_user(db_session, user_in)

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert "username" in exc.value.detail.lower()


async def test_create_user_email_exists(
    db_session: AsyncSession, existing_user: DBUser
) -> None:
    """
    Tests that creating a user with an existing email fails.
    """
    user_in = UserCreate(
        username="unique",
        email=existing_user.email,
        password="secret123",
        scopes=settings.TEST_SCOPE,
    )

    with pytest.raises(HTTPException) as exc:
        await create_user(db_session, user_in)

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert "email" in exc.value.detail.lower()


async def test_create_user_integrity_error_username(
    db_session: AsyncSession, monkeypatch: MonkeyPatch
) -> None:
    """
    Tests handling of a race condition where a username already exists.
    """
    user_in = UserCreate(
        username="race",
        email="race@example.com",
        password="secret123",
        scopes=settings.TEST_SCOPE,
    )

    def fake_flush():
        raise IntegrityError("stmt", "params", Exception("ix_users_username"))

    monkeypatch.setattr(db_session, "flush", fake_flush)

    with pytest.raises(HTTPException) as exc:
        await create_user(db_session, user_in)

    assert exc.value.status_code == status.HTTP_409_CONFLICT
    assert "username" in exc.value.detail.lower()


@pytest.mark.parametrize(
    "username, email, expected_status",
    [
        ("user1", "new.user@example.com", status.HTTP_409_CONFLICT),
        ("new.user", "user2@example.com", status.HTTP_409_CONFLICT),
        ("user1", "user1@example.com", status.HTTP_409_CONFLICT),
    ],
)
async def test_create_user_conflict_integration(
    db_session: AsyncSession,
    regular_users: list[DBUser],
    username: str,
    email: str,
    expected_status: int,
) -> None:
    """
    Test creating a user that conflicts with existing user in the database.
    """
    user_in = UserCreate(
        username=username,
        email=email,
        password="a_new_password",
        scopes="user",
    )

    with pytest.raises(HTTPException) as exc:
        await create_user(db_session, user_in)

    assert exc.value.status_code == expected_status
    assert "already exists" in exc.value.detail.lower()


async def test_create_user_invalid_email_format() -> None:
    """
    Tests that creating a user with an invalid email format raises a ValidationError.
    """
    with pytest.raises(ValidationError) as exc:
        UserCreate(
            username="newuser",
            email="new|example.com",
            password="secret123",
            full_name="New User",
            scopes="user",
        )

    assert "email" in str(exc.value)
    # Pydantic v2 provides a more specific error type
    assert "value is not a valid email address" in str(exc.value)
