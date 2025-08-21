from datetime import datetime
from datetime import timedelta
from datetime import timezone
from time import sleep

import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.user.models import User as DBUser


class TestUserModel:
    """
    Test suite for the User database model.
    """

    async def test_successful_user_creation(self, db_session: AsyncSession) -> None:
        """
        Tests that a user can be created successfully with all fields populated.
        """
        user = DBUser(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            hashed_password="a_very_secure_hash",
            scopes="read write",
            disabled=False,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.full_name == "Test User"
        assert user.hashed_password == "a_very_secure_hash"
        assert user.scopes == "read write"
        assert user.disabled is False

    async def test_user_defaults(self, db_session: AsyncSession) -> None:
        """
        Tests that default values are applied correctly when not specified.
        """
        user = DBUser(username="defaultuser", hashed_password="another_hash")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.email is None
        assert user.full_name is None
        assert user.disabled is False
        assert user.scopes == ""

    # --- Constraint Tests ---

    async def test_username_uniqueness(
        self, db_session: AsyncSession, raw_db_session: AsyncSession
    ) -> None:
        """
        Tests that a commit with a duplicate username fails and rolls back.
        """
        user1 = DBUser(username="unique_username", hashed_password="hash1")
        db_session.add(user1)
        await db_session.commit()

        # Check that the first user exists
        assert await raw_db_session.get(DBUser, user1.id) is not None

        # Attempt to add a user with the same username
        user2 = DBUser(username="unique_username", hashed_password="hash2")
        db_session.add(user2)

        # We expect this to raise an error and cause the fixture to roll back.
        with pytest.raises(IntegrityError):
            await db_session.commit()

        # After the error, the fixture's transaction is rolled back.
        # We use our *separate, raw session* to verify that the second user
        # does NOT exist in the database.
        count = await raw_db_session.scalar(select(func.count()).select_from(DBUser))
        assert count == 1

    async def test_username_is_not_nullable(
        self, db_session: AsyncSession, raw_db_session: AsyncSession
    ) -> None:
        """
        Tests that a commit with a null username fails.
        """
        user = DBUser(username=None, hashed_password="some_hash")
        db_session.add(user)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        # Verify no user were created.
        count = await raw_db_session.scalar(select(func.count()).select_from(DBUser))
        assert count == 0

    async def test_email_uniqueness(
        self, db_session: AsyncSession, raw_db_session: AsyncSession
    ) -> None:
        """
        Tests that a commit with a duplicate email fails.
        """
        user1 = DBUser(
            username="user1", email="unique@example.com", hashed_password="hash1"
        )
        db_session.add(user1)
        await db_session.commit()

        user2 = DBUser(
            username="user2", email="unique@example.com", hashed_password="hash2"
        )
        db_session.add(user2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        # Verify only the first user exists.
        count = await raw_db_session.scalar(select(func.count()).select_from(DBUser))
        assert count == 1

    async def test_multiple_null_emails(self, db_session: AsyncSession) -> None:
        """
        Tests that multiple user can have a NULL email, as unique constraints
        typically don't apply to NULL values.
        """
        user1 = DBUser(username="no_email_user1", hashed_password="hash1", email=None)
        user2 = DBUser(username="no_email_user2", hashed_password="hash2", email=None)
        db_session.add_all([user1, user2])

        # This should succeed
        await db_session.commit()
        assert user1.id is not None
        assert user2.id is not None

    async def test_password_is_not_nullable(
        self, db_session: AsyncSession, raw_db_session: AsyncSession
    ) -> None:
        """
        Tests that a commit with a null password fails.
        """
        user = DBUser(username="user_no_pass", hashed_password=None)
        db_session.add(user)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        # Verify no user were created.
        count = await raw_db_session.scalar(select(func.count()).select_from(DBUser))
        assert count == 0

    # --- TimestampMixin Tests ---

    async def test_timestamps_on_create(self, db_session: AsyncSession) -> None:
        now = datetime.now(timezone.utc)  # Ensure timezone-aware datetime
        user = DBUser(username="timestamp_user", hashed_password="a_hash")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.created_at is not None
        assert user.updated_at is not None
        assert now - user.created_at < timedelta(seconds=5)
        assert now - user.updated_at < timedelta(seconds=5)
        assert abs(user.updated_at - user.created_at) < timedelta(seconds=1)

    async def test_updated_at_on_update(self, db_session: AsyncSession) -> None:
        user = DBUser(username="update_user", hashed_password="a_hash")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        original_created_at = user.created_at
        original_updated_at = user.updated_at

        sleep(1)

        user.full_name = "An Updated Name"
        await db_session.commit()
        await db_session.refresh(user)

        assert user.created_at == original_created_at  # Should NOT change
        assert user.updated_at > original_updated_at  # Should change
