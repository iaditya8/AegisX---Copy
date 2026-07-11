import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.infrastructure.database.models import (
    Asset,
    AssetHistory,
    AssetPort,
    AssetService,
    AuditLog,
    Scope,
    User,
)
from src.services.asset_intelligence_service import AssetIntelligenceService

import json

def custom_json_serializer(obj):
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def custom_dumps(obj, **kwargs):
    return json.dumps(obj, default=custom_json_serializer, **kwargs)


# Mock SQLite Database
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    json_serializer=custom_dumps,
)


# Custom functions for SQLite compatibility
@event.listens_for(engine.sync_engine, "connect")
def sqlite_connect(dbapi_connection, connection_record):
    dbapi_connection.create_function(
        "now", 0, lambda: datetime.now(timezone.utc).isoformat()
    )
    dbapi_connection.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))


# SQLite doesn't natively support UUID defaults in SQLAlchemy easily, auto-generate them
from src.infrastructure.database.models import Base


TEST_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")

@event.listens_for(Base, "init", propagate=True)
def init_uuid(target, args, kwargs):
    if not hasattr(target, "id") or target.id is None:
        target.id = uuid.uuid4()
    if hasattr(target, "tenant_id") and getattr(target, "tenant_id", None) is None:
        target.tenant_id = TEST_TENANT_ID


TestSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture
async def seeded_db():
    async with engine.begin() as conn:
        # Patch models to use JSON instead of JSONB/INET for SQLite
        from sqlalchemy.dialects import sqlite
        from sqlalchemy.types import JSON, String

        for table in Base.metadata.sorted_tables:
            for column in table.columns:
                if type(column.type).__name__ == "JSONB":
                    column.type = JSON().with_variant(sqlite.JSON(), "sqlite")
                elif type(column.type).__name__ == "INET":
                    column.type = String().with_variant(sqlite.TEXT(), "sqlite")
                elif type(column.type).__name__ == "ARRAY":
                    column.type = JSON().with_variant(sqlite.JSON(), "sqlite")
                elif type(column.type).__name__ == "UUID":
                    from sqlalchemy.types import Uuid
                    column.type = Uuid(as_uuid=True)

        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    with patch(
        "src.infrastructure.celery.worker.AsyncSessionLocal", TestSessionLocal
    ), patch(
        "src.infrastructure.database.session.AsyncSessionLocal", TestSessionLocal
    ), patch(
        "src.infrastructure.database.unit_of_work.AsyncSessionLocal", TestSessionLocal
    ):
        async with TestSessionLocal() as db:
            from src.infrastructure.database.models import Tenant
            tenant = Tenant(id=TEST_TENANT_ID, name="Test Tenant")
            db.add(tenant)
            await db.flush()

            user_id = uuid.uuid4()
            user = User(
                id=user_id,
                email="test@aegisx.local",
                username="testuser",
                role="admin",
                password_hash="mock",
            )
            db.add(user)

            scope_id = uuid.uuid4()
            scope = Scope(
                id=scope_id,
                owner_id=user_id,
                name="Test Scope",
                type="external",
                definition={"domains": ["example.com"], "ips": ["192.168.1.100"]},
            )
            db.add(scope)

            asset = Asset(
                scope_id=scope_id,
                host="example.com",
                ip="192.168.1.100",
                asset_type="domain",
            )
            db.add(asset)
            await db.commit()
            await db.refresh(asset)

            yield {"user_id": user_id, "scope_id": scope_id, "asset_id": asset.id}

        # Cleanup handled by standard test teardown usually


def mock_naabu_output():
    return json.dumps(
        {"192.168.1.100": "192.168.1.100:80\n192.168.1.100:443\n192.168.1.100:8080"}
    )


def mock_naabu_output_filtered():
    return json.dumps({"192.168.1.100": "192.168.1.100:80\n192.168.1.100:443"})


def mock_nmap_xml():
    xml = """<?xml version="1.0"?>
    <nmaprun>
      <host>
        <address addr="192.168.1.100" addrtype="ipv4"/>
        <ports>
          <port protocol="tcp" portid="80">
            <state state="open" reason="syn-ack"/>
            <service name="http" product="nginx" version="1.18.0" extrainfo="Ubuntu"/>
          </port>
          <port protocol="tcp" portid="443">
            <state state="open" reason="syn-ack"/>
            <service name="https" product="openssl"/>
          </port>
          <port protocol="tcp" portid="8080">
            <state state="open" reason="syn-ack"/>
            <service name="http-proxy" product="php" version="7.4.3"/>
          </port>
        </ports>
      </host>
    </nmaprun>
    """
    return json.dumps({"192.168.1.100": xml})


def mock_nmap_xml_updated():
    xml = """<?xml version="1.0"?>
    <nmaprun>
      <host>
        <address addr="192.168.1.100" addrtype="ipv4"/>
        <ports>
          <port protocol="tcp" portid="80">
            <state state="open" reason="syn-ack"/>
            <service name="http" product="nginx" version="1.24.0" extrainfo="Debian"/>
          </port>
        </ports>
      </host>
    </nmaprun>
    """
    return json.dumps({"192.168.1.100": xml})


@pytest.mark.asyncio
async def test_port_state_transition_tracking(seeded_db):
    """Verifies that when a port is closed/filtered, the transition generates an audit log, history, and event."""
    from src.services.port_service import PortService
    from src.services.service_normalization_service import ServiceNormalizationService

    async with TestSessionLocal() as db:
        # Run 1: 3 ports open
        ports = ServiceNormalizationService.normalize_naabu(mock_naabu_output())
        await PortService.process_discovered_ports(
            db,
            seeded_db["scope_id"],
            ports,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        q_ports = select(AssetPort).where(AssetPort.asset_id == seeded_db["asset_id"])
        res_ports = await db.execute(q_ports)
        db_ports = res_ports.scalars().all()
        assert len(db_ports) == 3

        # Run 2: Port 8080 is now missing from naabu output, which means we should manually set it to filtered.
        # Wait, the port_service code currently only updates state if provided.
        # For this test, we simulate the normalizer passing state="filtered" or we just update the state explicitly in a payload.
        # Let's mock a payload where port 8080 is filtered.
        filtered_payload = [
            {
                "host_or_ip": "192.168.1.100",
                "port": 8080,
                "protocol": "tcp",
                "state": "filtered",
            }
        ]

        await PortService.process_discovered_ports(
            db,
            seeded_db["scope_id"],
            filtered_payload,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        # Verify state updated
        res_ports = await db.execute(q_ports)
        db_ports = res_ports.scalars().all()
        filtered_port = next(p for p in db_ports if p.port == 8080)
        assert filtered_port.state == "filtered"

        # Verify History
        q_history = select(AssetHistory).where(
            AssetHistory.entity_type == "port",
            AssetHistory.change_type == "state_change",
        )
        res_history = await db.execute(q_history)
        history_rec = res_history.scalars().first()
        assert history_rec is not None
        assert history_rec.old_value["state"] == "open"
        assert history_rec.new_value["state"] == "filtered"

        # Verify Audit
        q_audit = select(AuditLog).where(AuditLog.action == "update_port_state")
        res_audit = await db.execute(q_audit)
        audit_rec = res_audit.scalars().first()
        assert audit_rec is not None
        assert audit_rec.metadata_json["new_state"] == "filtered"


@pytest.mark.asyncio
async def test_service_version_change_detection(seeded_db):
    """Verifies that changing a service's version generates the appropriate history and events."""
    from src.services.port_service import PortService
    from src.services.service_normalization_service import ServiceNormalizationService
    from src.services.service_service import ServiceService

    async with TestSessionLocal() as db:
        ports = ServiceNormalizationService.normalize_naabu(mock_naabu_output())
        await PortService.process_discovered_ports(
            db,
            seeded_db["scope_id"],
            ports,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        # Run 1: Nginx 1.18.0
        services = ServiceNormalizationService.normalize_nmap(mock_nmap_xml())
        await ServiceService.process_discovered_services(
            db,
            seeded_db["scope_id"],
            services,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        # Verify service created
        q_services = select(AssetService).join(AssetPort)
        res_services = await db.execute(q_services)
        db_services = res_services.scalars().all()
        assert len(db_services) == 3
        nginx_svc = next(s for s in db_services if s.product == "nginx")
        assert nginx_svc.version == "1.18.0"

        # Run 2: Nginx 1.24.0
        services_updated = ServiceNormalizationService.normalize_nmap(
            mock_nmap_xml_updated()
        )
        await ServiceService.process_discovered_services(
            db,
            seeded_db["scope_id"],
            services_updated,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        res_services = await db.execute(q_services)
        db_services = res_services.scalars().all()
        nginx_svc = next(s for s in db_services if s.product == "nginx")
        assert nginx_svc.version == "1.24.0"

        # Verify History for version_change and banner_change
        q_history = select(AssetHistory).where(
            AssetHistory.change_type == "version_change"
        )
        res_history = await db.execute(q_history)
        history_rec = res_history.scalars().first()
        assert history_rec is not None
        assert history_rec.old_value["version"] == "1.18.0"
        assert history_rec.new_value["version"] == "1.24.0"


@pytest.mark.asyncio
async def test_asset_intelligence_snapshot_generation(seeded_db):
    """Verifies that the generated snapshot contains aggregated ports, services, technologies, and products."""
    from src.services.port_service import PortService
    from src.services.service_normalization_service import ServiceNormalizationService
    from src.services.service_service import ServiceService

    async with TestSessionLocal() as db:
        # Seed
        ports = ServiceNormalizationService.normalize_naabu(mock_naabu_output())
        await PortService.process_discovered_ports(
            db,
            seeded_db["scope_id"],
            ports,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )
        services = ServiceNormalizationService.normalize_nmap(mock_nmap_xml())
        await ServiceService.process_discovered_services(
            db,
            seeded_db["scope_id"],
            services,
            uuid.uuid4(),
            uuid.uuid4(),
            seeded_db["user_id"],
        )

        # Snapshot should have been updated by the services internally
        snapshot = AssetIntelligenceService.get_asset_snapshot(seeded_db["asset_id"])

        assert snapshot["open_port_count"] == 3
        assert snapshot["service_count"] == 3
        assert "nginx" in snapshot["technology_stack"]
        assert "openssl" in snapshot["technology_stack"]
        assert "php" in snapshot["technology_stack"]
        assert "nginx" in snapshot["products"]
        assert "openssl" in snapshot["products"]
        assert "php" in snapshot["products"]
