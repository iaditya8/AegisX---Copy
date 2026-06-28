import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, AsyncMock
from src.services.planning_drift_service import PlanningDriftService


@pytest.fixture(autouse=True)
def clean_stores():
    PlanningDriftService.clear_drifts()


def test_concurrent_drift_processing():
    scope_id = uuid.uuid4()
    db = MagicMock()
    db.commit = AsyncMock()

    def process():
        # Check and process drift concurrently
        adapter = PlanningDriftService._drifts.adapter
        acquired = adapter.acquire_lock("drift_lock", ttl_seconds=2)
        if acquired:
            try:
                # Retrieve and update drift cache safely
                PlanningDriftService._drifts.append({
                    "scope_id": str(scope_id),
                    "drift_id": str(uuid.uuid4())
                })
            finally:
                adapter.release_lock("drift_lock")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process) for _ in range(5)]
        for f in futures:
            f.result()

    # Verify that at least one thread successfully updated drifts
    drifts = PlanningDriftService.get_drifts()
    assert len(drifts) >= 1
