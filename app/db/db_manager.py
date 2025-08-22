"""
Asynchronous database connection and session management.

Implements a singleton DatabaseManager that handles engine creation,
connection pool monitoring via Prometheus, session management,
and graceful startup/shutdown with detailed error logging.
"""

from contextlib import asynccontextmanager
import socket
from typing import Any
from typing import AsyncGenerator
from typing import Optional
from typing import Self

from prometheus_client import Counter
from prometheus_client import Gauge
from prometheus_client import Histogram
from sqlalchemy import event
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.logging import log


DB_CONNECTION_GAUGE = Gauge(
    "db_connection_pool",
    "Current connection pool status",
    ["state"],
    multiprocess_mode="liveall",
)
DB_CONNECTION_ERRORS = Counter(
    "db_connection_errors", "Database connection errors", ["type"]
)
DB_TRANSACTION_TIME = Histogram(
    "db_transaction_duration_seconds", "Database transaction duration", ["operation"]
)


class DatabaseManager:
    """
    Manages asynchronous database connections and sessions as a singleton.

    Handles:
    - Initialization (connection verification, engine creation)
    - Schema compatibility check
    - Prometheus metrics for pool monitoring
    - Session lifecycle management with commit/rollback
    - Graceful shutdown
    """

    _instance: Optional[Self] = None
    engine: Optional[AsyncEngine]
    sessionmaker: Optional[async_sessionmaker[AsyncSession]]
    _debug: bool
    _initialized: bool

    def __new__(cls) -> Self:
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self.engine = None
        self.sessionmaker = None
        self._debug = settings.ENVIRONMENT == "DEVELOPMENT"
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize engine, connection pool, sessionmaker, and verify connectivity."""
        if self._initialized:
            return

        try:
            await self._verify_connection_parameters()
            self.engine = self._create_engine()
            self._setup_pool_monitoring()
            await self._verify_schema_compatibility()
            await self.test_connection()
            self.sessionmaker = async_sessionmaker(
                bind=self.engine,
                expire_on_commit=False,
                autoflush=False,
                class_=AsyncSession,
                twophase=settings.DB_USE_TWOPHASE,
            )
            self._initialized = True
            log.info("Database manager initialized successfully")
        except Exception as e:
            log.critical("Database initialization failed: {}", e)
            DB_CONNECTION_ERRORS.labels("initialization").inc()
            self._initialized = False
            raise

    def _create_engine(self) -> AsyncEngine:
        """Create and configure the async SQLAlchemy engine."""
        return create_async_engine(
            str(settings.database_url),
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=True,
            pool_use_lifo=True,
            connect_args={
                "server_settings": {
                    "application_name": settings.APP_NAME,
                    "statement_timeout": str(settings.DB_STATEMENT_TIMEOUT * 1000),
                    "idle_in_transaction_session_timeout": str(
                        settings.DB_IDLE_TIMEOUT * 1000
                    ),
                    "lock_timeout": str(settings.DB_LOCK_TIMEOUT * 1000),
                },
                "command_timeout": settings.DB_CONNECT_TIMEOUT,
            },
            echo=self._debug,
            echo_pool=self._debug,
        )

    @staticmethod
    async def _verify_connection_parameters() -> None:
        """Verify database host and port by resolving and TCP socket connection."""
        try:
            db_url_str = str(settings.database_url)
            host_port = db_url_str.split("@")[1].split("/")[0]
            host, port_str = (host_port.split(":") + ["5432"])[:2]
            port_int = int(port_str)

            log.info("Resolving database host: {}", host)
            ip = socket.gethostbyname(host)
            log.info("Resolved IP: {}:{}", ip, port_int)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect((ip, port_int))

        except Exception as e:
            log.critical("Connection verification failed: {}", e)
            DB_CONNECTION_ERRORS.labels("connection_verification").inc()
            raise

    async def _verify_schema_compatibility(self) -> None:
        """
        Check for existence of alembic_version table to ensure migrations.

        Logs a warning if the table is missing.
        """
        if self.engine is None:
            log.error("Schema verification called before engine initialization")
            raise RuntimeError("DBManager is not initialized. Call initialize() first.")

        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables "
                        "WHERE table_name = 'alembic_version')"
                    )
                )
                if not result.scalar():
                    log.warning("No alembic_version table found – is this a fresh DB?")
        except SQLAlchemyError as e:
            log.error("Schema verification failed: {}", e)
            DB_CONNECTION_ERRORS.labels("schema_verification").inc()
            raise

    async def test_connection(self) -> bool:
        """
        Test DB connectivity with simple queries and transactions.

        Raises on failure; returns True on success.
        """
        if self.engine is None:
            log.error("Connection test called before engine initialization")
            raise RuntimeError("DBManager is not initialized. Call initialize() first.")

        with DB_TRANSACTION_TIME.labels("health_check").time():
            try:
                async with self.engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                    await conn.commit()

                    async with conn.begin():
                        await conn.execute(text("SELECT 1"))

                    txn = await conn.begin()
                    await conn.execute(text("SELECT 1"))
                    await txn.rollback()

                log.info("Connection test passed")
                return True
            except SQLAlchemyError as e:
                log.critical("Connection test failed: {}", e)
                DB_CONNECTION_ERRORS.labels("connection_test").inc()
                raise

    def _setup_pool_monitoring(self) -> None:
        """
        Register event listeners on the connection pool for Prometheus metrics.

        Monitors connection checkouts, checkins, connects, and closes.
        """
        if self.engine is None:
            log.error("Pool monitoring setup called before engine initialization")
            raise RuntimeError("DBManager is not initialized. Call initialize() first.")

        pool = self.engine.sync_engine.pool

        @event.listens_for(pool, "checkout")
        def on_checkout(*_: Any) -> None:
            DB_CONNECTION_GAUGE.labels("checked_out").inc()
            DB_CONNECTION_GAUGE.labels("idle").dec()
            if self._debug:
                log.debug("Connection checked out")

        @event.listens_for(pool, "checkin")
        def on_checkin(*_: Any) -> None:
            DB_CONNECTION_GAUGE.labels("checked_out").dec()
            DB_CONNECTION_GAUGE.labels("idle").inc()
            if self._debug:
                log.debug("Connection returned")

        @event.listens_for(pool, "connect")
        def on_connect(*_: Any) -> None:
            DB_CONNECTION_GAUGE.labels("total").inc()
            DB_CONNECTION_GAUGE.labels("idle").inc()
            if self._debug:
                log.debug("Connection established")

        @event.listens_for(pool, "close")
        def on_close(*_: Any) -> None:
            DB_CONNECTION_GAUGE.labels("total").dec()
            DB_CONNECTION_GAUGE.labels("idle").dec()
            if self._debug:
                log.debug("Connection closed (pool event)")

    @asynccontextmanager
    async def get_session(
        self,
        operation_name: str = "unspecified_db_operation",
    ) -> AsyncGenerator[AsyncSession, None]:
        """
        Async context manager to provide a database session.

        Commits on success, rolls back on exception, closes session always.
        Tracks operation time and logs errors with Prometheus metrics.
        """
        if not self._initialized:
            await self.initialize()

        if self.sessionmaker is None:
            log.error("get_session called but sessionmaker is None after init")
            raise RuntimeError("DBManager failed to initialize its sessionmaker.")

        session = self.sessionmaker()

        try:
            with DB_TRANSACTION_TIME.labels(operation_name).time():
                yield session
                await session.commit()
                log.debug("Transaction committed for operation: {}", operation_name)
        except Exception as e:
            error_type = type(e).__name__
            log.error("Database operation failed: {}", error_type, exc_info=True)
            DB_CONNECTION_ERRORS.labels(error_type).inc()

            if session.in_transaction():
                try:
                    await session.rollback()
                    log.debug("Transaction rolled back")
                except Exception as rollback_error:
                    log.debug("Rollback failed: {}", type(rollback_error).__name__)
                    DB_CONNECTION_ERRORS.labels("rollback_failure").inc()
            raise
        finally:
            try:
                await session.close()
            except Exception as close_error:
                log.error("Session close failed: {}", type(close_error).__name__)
                DB_CONNECTION_ERRORS.labels("close_failure").inc()

    async def shutdown(self) -> None:
        """Dispose of the engine and reset initialization flags."""
        if self.engine:
            try:
                log.info("Closing database connection pool...")
                await self.engine.dispose()
                self.engine = None
                self.sessionmaker = None
                self._initialized = False
                log.info("Database connection pool closed.")
            except Exception as e:
                log.error("Error disposing database engine: {}", e, exc_info=True)
        else:
            log.info("Database engine not initialized, skipping shutdown.")


# Singleton instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session and handles the
    transaction lifecycle (commit/rollback) for each request.
    """
    async with db_manager.get_session() as session:
        try:
            yield session
            await session.commit()

        except Exception:
            await session.rollback()

            raise
