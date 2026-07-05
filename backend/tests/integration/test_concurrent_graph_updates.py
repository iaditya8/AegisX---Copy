import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService
from src.domain.entities.security_intelligence_graph import NodeType


import asyncio

@pytest.fixture(autouse=True)
def clean_stores():
    SecurityIntelligenceGraphService.clear_graph()


@pytest.mark.asyncio
async def test_concurrent_graph_updates(mock_db):
    entity_id = uuid.uuid4()
    scope_id = uuid.uuid4()

    async def add_node():
        uid = uuid.uuid4()
        await SecurityIntelligenceGraphService.create_or_sync_node(
            node_type=NodeType.ASSET,
            entity_id=uid,
            scope_id=scope_id
        )

    tasks = [add_node() for _ in range(10)]
    await asyncio.gather(*tasks)

    nodes = SecurityIntelligenceGraphService.get_all_nodes()
    assert len(nodes) == 10
