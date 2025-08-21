from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.db_manager import DatabaseManager


@pytest.fixture
def mock_settings(mocker):
    """Mocks the global settings object for predictable configuration."""
    mock_settings = MagicMock()
    mock_settings.database_url = "postgresql+asyncpg://user:pass@host:5432/db"
    mock_settings.ENVIRONMENT = "TESTING"
    mock_settings.DB_POOL_SIZE = 5
    mocker.patch("app.db.db_manager.settings", mock_settings)
    return mock_settings


@pytest.fixture
def mock_prometheus(mocker: MockerFixture) -> dict[str, MagicMock]:
    """Mocks all Prometheus metrics used in the db_manager."""
    mocks = {
        "gauge": mocker.patch("app.db.db_manager.DB_CONNECTION_GAUGE"),
        "counter": mocker.patch("app.db.db_manager.DB_CONNECTION_ERRORS"),
        "histogram": mocker.patch("app.db.db_manager.DB_TRANSACTION_TIME"),
    }
    # Mock the .time() method to return a dummy context manager
    mocks["histogram"].labels.return_value.time.return_value.__enter__.return_value = (
        None
    )
    mocks["histogram"].labels.return_value.time.return_value.__exit__.return_value = (
        None
    )
    return mocks


@pytest.fixture
def db_manager_instance(
    mock_settings: MagicMock,
    mock_prometheus: dict[str, MagicMock],
) -> DatabaseManager:
    """Provides a fresh instance of DatabaseManager for each test."""
    return DatabaseManager()


class TestDatabaseManagerSingleton:
    def test_singleton_instance(self):
        """Tests that DatabaseManager is a singleton."""
        instance1 = DatabaseManager()
        instance2 = DatabaseManager()
        assert instance1 is instance2
        assert instance1._initialized is False


class TestDatabaseManagerLifecycle:

    async def test_initialize_success(
        self,
        db_manager_instance: DatabaseManager,
        mocker: MockerFixture,
    ) -> None:
        """Tests the full, successful initialization path."""

        # Patch all helper methods called by initialize
        mock_verify_params = mocker.patch.object(
            DatabaseManager, "_verify_connection_parameters", new_callable=AsyncMock
        )
        mock_verify_schema = mocker.patch.object(
            DatabaseManager, "_verify_schema_compatibility", new_callable=AsyncMock
        )
        mock_test_conn = mocker.patch.object(
            DatabaseManager, "test_connection", new_callable=AsyncMock
        )

        # Mock the engine creation and event listeners
        mock_engine = MagicMock()
        mock_engine.sync_engine.pool = MagicMock()
        mock_create_engine = mocker.patch(
            "app.db.db_manager.create_async_engine", return_value=mock_engine
        )
        mock_event_listen = mocker.patch("app.db.db_manager.event.listens_for")

        # Call the method under test
        await db_manager_instance.initialize()

        # Assertions
        assert db_manager_instance._initialized is True
        assert db_manager_instance.engine is mock_engine
        assert db_manager_instance.sessionmaker is not None

        mock_create_engine.assert_called_once()
        mock_verify_params.assert_awaited_once()
        mock_verify_schema.assert_awaited_once()
        mock_test_conn.assert_awaited_once()

        # There should be 4 event listener registrations
        assert mock_event_listen.call_count == 4

    async def test_initialize_failure_on_connection(
        self,
        db_manager_instance: DatabaseManager,
        mock_prometheus: dict[str, MagicMock],
        mocker: MockerFixture,
    ) -> None:
        """Tests that initialization fails gracefully if a sub-step fails."""
        mocker.patch.object(
            DatabaseManager,
            "_verify_connection_parameters",
            side_effect=ConnectionRefusedError("Test Failure"),
        )
        mock_counter = mock_prometheus["counter"]

        with pytest.raises(ConnectionRefusedError):
            await db_manager_instance.initialize()

        assert db_manager_instance._initialized is False
        mock_counter.labels.assert_called_with("initialization")
        mock_counter.labels.return_value.inc.assert_called_once()

    async def test_shutdown(self, db_manager_instance: DatabaseManager) -> None:
        """Tests a successful shutdown."""
        # Simulate an initialized state
        mock_engine = AsyncMock()
        db_manager_instance.engine = mock_engine
        db_manager_instance._initialized = True

        await db_manager_instance.shutdown()

        mock_engine.dispose.assert_awaited_once()
        assert db_manager_instance.engine is None
        assert db_manager_instance._initialized is False  # type: ignore[unreachable]


class TestDatabaseManagerSession:
    @pytest.fixture
    async def initialized_manager(
        self,
        db_manager_instance: DatabaseManager,
        mocker: MockerFixture,  # Added mocker for consistency
    ) -> DatabaseManager:
        """
        Provides a manager in a mocked 'initialized' state.
        Correctly mocks the sessionmaker factory to return an AsyncMock session.
        """
        mock_async_session = AsyncMock(spec=AsyncSession)
        mock_session_factory = MagicMock(return_value=mock_async_session)

        # We assign the mock directly. The tests will use `cast` to handle it.
        db_manager_instance.sessionmaker = mock_session_factory
        db_manager_instance._initialized = True
        return db_manager_instance

    async def test_get_session_success(
        self,
        initialized_manager: DatabaseManager,
        mock_prometheus: dict[str, MagicMock],
    ) -> None:
        """Tests the happy path: commit on success, then close."""
        assert initialized_manager.sessionmaker is not None

        # Cast the sessionmaker to a MagicMock to access mock-specific attributes.
        mock_factory = cast(MagicMock, initialized_manager.sessionmaker)
        mock_session = mock_factory.return_value

        async with initialized_manager.get_session() as session:
            assert session is mock_session

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_awaited()
        mock_session.close.assert_awaited_once()

    async def test_get_session_failure_rolls_back(
        self,
        initialized_manager: DatabaseManager,
        mock_prometheus: dict[str, MagicMock],
    ) -> None:
        """Tests the failure path: rollback on exception, then close."""
        assert initialized_manager.sessionmaker is not None

        mock_factory = cast(MagicMock, initialized_manager.sessionmaker)
        mock_session = cast(AsyncMock, mock_factory.return_value)
        mock_session.in_transaction.return_value = True

        with pytest.raises(ValueError, match="Test DB Error"):
            async with initialized_manager.get_session():
                raise ValueError("Test DB Error")

        mock_session.commit.assert_not_awaited()
        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()

    async def test_get_session_rollback_failure(
        self,
        initialized_manager: DatabaseManager,
        mock_prometheus: dict[str, MagicMock],
    ) -> None:
        """Tests the edge case where the rollback itself fails."""
        assert initialized_manager.sessionmaker is not None

        mock_factory = cast(MagicMock, initialized_manager.sessionmaker)
        mock_session = cast(AsyncMock, mock_factory.return_value)
        mock_session.in_transaction.return_value = True
        mock_session.rollback.side_effect = ConnectionError("Rollback failed")

        with pytest.raises(ValueError, match="Original Error"):
            async with initialized_manager.get_session():
                raise ValueError("Original Error")

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()
