import asyncio
import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService
from src.services.intelligence_propagation_service import IntelligencePropagationService
from src.domain.entities.security_intelligence_fabric import FabricPriority
from src.core.tenant import get_current_tenant_id, set_current_tenant_id


@pytest.fixture(autouse=True)
def clean_stores():
    UnifiedSecurityIntelligenceFabricService.clear_fabric()


def test_concurrent_fabric_propagation(mock_db):
    scope_id = uuid.uuid4()
    parent_tenant_id = get_current_tenant_id()

    def run_sync(index: int):
        set_current_tenant_id(parent_tenant_id)
        # Concurrently create nodes in the fabric store
        asyncio.run(
            UnifiedSecurityIntelligenceFabricService.create_or_sync_fabric_node(
                source_type="ASSET",
                scope_id=scope_id,
                priority=FabricPriority.CRITICAL,
                rules_hash=f"rules-hash-{index}"
            )
        )

    # Dispatch 10 concurrent fabric syncs
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_sync, i) for i in range(10)]
        for f in futures:
            f.result()

    # Verify that all 10 nodes exist in fabric
    nodes = UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()
    assert len(nodes) == 10

    # Run propagation concurrently
    def run_prop():
        set_current_tenant_id(parent_tenant_id)
        IntelligencePropagationService.process_propagation()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(run_prop) for _ in range(5)]
        for f in futures:
            f.result()

    # Re-verify that propagation executed successfully and set confidence scores
    for n in UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes():
        assert "current_confidence" in n.confidence_weights
