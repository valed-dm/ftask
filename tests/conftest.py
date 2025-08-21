from typing import Any
from typing import AsyncGenerator
from typing import Callable
from typing import Generator
from typing import cast

import docker
from fastapi import FastAPI
from httpx import ASGITransport
from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer

from app.auth.auth import get_password_hash
from app.core.config import settings
from app.db import Base
from app.db.db_manager import DatabaseManager
from app.db.db_manager import get_db
from app.main import app as main_app
from app.task.models import Task
from app.user.models import User


# --- App Fixtures ---


@pytest.fixture
def app() -> FastAPI:
    return main_app


@pytest.fixture
async def async_client(app_with_db: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Function-scoped async client bound to the overridden DB."""
    transport = ASGITransport(app=app_with_db)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# --- Database Fixtures (Function-Scoped for Maximum Stability) ---


@pytest.fixture(scope="session")
def docker_client() -> Generator[docker.client.DockerClient, None, None]:
    """Session-scoped Docker client for performance."""
    client = docker.from_env()
    yield client
    client.close()


@pytest.fixture(scope="function")
def postgres_container(
    docker_client: docker.client.DockerClient,
) -> Generator[PostgresContainer, None, None]:
    """Fresh Postgres container per test for full isolation."""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture(scope="function")
async def engine(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncEngine, None]:
    """Creates a new async engine & schema for each test."""
    raw_url = postgres_container.get_connection_url()
    db_url = raw_url.replace("+psycopg2", "").replace(
        "postgresql", "postgresql+asyncpg", 1
    )

    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """
    Returns a SQLAlchemy session factory for the test database.
    This is the main fixture that other fixtures should depend on.
    """
    return async_sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture(scope="function")
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Primary SQLAlchemy session for test data setup.
    Used by fixtures like `admin_user`.
    """
    async with session_factory() as session:
        yield session


@pytest.fixture(scope="function")
async def raw_db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """
    Independent session to verify committed state after an API call.
    Your tests can use this to read from the DB without interfering.
    """
    async with session_factory() as session:
        yield session


# --- Dependency Overrides ---


@pytest.fixture
def override_get_db(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], AsyncGenerator[AsyncSession, None]]:
    """
    Overrides the `get_db` dependency to provide a clean, new session
    for each API request, mimicking the real application's behavior.
    """

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        # A new session is created from the factory for the request.
        async with session_factory() as session:
            yield session
            # This session is now independent of the `db_session` used for setup.

    return _override_get_db


@pytest.fixture
def app_with_db(
    app: FastAPI,
    override_get_db: Callable[[], AsyncGenerator[AsyncSession, None]],
) -> Generator[FastAPI, None, None]:
    """FastAPI app with DB dependency overridden."""
    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_db_manager_singleton():
    """
    This autouse fixture automatically runs for every test. It ensures that
    the DatabaseManager singleton is reset to a clean state before each test,
    preventing state leakage.
    """
    # Use setattr to modify the "private" instance variable
    DatabaseManager._instance = None
    yield
    # Teardown (optional, but good practice)
    DatabaseManager._instance = None


# --- Test-specific Fixtures ---


@pytest.fixture
async def test_user(db_session: AsyncSession) -> tuple[str, str]:
    """Creates a default test user."""
    user = User(
        username=settings.TEST_USERNAME,
        email=settings.TEST_EMAIL,
        hashed_password=get_password_hash(settings.TEST_PASSWORD),
        full_name=settings.TEST_FULL_NAME,
        scopes=settings.TEST_SCOPE,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.username, settings.TEST_PASSWORD


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> tuple[str, str]:
    """Creates an admin user."""
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Admin User",
        scopes=settings.TEST_SCOPE,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user.username, "AdminPass123!"


@pytest.fixture
async def existing_user(db_session: AsyncSession) -> User:
    """
    Creates a user in the database for testing existing user scenarios.
    """
    user = User(
        username="existinguser",
        email="existing@example.com",
        hashed_password="hashedpassword",
        full_name="Existing User",
        scopes=settings.TEST_SCOPE,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def regular_users(db_session: AsyncSession) -> list[User]:
    """Creates a list of regular (non-admin) user in the database."""
    users_data = [
        User(
            id=101,
            username="user1",
            email="user1@example.com",
            full_name="User One",
            hashed_password="pw",
            scopes="user",
        ),
        User(
            id=102,
            username="user2",
            email="user2@example.com",
            full_name="User Two",
            hashed_password="pw",
            scopes="user",
        ),
        User(
            id=103,
            username="user3",
            email="user3@example.com",
            full_name="User Three",
            hashed_password="pw",
            scopes="user",
            disabled=True,
        ),
    ]
    db_session.add_all(users_data)
    await db_session.commit()
    for u in users_data:
        await db_session.refresh(u)
    return users_data


@pytest.fixture
async def auth_token(async_client: AsyncClient, test_user: tuple[str, str]) -> str:
    """Logs in as the test user and returns a Bearer token."""
    username, password = test_user
    resp = await async_client.post(
        "/users/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    json_data = cast(dict[str, Any], resp.json())
    return cast(str, json_data["access_token"])


@pytest.fixture
async def admin_token(async_client: AsyncClient, admin_user: tuple[str, str]) -> str:
    """Logs in as admin and returns a Bearer token."""
    username, password = admin_user
    resp = await async_client.post(
        "/users/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return cast(str, resp.json()["access_token"])


@pytest.fixture
async def user_a(db_session: AsyncSession) -> User:
    """Creates a standard user 'User A' with a properly hashed password."""
    user = User(
        username="user_a",
        email="user_a@example.com",
        hashed_password=get_password_hash("password_a"),
        full_name="User A",
        scopes="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def user_a_token(async_client: AsyncClient, user_a: User) -> str:
    """Logs in as User A and returns a Bearer token."""
    resp = await async_client.post(
        "/users/token", data={"username": "user_a", "password": "password_a"}
    )
    resp.raise_for_status()
    json_data = cast(dict[str, Any], resp.json())
    access_token = cast(str, json_data["access_token"])

    return access_token


# --- User B Fixtures ---


@pytest.fixture
async def user_b(db_session: AsyncSession) -> User:
    """Creates a second standard user 'User B' with a properly hashed password."""
    user = User(
        username="user_b",
        email="user_b@example.com",
        hashed_password=get_password_hash("password_b"),
        full_name="User B",
        scopes="user",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def user_b_token(async_client: AsyncClient, user_b: User) -> str:
    """Logs in as User B and returns a Bearer token."""
    resp = await async_client.post(
        "/users/token", data={"username": "user_b", "password": "password_b"}
    )
    resp.raise_for_status()
    json_data = cast(dict[str, Any], resp.json())
    access_token = cast(str, json_data["access_token"])

    return access_token


# --- Task Fixture ---


@pytest.fixture
async def user_a_task(db_session: AsyncSession, user_a: User) -> Task:
    """Creates a task owned by User A directly in the database."""
    task = Task(title="User A's Task", owner_id=user_a.id)
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task
