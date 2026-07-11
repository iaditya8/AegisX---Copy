import uuid
import pytest
from datetime import datetime, timezone

from src.infrastructure.database.models import (
    Asset,
    Finding,
    ThreatIntelIOC,
    PurpleTeamValidation,
    CorrelationRule,
    CorrelationCluster,
    CorrelationClusterSignal,
    CorrelationRuleMatch,
    CorrelationHistory,
    Incident,
)
from src.services.correlation_rule_engine import CorrelationRuleEngine
from src.services.correlation_aggregator_service import CorrelationAggregatorService
from src.services.correlation_incident_bridge import CorrelationIncidentBridge
from src.services.correlation_event_consumer import CorrelationEventConsumer
from src.services.correlation_service import CorrelationService
from src.core.tenant import set_current_tenant_id


TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(autouse=True)
def setup_tenant():
    set_current_tenant_id(TENANT_A)
    yield
    set_current_tenant_id(None)
@pytest.fixture(autouse=True)
def configure_mock_db(mock_db):
    """Ensure Asset, Finding, and Correlation queries are executed against _entities in UCE tests."""
    orig_execute = mock_db.execute._orig_execute

    async def custom_execute(query, *args, **kwargs):
        if query is not None and hasattr(query, "column_descriptions"):
            try:
                expr = query.column_descriptions[0]["expr"]
                expr_name = getattr(expr, "__name__", "")
                if expr_name in (
                    "Asset", "Finding", "CorrelationRule", "CorrelationCluster",
                    "CorrelationClusterSignal", "CorrelationHistory", "CorrelationRuleMatch",
                    "Incident", "ThreatIntelIOC", "PurpleTeamValidation"
                ):
                    return await orig_execute(query, *args, **kwargs)
            except Exception:
                pass
        return mock_db.execute.return_value

    mock_db.execute.side_effect = custom_execute
@pytest.mark.asyncio
async def test_rule_evaluation_logic():
    """Test logical condition expressions in CorrelationRuleEngine."""
    rule = CorrelationRule(
        condition_expression={
            "operator": "AND",
            "conditions": [
                {"signal": "finding.cve_match", "operator": "IN", "value": "threat.ioc_cves"},
                {"signal": "asset.exposure_level", "operator": "GT", "value": 0.7},
                {"signal": "purple_team.validation_status", "operator": "EQUALS", "value": "FAILED"},
            ]
        }
    )

    # Context that matches
    context_matching = {
        "finding.cve_match": "CVE-2023-1234",
        "asset.exposure_level": 0.8,
        "purple_team.validation_status": "FAILED",
        "threat.ioc_cves": ["CVE-2023-1234", "CVE-2023-5678"]
    }
    assert CorrelationRuleEngine.evaluate_expression(rule.condition_expression, context_matching) is True

    # Context that fails GT exposure level
    context_failing_exposure = {
        "finding.cve_match": "CVE-2023-1234",
        "asset.exposure_level": 0.6,
        "purple_team.validation_status": "FAILED",
        "threat.ioc_cves": ["CVE-2023-1234"]
    }
    assert CorrelationRuleEngine.evaluate_expression(rule.condition_expression, context_failing_exposure) is False

    # Context that fails validation status
    context_failing_validation = {
        "finding.cve_match": "CVE-2023-1234",
        "asset.exposure_level": 0.8,
        "purple_team.validation_status": "PASSED",
        "threat.ioc_cves": ["CVE-2023-1234"]
    }
    assert CorrelationRuleEngine.evaluate_expression(rule.condition_expression, context_failing_validation) is False


@pytest.mark.asyncio
async def test_correlation_aggregator_score_and_upsert(mock_db):
    """Test score aggregation and idempotent cluster upserting."""
    asset_id = uuid.uuid4()
    asset = Asset(
        id=asset_id,
        tenant_id=TENANT_A,
        metadata_json={"criticality": "8.0", "exposure_level": "0.9"}
    )
    mock_db.add(asset)

    finding1 = Finding(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        asset_id=asset_id,
        severity="high",
        status="open",
        metadata_json={"cvss": 7.5, "cves": ["CVE-2023-1234"]}
    )
    finding2 = Finding(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        asset_id=asset_id,
        severity="critical",
        status="open",
        metadata_json={"cvss": 9.8, "cves": ["CVE-2023-5678"]}
    )
    mock_db.add(finding1)
    mock_db.add(finding2)

    signals = [("finding", finding1.id), ("finding", finding2.id)]

    cluster = await CorrelationAggregatorService.aggregate_and_upsert(
        db=mock_db,
        asset_id=asset_id,
        signals=signals
    )

    assert cluster is not None
    assert cluster.asset_id == asset_id
    assert cluster.unified_score > 0.0
    assert cluster.status == "open"
    assert cluster.fingerprint != ""

    # Verify score components breakdown
    breakdown = cluster.score_breakdown_json
    assert breakdown is not None
    assert breakdown["asset_contribution"] == 0.3 * 8.0
    assert breakdown["finding_contribution"] == 0.4 * 9.8


@pytest.mark.asyncio
async def test_event_consumer_correlation_pipeline(mock_db):
    """Test the full event consumption, rule matching, and cluster staging pipeline."""
    asset_id = uuid.uuid4()
    asset = Asset(
        id=asset_id,
        tenant_id=TENANT_A,
        metadata_json={"criticality": "9.0", "exposure_level": "0.85"}
    )
    mock_db.add(asset)

    finding = Finding(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        asset_id=asset_id,
        severity="high",
        status="open",
        metadata_json={"cvss": 8.0, "cves": ["CVE-2023-1234"]}
    )
    mock_db.add(finding)

    ioc = ThreatIntelIOC(
        ioc_id=uuid.uuid4(),
        ioc_fingerprint="test_ioc_fingerprint",
        tenant_id=TENANT_A,
        value="1.2.3.4",
        ioc_type="ip",
        severity="high",
        status="active",
        reputation=10,
        feed_type="test",
        tags=["CVE-2023-1234"],
        is_deleted=False
    )
    mock_db.add(ioc)

    rule = CorrelationRule(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        name="IOC Vulnerability Correlation Rule",
        description="Correlates vulnerability CVE matching threat intel IOC CVE",
        status="active",
        condition_expression={
            "operator": "AND",
            "conditions": [
                {"signal": "finding.cve_match", "operator": "IN", "value": "threat.ioc_cves"},
                {"signal": "asset.exposure_level", "operator": "GT", "value": 0.5}
            ]
        },
        priority_level="critical",
        rule_version=1
    )
    mock_db.add(rule)

    payload = {
        "asset_id": str(asset_id),
        "finding_id": str(finding.id),
        "ioc_id": str(ioc.ioc_id)
    }

    await CorrelationEventConsumer.consume_event(mock_db, "finding.discovered", payload)

    # Verify Cluster created
    clusters = mock_db._entities.get(CorrelationCluster, [])
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.asset_id == asset_id
    assert cluster.unified_score >= 5.0  # High score due to high criticality & CVSS

    # Verify Rule Match created
    matches = mock_db._entities.get(CorrelationRuleMatch, [])
    assert len(matches) == 1
    assert matches[0].rule_id == rule.id
    assert matches[0].cluster_id == cluster.id

    # Verify history trace
    histories = mock_db._entities.get(CorrelationHistory, [])
    assert len(histories) > 0


@pytest.mark.asyncio
async def test_escalation_bridge(mock_db):
    """Test incident bridge escalates cluster into incident and stages records."""
    asset_id = uuid.uuid4()
    cluster = CorrelationCluster(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        asset_id=asset_id,
        unified_score=8.5,
        status="open",
        fingerprint="test_fingerprint_escalation"
    )
    mock_db.add(cluster)

    finding = Finding(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        asset_id=asset_id,
        severity="high",
        status="open",
        metadata_json={"cvss": 8.0}
    )
    mock_db.add(finding)

    sig = CorrelationClusterSignal(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        cluster_id=cluster.id,
        signal_type="finding",
        signal_id=finding.id
    )
    mock_db.add(sig)

    # Escalate
    incident = await CorrelationIncidentBridge.escalate_cluster(
        db=mock_db,
        cluster_id=cluster.id,
        title="Escalated Incident Title",
        description="Escalated Incident Description"
    )

    assert incident is not None
    assert incident.title == "Escalated Incident Title"
    assert incident.description == "Escalated Incident Description"
    assert incident.status == "open"
    assert finding.id in incident.finding_ids

    # Cluster should now be associated and updated to triaged
    assert cluster.associated_incident_id == incident.id
    assert cluster.status == "triaged"


@pytest.mark.asyncio
async def test_transaction_neutrality(mock_db):
    """Verify that consumer, aggregator, and bridge never call commit() directly."""
    # Patch commit to raise exception
    mock_db.commit.side_effect = Exception("commit() should not be called by services!")

    asset_id = uuid.uuid4()
    cluster = CorrelationCluster(
        id=uuid.uuid4(),
        tenant_id=TENANT_A,
        asset_id=asset_id,
        unified_score=8.5,
        status="open",
        fingerprint="test_fingerprint_neutrality"
    )
    mock_db.add(cluster)

    # Escalation should execute flush but not commit
    incident = await CorrelationIncidentBridge.escalate_cluster(
        db=mock_db,
        cluster_id=cluster.id,
        title="Neutrality Title",
        description="Neutrality Description"
    )
    assert incident is not None
    assert mock_db.flush.called
    assert not mock_db.commit.called
