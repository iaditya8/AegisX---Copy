import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.infrastructure.database.session import set_rls_context_after_begin
from src.core.tenant import set_current_tenant_id, TenantMismatchError
from src.api.v1.dependencies.db import get_tenant_db
from src.infrastructure.repositories.base import BaseRepository
from src.infrastructure.database.models import Asset


def test_connection_pool_rls_context_listener():
    """Verify that the after_begin transaction listener sets the RLS context."""
    tenant_id = uuid.uuid4()
    set_current_tenant_id(tenant_id)
    
    session = MagicMock()
    transaction = MagicMock()
    connection = MagicMock()
    
    connection.dialect.name = "postgresql"
    
    # Trigger the event listener
    set_rls_context_after_begin(session, transaction, connection)
    
    # Assert connection.exec_driver_sql was called with the correct set_config statement
    connection.exec_driver_sql.assert_called_once_with(
        f"SELECT set_config('app.current_tenant', '{tenant_id}', true)"
    )
    
    set_current_tenant_id(None)


@pytest.mark.asyncio
async def test_get_tenant_db_rls_setup():
    """Verify get_tenant_db FastAPI dependency executes set_config with the current user's tenant ID."""
    tenant_id = uuid.uuid4()
    user = MagicMock()
    user.tenant_id = tenant_id
    
    db_session = MagicMock()
    db_session.execute = AsyncMock()
    
    # Call the dependency
    await get_tenant_db(db=db_session, current_user=user)
    
    # Assert it called set_config
    db_session.execute.assert_called_once()
    args, kwargs = db_session.execute.call_args
    sql_query = str(args[0])
    assert "set_config" in sql_query
    
    # Check that tenant_id was passed in parameters (positional dictionary)
    assert args[1]["tenant_id"] == str(tenant_id)


@pytest.mark.asyncio
async def test_base_repository_tenant_mismatch_prevention(mock_db):
    """Verify that BaseRepository raises TenantMismatchError if saving an object with a mismatched tenant ID."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    
    # Active tenant context is tenant_a
    set_current_tenant_id(tenant_a)
    
    # Create an asset for tenant_b
    asset = Asset(
        id=uuid.uuid4(),
        host="Pentest Target",
        tenant_id=tenant_b
    )
    
    repo = BaseRepository(model_class=Asset, session=mock_db)
    
    # Save should raise TenantMismatchError
    with pytest.raises(TenantMismatchError):
        await repo.save(asset)
        
    set_current_tenant_id(None)
