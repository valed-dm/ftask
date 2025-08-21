from datetime import datetime
from time import sleep

import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.task.models import Task
from app.user.models import User as DBUser


@pytest.fixture
async def task_owner(db_session: AsyncSession) -> DBUser:
    """
    Provides a pre-existing user to act as the owner for task.
    This is a prerequisite for almost all task-related tests.
    """
    user = DBUser(username="task_owner_user", hashed_password="secure_password")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


class TestTaskModel:
    """
    Test suite for the Task database model.
    """

    async def test_successful_task_creation(
        self,
        db_session: AsyncSession,
        task_owner: DBUser,
    ) -> None:
        """
        Tests that a task can be created successfully with all fields populated.
        """
        task = Task(
            title="A Detailed Task",
            description="This is a description of the task.",
            owner_id=task_owner.id,
        )
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        assert task.id is not None
        assert task.title == "A Detailed Task"
        assert task.description == "This is a description of the task."
        assert task.owner_id == task_owner.id
        # Verify the relationship loaded correctly
        assert task.owner.username == "task_owner_user"

    async def test_task_defaults(
        self,
        db_session: AsyncSession,
        task_owner: DBUser,
    ) -> None:
        """
        Tests that default values are applied correctly when not specified.
        """
        task = Task(title="A Simple Task", owner_id=task_owner.id)
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        assert task.description is None
        # From the TaskStatus Enum
        assert task.status.value == "created"

    async def test_timestamps_on_create_and_update(
        self,
        db_session: AsyncSession,
        task_owner: DBUser,
    ) -> None:
        """
        Tests that created_at/updated_at are set correctly via TimestampMixin.
        """
        task = Task(title="Timestamp Task", owner_id=task_owner.id)
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # Timestamps should be set on creation
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)
        initial_created_at = task.created_at

        # Ensure a measurable time difference
        sleep(0.1)

        # Now, update the task
        task.title = "Updated Timestamp Task"
        db_session.add(task)
        await db_session.commit()
        await db_session.refresh(task)

        # created_at should NOT change, updated_at SHOULD change
        assert task.created_at == initial_created_at
        assert task.updated_at > initial_created_at

    # --- Constraint Tests ---

    async def test_title_is_not_nullable(
        self,
        db_session: AsyncSession,
        task_owner: DBUser,
        raw_db_session: AsyncSession,
    ) -> None:
        """
        Tests that a commit with a null title fails.
        """
        task = Task(title=None, owner_id=task_owner.id)
        db_session.add(task)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        # Verify no task were created
        count = await raw_db_session.scalar(select(func.count()).select_from(Task))
        assert count == 0

    async def test_owner_id_is_not_nullable(
        self, db_session: AsyncSession, raw_db_session: AsyncSession
    ) -> None:
        """
        Tests that a commit with a null owner_id fails.
        """
        task = Task(title="Orphan Task", owner_id=None)
        db_session.add(task)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        # Verify no task were created
        count = await raw_db_session.scalar(select(func.count()).select_from(Task))
        assert count == 0

    async def test_foreign_key_constraint_on_owner(
        self, db_session: AsyncSession, raw_db_session: AsyncSession
    ) -> None:
        """
        Tests that creating a task with a non-existent owner_id fails.
        """
        non_existent_user_id = 99999
        task = Task(title="Ghost Task", owner_id=non_existent_user_id)
        db_session.add(task)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        # Verify no task were created
        count = await raw_db_session.scalar(select(func.count()).select_from(Task))
        assert count == 0

    # --- Relationship and Cascade Tests ---

    async def test_ondelete_cascade(
        self,
        db_session: AsyncSession,
        task_owner: DBUser,
        raw_db_session: AsyncSession,
    ) -> None:
        """
        Tests that deleting a User correctly cascades and deletes their Tasks.
        """
        # Create a task owned by the user
        task = Task(title="Task to be deleted", owner_id=task_owner.id)
        db_session.add(task)
        await db_session.commit()

        # Verify with an independent session that the task exists
        task_count = await raw_db_session.scalar(select(func.count()).select_from(Task))
        assert task_count == 1

        # Now, delete the owner User
        await db_session.delete(task_owner)
        await db_session.commit()

        # Verify with the independent session that the task has been cascaded-deleted
        task_count_after_delete = await raw_db_session.scalar(
            select(func.count()).select_from(Task)
        )
        assert task_count_after_delete == 0
