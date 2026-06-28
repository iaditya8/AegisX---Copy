import uuid
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.services.cache_bootstrap_service import CacheBootstrapService
from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService
from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
from src.services.security_decision_service import SecurityDecisionService
from src.services.autonomous_security_planning_service import AutonomousSecurityPlanningService


@pytest.fixture(autouse=True)
def clean_stores():
    UnifiedSecurityIntelligenceFabricService.clear_fabric()
    SecurityIntelligenceGraphService.clear_graph()
    SecurityDecisionService.clear_decisions()
    AutonomousSecurityPlanningService.clear_plans()


@pytest.mark.asyncio
async def test_cache_bootstrap_recovery():
    # Mocking database Session and executing select scopes
    db = MagicMock()
    scope_id = uuid.uuid4()
    
    # Mocking select query results
    mock_result = MagicMock()
    mock_result.all.return_value = [(scope_id,)]
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    # Trigger Cache Bootstrap
    await CacheBootstrapService.bootstrap_cache(db)

    # Verify that graph nodes cache, planning cache, decision cache, and fabric cache are populated/restored
    # Since mock DB returns empty queries for assets/findings during sync, the nodes synced
    # will correspond to the static sync_resilience / sync_fabric_state etc. defined in services.
    fabric_nodes = UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()
    # At least the bootstrapped nodes from sync_fabric_state must be present
    assert len(fabric_nodes) > 0

    # Decision recommendations must be populated
    decisions = SecurityDecisionService.get_all_decisions()
    assert len(decisions) > 0

    # Plans must be populated
    plans = AutonomousSecurityPlanningService.get_all_plans()
    assert len(plans) > 0
