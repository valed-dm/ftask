from unittest.mock import MagicMock

import aiohttp
from fastapi import FastAPI
import pytest
from pytest_mock import MockerFixture
import sentry_sdk

from app.core.config import settings
from app.core.logging import log
from app.lifecycle.app_lifecycle import AppLifecycle
from app.lifecycle.db_lifecycle import DatabaseLifecycle


@pytest.fixture
def mock_app() -> MagicMock:
    """Provides a mock FastAPI app object with a mockable `state`."""
    app = MagicMock(spec=FastAPI)
    app.state = MagicMock()
    return app


@pytest.fixture
def lifecycle_manager(mock_app: MagicMock) -> AppLifecycle:
    """Provides an instance of the AppLifecycle class."""
    return AppLifecycle(app=mock_app)


async def test_on_startup(
    lifecycle_manager: AppLifecycle,
    mock_app: MagicMock,
    mocker: MockerFixture,
) -> None:
    """
    Tests that on_startup correctly calls all initialization functions.
    """
    # 1. Mock all external dependencies that on_startup calls
    mock_sentry_init = mocker.patch.object(sentry_sdk, "init")
    mock_db_init = mocker.patch.object(
        DatabaseLifecycle, "initialize", new_callable=mocker.AsyncMock
    )

    # Mock aiohttp.ClientSession to control its creation and behavior
    mock_session_instance = mocker.AsyncMock(spec=aiohttp.ClientSession)
    mock_aiohttp_session = mocker.patch(
        "aiohttp.ClientSession", return_value=mock_session_instance
    )

    mock_log_info = mocker.spy(log, "info")

    # 2. Run the method we are testing
    await lifecycle_manager.on_startup()

    # 3. Assert that all dependencies were called as expected
    mock_sentry_init.assert_called_once_with(
        str(settings.GLITCHTIP_DSN), traces_sample_rate=1.0
    )
    mock_db_init.assert_awaited_once()
    mock_aiohttp_session.assert_called_once()

    # Assert that the created session was stored in the app's state
    assert mock_app.state.aiohttp_session is mock_session_instance

    # Assert that logging happened
    assert mock_log_info.call_count >= 3
    mock_log_info.assert_any_call("Starting {} app...", settings.APP_NAME)
    mock_log_info.assert_any_call("Aiohttp session initialized.")
    mock_log_info.assert_any_call(
        "{} startup complete. Ready to serve requests.", settings.APP_NAME
    )


async def test_on_shutdown_happy_path(
    lifecycle_manager: AppLifecycle,
    mocker: MockerFixture,
) -> None:
    """
    Tests that on_shutdown correctly calls all cleanup functions
    when the aiohttp session is open.
    """
    # 1. Setup the initial state: simulate a successful startup
    mock_session = mocker.AsyncMock(spec=aiohttp.ClientSession)
    mock_session.closed = False  # The session is open
    lifecycle_manager.aiohttp_session = mock_session

    # Mock external dependencies
    mock_db_shutdown = mocker.patch.object(
        DatabaseLifecycle, "shutdown", new_callable=mocker.AsyncMock
    )
    mock_log_info = mocker.spy(log, "info")

    # 2. Run the method
    await lifecycle_manager.on_shutdown()

    # 3. Assert cleanup was performed
    mock_db_shutdown.assert_awaited_once()

    # Assert the aiohttp session's close method was called
    mock_session.close.assert_awaited_once()

    # Assert logging happened
    mock_log_info.assert_any_call("Shutting down {} app...", settings.APP_NAME)
    mock_log_info.assert_any_call("Aiohttp session closed.")


async def test_on_shutdown_no_session(
    lifecycle_manager: AppLifecycle,
    mocker: MockerFixture,
) -> None:
    """
    Tests that on_shutdown does not fail if there is no aiohttp session.
    """
    # 1. Setup: aiohttp_session is None (its default state)
    assert lifecycle_manager.aiohttp_session is None

    mock_db_shutdown = mocker.patch.object(
        DatabaseLifecycle, "shutdown", new_callable=mocker.AsyncMock
    )

    # We want to ensure aiohttp.ClientSession.close is never called
    # To do this, we can mock the entire class and check its instance's method
    mock_session_class = mocker.patch("aiohttp.ClientSession")

    # 2. Run the method
    await lifecycle_manager.on_shutdown()

    # 3. Assert that the app shuts down cleanly without trying
    # to close a non-existent session
    mock_db_shutdown.assert_awaited_once()
    mock_session_class.return_value.close.assert_not_called()


async def test_on_shutdown_error_on_close(
    lifecycle_manager: AppLifecycle,
    mocker: MockerFixture,
) -> None:
    """
    Tests that an error during aiohttp session closing is logged
    and does not crash shutdown.
    """
    # 1. Setup: a session exists but its close() method will raise an error
    mock_session = mocker.AsyncMock(spec=aiohttp.ClientSession)
    mock_session.closed = False
    mock_session.close.side_effect = RuntimeError("Failed to close socket")
    lifecycle_manager.aiohttp_session = mock_session

    mock_db_shutdown = mocker.patch.object(
        DatabaseLifecycle, "shutdown", new_callable=mocker.AsyncMock
    )
    mock_log_error = mocker.spy(log, "error")

    # 2. Run the method
    await lifecycle_manager.on_shutdown()

    # 3. Assert that the error was logged and shutdown continued
    mock_log_error.assert_called_once()
    mock_db_shutdown.assert_awaited_once()  # Verify that shutdown proceeded
