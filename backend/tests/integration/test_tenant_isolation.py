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


@pytest.mark.asyncio
async def test_workflow_event_service_transaction_neutrality(mock_db):
    """Verify that WorkflowEventService.emit_event does not commit the transaction."""
    from src.services.workflow_event_service import WorkflowEventService
    from src.infrastructure.database.models import Workflow
    
    tenant_id = uuid.uuid4()
    set_current_tenant_id(tenant_id)
    
    # Mock Workflow retrieval
    wf = Workflow(id=uuid.uuid4(), tenant_id=tenant_id)
    mock_db._entities[Workflow] = [wf]
    
    event = await WorkflowEventService.emit_event(
        db=mock_db,
        event_type="test.event",
        payload={"data": "test"}
    )
    
    assert event is not None
    # Verify db.add was called
    assert any(isinstance(e, type(event)) for e in mock_db._entities.get(type(event), []))
    # Verify db.commit was NOT called
    mock_db.commit.assert_not_called()
    set_current_tenant_id(None)


@pytest.mark.asyncio
async def test_finding_service_transaction_neutrality(mock_db):
    """Verify that FindingService does not commit the transaction."""
    from src.services.finding_service import FindingService
    from src.infrastructure.database.models import Asset, Workflow
    
    tenant_id = uuid.uuid4()
    set_current_tenant_id(tenant_id)
    
    asset = Asset(id=uuid.uuid4(), scope_id=uuid.uuid4(), host="example.com", ip="example.com", tenant_id=tenant_id)
    wf = Workflow(id=uuid.uuid4(), tenant_id=tenant_id)
    mock_db._entities[Asset] = [asset]
    mock_db._entities[Workflow] = [wf]
    
    findings_list = [{
        "finding": {
            "template_id": "cve-1234",
            "title": "Vulnerability",
            "description": "Desc",
            "severity": "high",
            "template_name": "Nuclei-CVE",
            "source_plugin": "nuclei"
        },
        "evidence": {
            "evidence_type": "http",
            "raw_request": "GET",
            "raw_response": "200",
            "matched_at": "http://example.com/path",
            "matcher_name": "matcher",
            "matcher_value": "val",
            "metadata_json": {"host": "example.com"}
        }
    }]
    
    processed = await FindingService.process_discovered_findings(
        db=mock_db,
        scope_id=asset.scope_id,
        findings_list=findings_list,
        scan_run_id=uuid.uuid4(),
        workflow_id=wf.id,
        actor_id=uuid.uuid4()
    )
    
    assert len(processed) > 0
    # Verify db.commit was NOT called
    mock_db.commit.assert_not_called()
    set_current_tenant_id(None)


@pytest.mark.asyncio
async def test_ioc_added_event_emission(mock_db):
    """Verify that threat.ioc_added event is emitted on IOC creation."""
    from src.services.ioc_service import IOCService
    from src.domain.entities.threat_intelligence import IOCType, IOCSeverity, ThreatFeedType
    from src.infrastructure.database.models import Workflow, WorkflowEvent
    
    tenant_id = uuid.uuid4()
    set_current_tenant_id(tenant_id)
    IOCService.clear_iocs()
    
    wf = Workflow(id=uuid.uuid4(), tenant_id=tenant_id)
    mock_db._entities[Workflow] = [wf]
    
    record = IOCService.create_or_sync_ioc(
        value="1.1.1.1",
        ioc_type=IOCType.IP_ADDRESS,
        severity=IOCSeverity.HIGH,
        reputation=90,
        feed_type=ThreatFeedType.INTERNAL,
        db=mock_db
    )
    
    assert record is not None
    # Allow async task in loop to run
    import asyncio
    await asyncio.sleep(0.1)
    
    # Assert WorkflowEvent was staged
    events = mock_db._entities.get(WorkflowEvent, [])
    assert len(events) > 0
    assert any(e.event_type == "threat.ioc_added" for e in events)
    set_current_tenant_id(None)


@pytest.mark.asyncio
async def test_validation_failed_event_emission(mock_db):
    """Verify that validation.failed event is emitted on validation failure."""
    from src.services.control_validation_service import ControlValidationService
    from src.domain.entities.control_validation import ControlType, ControlSeverity, ValidationStatus
    from src.infrastructure.database.models import Workflow, WorkflowEvent
    
    tenant_id = uuid.uuid4()
    set_current_tenant_id(tenant_id)
    ControlValidationService.clear_controls()
    
    wf = Workflow(id=uuid.uuid4(), tenant_id=tenant_id)
    mock_db._entities[Workflow] = [wf]
    
    control = await ControlValidationService.create_or_sync_control(
        name="Firewall",
        description="Prevent unauthorized access",
        control_type=ControlType.PREVENTIVE,
        severity=ControlSeverity.HIGH,
        attack_techniques=["T1001"]
    )
    
    # Run validation with status FAILED
    await ControlValidationService.execute_validation(
        db=mock_db,
        control_id=control.control_id,
        attack_technique="T1001",
        status=ValidationStatus.FAILED,
        evidence="Firewall block failed"
    )
    
    # Assert WorkflowEvent was staged
    events = mock_db._entities.get(WorkflowEvent, [])
    assert len(events) > 0
    assert any(e.event_type == "validation.failed" for e in events)
    set_current_tenant_id(None)


@pytest.mark.asyncio
async def test_transaction_rollback_guarantees(mock_db):
    """Verify that raising an exception rolls back staged outbox events."""
    from src.infrastructure.database.unit_of_work import UnitOfWork
    from src.services.workflow_event_service import WorkflowEventService
    from src.infrastructure.database.models import Workflow
    
    tenant_id = uuid.uuid4()
    set_current_tenant_id(tenant_id)
    
    wf = Workflow(id=uuid.uuid4(), tenant_id=tenant_id)
    mock_db._entities[Workflow] = [wf]
    
    with pytest.raises(ValueError):
        async with UnitOfWork() as uow:
            # Stage outbox event
            await WorkflowEventService.emit_event(
                db=uow.session,
                event_type="rollback.test",
                payload={}
            )
            # Raise exception to trigger rollback
            raise ValueError("Simulated failure")
            
    # Commit must not be called, rollback must be called
    mock_db.rollback.assert_called_once()
    mock_db.commit.assert_not_called()
    set_current_tenant_id(None)
