import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.pool import StaticPool

# Ensure all tenant models are imported so their tables register on SQLModel.metadata
from langflow.services.database.models import (  # noqa: F401
    ApiKey,
    Deployment,
    DeploymentProviderAccount,
    File,
    Flow,
    FlowVersion,
    Folder,
    Job,
    MessageTable,
    TransactionTable,
    Variable,
)
from langflow.services.database.models.vertex_builds.model import VertexBuildTable  # noqa: F401
from langflow.services.database.scoping import TENANT_SCOPED_TABLES


@pytest.mark.asyncio
async def test_every_tenant_table_has_org_id():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        missing = await conn.run_sync(
            lambda sync_conn: [
                t
                for t in TENANT_SCOPED_TABLES
                if "organization_id" not in {c["name"] for c in inspect(sync_conn).get_columns(t)}
            ]
        )
    await engine.dispose()
    assert missing == [], f"Missing organization_id on: {missing}"
