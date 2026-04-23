from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from sqlalchemy import delete
from sqlalchemy import exc as sqlalchemy_exc
from sqlmodel import col, select

from langflow.services.cache.base import ExternalAsyncBaseCacheService
from langflow.services.cache.factory import CacheServiceFactory
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.database.utils import initialize_database
from langflow.services.schema import ServiceType

from .deps import get_db_service, get_service, get_settings_service, session_scope

if TYPE_CHECKING:
    from lfx.services.settings.manager import SettingsService
    from sqlmodel.ext.asyncio.session import AsyncSession


async def setup_superuser(settings_service: SettingsService, session: AsyncSession) -> None:
    from langflow.services.auth.utils import create_super_user

    username = settings_service.auth_settings.SUPERUSER
    password_secret = settings_service.auth_settings.SUPERUSER_PASSWORD
    password = password_secret.get_secret_value() if password_secret else ""

    if not username:
        msg = (
            "LANGFLOW_SUPERUSER must be set. Username/password authentication is required; "
            "provide LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD via environment or .env."
        )
        raise ValueError(msg)
    if not password:
        msg = (
            "LANGFLOW_SUPERUSER_PASSWORD must be set. Username/password authentication is required; "
            "provide LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD via environment or .env."
        )
        raise ValueError(msg)

    await logger.adebug(f"Creating or updating superuser '{username}'.")
    await create_super_user(username=username, password=password, db=session)
    settings_service.auth_settings.reset_credentials()


async def teardown_services() -> None:
    """Teardown all the services."""
    from lfx.services.manager import get_service_manager

    service_manager = get_service_manager()
    await service_manager.teardown()


def initialize_settings_service() -> None:
    """Initialize the settings manager."""
    from lfx.services.settings import factory as settings_factory

    get_service(ServiceType.SETTINGS_SERVICE, settings_factory.SettingsServiceFactory())


def initialize_session_service() -> None:
    """Initialize the session manager."""
    from langflow.services.cache import factory as cache_factory
    from langflow.services.session import factory as session_service_factory

    initialize_settings_service()

    get_service(
        ServiceType.CACHE_SERVICE,
        cache_factory.CacheServiceFactory(),
    )

    get_service(
        ServiceType.SESSION_SERVICE,
        session_service_factory.SessionServiceFactory(),
    )


async def clean_transactions(settings_service: SettingsService, session: AsyncSession) -> None:
    """Clean up old transactions from the database.

    This function deletes transactions that exceed the maximum number to keep (configured in settings).
    It orders transactions by timestamp descending and removes the oldest ones beyond the limit.

    Args:
        settings_service: The settings service containing configuration like max_transactions_to_keep
        session: The database session to use for the deletion
    """
    try:
        # Delete transactions using bulk delete
        delete_stmt = delete(TransactionTable).where(
            col(TransactionTable.id).in_(
                select(TransactionTable.id)
                .order_by(col(TransactionTable.timestamp).desc())
                .offset(settings_service.settings.max_transactions_to_keep)
            )
        )

        await session.exec(delete_stmt)
        logger.debug("Successfully cleaned up old transactions")
    except (sqlalchemy_exc.SQLAlchemyError, asyncio.TimeoutError) as exc:
        logger.error(f"Error cleaning up transactions: {exc!s}")
        # Don't re-raise since this is a cleanup task


async def clean_vertex_builds(settings_service: SettingsService, session: AsyncSession) -> None:
    """Clean up old vertex builds from the database.

    This function deletes vertex builds that exceed the maximum number to keep (configured in settings).
    It orders vertex builds by timestamp descending and removes the oldest ones beyond the limit.

    Args:
        settings_service: The settings service containing configuration like max_vertex_builds_to_keep
        session: The database session to use for the deletion
    """
    try:
        # Delete vertex builds using bulk delete
        delete_stmt = delete(VertexBuildTable).where(
            col(VertexBuildTable.id).in_(
                select(VertexBuildTable.id)
                .order_by(col(VertexBuildTable.timestamp).desc())
                .offset(settings_service.settings.max_vertex_builds_to_keep)
            )
        )

        await session.exec(delete_stmt)
        logger.debug("Successfully cleaned up old vertex builds")
    except (sqlalchemy_exc.SQLAlchemyError, asyncio.TimeoutError) as exc:
        logger.error(f"Error cleaning up vertex builds: {exc!s}")
        # Don't re-raise since this is a cleanup task


def register_all_service_factories() -> None:
    """Register all available service factories with the service manager."""
    # Import all service factories
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType

    service_manager = get_service_manager()
    from lfx.services.mcp_composer import factory as mcp_composer_factory
    from lfx.services.settings import factory as settings_factory

    from langflow.services.auth import factory as auth_factory
    from langflow.services.auth.service import AuthService
    from langflow.services.cache import factory as cache_factory
    from langflow.services.chat import factory as chat_factory
    from langflow.services.database import factory as database_factory
    from langflow.services.job_queue import factory as job_queue_factory
    from langflow.services.session import factory as session_factory
    from langflow.services.shared_component_cache import factory as shared_component_cache_factory
    from langflow.services.state import factory as state_factory
    from langflow.services.storage import factory as storage_factory
    from langflow.services.store import factory as store_factory
    from langflow.services.task import factory as task_factory
    from langflow.services.telemetry import factory as telemetry_factory
    from langflow.services.tracing import factory as tracing_factory
    from langflow.services.transaction import factory as transaction_factory
    from langflow.services.variable import factory as variable_factory
    from langflow.services.notifier import factory as notifier_factory
    from langflow.services.pricing import factory as pricing_factory

    # Register all factories
    service_manager.register_factory(settings_factory.SettingsServiceFactory())
    service_manager.register_factory(cache_factory.CacheServiceFactory())
    service_manager.register_factory(chat_factory.ChatServiceFactory())
    service_manager.register_factory(database_factory.DatabaseServiceFactory())
    service_manager.register_factory(session_factory.SessionServiceFactory())
    service_manager.register_factory(storage_factory.StorageServiceFactory())
    service_manager.register_factory(variable_factory.VariableServiceFactory())
    service_manager.register_factory(telemetry_factory.TelemetryServiceFactory())
    service_manager.register_factory(tracing_factory.TracingServiceFactory())
    service_manager.register_factory(transaction_factory.TransactionServiceFactory())
    service_manager.register_factory(state_factory.StateServiceFactory())
    service_manager.register_factory(job_queue_factory.JobQueueServiceFactory())
    service_manager.register_factory(task_factory.TaskServiceFactory())
    service_manager.register_factory(store_factory.StoreServiceFactory())
    service_manager.register_factory(shared_component_cache_factory.SharedComponentCacheServiceFactory())
    # Override LFX's no-op auth service with Langflow's full JWT implementation
    service_manager.register_service_class(ServiceType.AUTH_SERVICE, AuthService, override=True)
    service_manager.register_factory(auth_factory.AuthServiceFactory())
    service_manager.register_factory(mcp_composer_factory.MCPComposerServiceFactory())
    from langflow.services.audit import factory as audit_factory
    service_manager.register_factory(audit_factory.AuditServiceFactory())
    service_manager.register_factory(notifier_factory.UsageAlertDispatcherFactory())
    service_manager.register_factory(pricing_factory.PricingServiceFactory())
    service_manager.set_factory_registered()


async def initialize_services(*, fix_migration: bool = False) -> None:
    """Initialize all the services needed."""
    from langflow.helpers.windows_postgres_helper import configure_windows_postgres_event_loop

    configure_windows_postgres_event_loop(source="initialize_services")

    # Register all service factories first
    register_all_service_factories()

    cache_service = get_service(ServiceType.CACHE_SERVICE, default=CacheServiceFactory())
    # Test external cache connection
    if isinstance(cache_service, ExternalAsyncBaseCacheService) and not (await cache_service.is_connected()):
        msg = "Cache service failed to connect to external database"
        raise ConnectionError(msg)

    # Setup the superuser
    await initialize_database(fix_migration=fix_migration)
    db_service = get_db_service()
    await db_service.initialize_alembic_log_file()
    async with session_scope() as session:
        settings_service = get_service(ServiceType.SETTINGS_SERVICE)
        await setup_superuser(settings_service, session)

    async with session_scope() as session:
        await clean_transactions(settings_service, session)
        await clean_vertex_builds(settings_service, session)
