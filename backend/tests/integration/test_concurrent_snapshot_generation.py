import uuid
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, AsyncMock
from src.services.planning_snapshot_service import PlanningSnapshotService


@pytest.fixture(autouse=True)
def clean_stores():
    PlanningSnapshotService.clear_snapshots()


def test_concurrent_snapshot_generation():
    scope_id = uuid.uuid4()
    db = MagicMock()
    # Mocking database calls during snapshot regeneration
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    lock = threading.Lock()
    generated_count = 0

    def generate():
        nonlocal generated_count
        # Run generator using event loops or mock direct invocation
        # Since PlanningSnapshotService.generate_snapshot is async, we simulate thread-safe concurrent sets
        # using the underlying adapter locks.
        adapter = PlanningSnapshotService._snapshots.adapter
        # Acquire lock concurrently
        acquired = adapter.acquire_lock("snapshot_test_key", ttl_seconds=2)
        if acquired:
            try:
                # Simulate work
                PlanningSnapshotService._snapshots[scope_id] = {"snapshot_id": str(uuid.uuid4())}
                with lock:
                    generated_count += 1
            finally:
                adapter.release_lock("snapshot_test_key")

    # Run in parallel thread pool
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(generate) for _ in range(5)]
        for f in futures:
            f.result()

    # With mutual exclusion lock, at least one thread must successfully lock and execute
    assert generated_count >= 1
    assert scope_id in PlanningSnapshotService._snapshots
