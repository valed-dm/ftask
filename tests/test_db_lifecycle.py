from unittest.mock import call

import pytest
from pytest_mock import MockerFixture

from app.core.logging import log
from app.db.db_manager import db_manager
from app.lifecycle.db_lifecycle import DatabaseLifecycle


class TestDatabaseLifecycle:
    """
    Test suite for the DatabaseLifecycle static class.
    (Option 1: Patch db_manager.initialize/shutdown)
    """

    async def test_initialize_success(self, mocker: MockerFixture) -> None:
        """Ensure initialize delegates to db_manager and logs correctly."""
        mock_db_initialize = mocker.patch.object(
            db_manager, "initialize", new_callable=mocker.AsyncMock
        )
        spy_log_info = mocker.spy(log, "info")

        await DatabaseLifecycle.initialize()

        mock_db_initialize.assert_awaited_once()

        expected_log_calls = [
            call("Initializing database connection..."),
            call("Database manager initialized successfully."),
        ]
        spy_log_info.assert_has_calls(expected_log_calls, any_order=False)

    async def test_initialize_failure(self, mocker: MockerFixture) -> None:
        """Ensure initialization errors are logged and re-raised."""
        test_exception = ConnectionRefusedError("Test connection error")
        mock_db_init = mocker.patch.object(
            db_manager, "initialize", side_effect=test_exception
        )
        mock_log_critical = mocker.spy(log, "critical")

        with pytest.raises(RuntimeError, match="Database initialization failed"):
            await DatabaseLifecycle.initialize()

        mock_db_init.assert_called_once()
        mock_log_critical.assert_called_once()
        logged_exception_object = mock_log_critical.call_args.args[1]
        assert "Test connection error" in str(logged_exception_object)

    async def test_shutdown_success(self, mocker: MockerFixture) -> None:
        """Ensure shutdown delegates to db_manager and logs correctly."""
        mock_db_shutdown = mocker.patch.object(
            db_manager, "shutdown", new_callable=mocker.AsyncMock
        )
        mock_log_info = mocker.spy(log, "info")

        await DatabaseLifecycle.shutdown()

        mock_db_shutdown.assert_awaited_once()
        assert mock_log_info.call_count == 2
        mock_log_info.assert_any_call("Shutting down database manager...")
        mock_log_info.assert_any_call("Database manager shutdown complete.")

    async def test_shutdown_failure(self, mocker: MockerFixture) -> None:
        """Ensure shutdown errors are logged but not re-raised."""
        test_exception = RuntimeError("Test shutdown error")
        mock_db_shutdown = mocker.patch.object(
            db_manager, "shutdown", side_effect=test_exception
        )
        mock_log_error = mocker.spy(log, "error")

        await DatabaseLifecycle.shutdown()

        mock_db_shutdown.assert_called_once()
        mock_log_error.assert_called_once()
        logged_exception_object = mock_log_error.call_args.args[1]
        assert "Test shutdown error" in str(logged_exception_object)
