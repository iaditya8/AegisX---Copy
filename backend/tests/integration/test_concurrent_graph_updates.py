import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
from src.domain.entities.security_intelligence_graph import NodeType


@pytest.fixture(autouse=True)
def clean_stores():
    SecurityIntelligenceGraphService.clear_graph()


def test_concurrent_graph_updates():
    entity_id = uuid.uuid4()
    scope_id = uuid.uuid4()

    def add_node(index: int):
        # Concurrently create nodes with different entity_ids
        uid = uuid.uuid4()
        SecurityIntelligenceGraphService.create_or_sync_node(
            node_type=NodeType.ASSET,
            entity_id=uid,
            scope_id=scope_id
        )

    # Spawn 10 concurrent node updates
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(add_node, i) for i in range(10)]
        for f in futures:
            f.result()

    nodes = SecurityIntelligenceGraphService.get_all_nodes()
    # 10 distinct nodes must exist in the cache store without loss
    assert len(nodes) == 10
