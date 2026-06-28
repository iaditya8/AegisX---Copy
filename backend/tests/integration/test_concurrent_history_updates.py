import uuid
import pytest
from concurrent.futures import ThreadPoolExecutor
from src.services.planning_history_service import PlanningHistoryService


@pytest.fixture(autouse=True)
def clean_stores():
    PlanningHistoryService.clear_history()


def test_concurrent_history_updates():
    plan_id = uuid.uuid4()
    
    def append_event(index: int):
        PlanningHistoryService.record_event(
            plan_id=plan_id,
            event_type="TEST_EVENT",
            details=f"Concurrent event details {index}"
        )

    # Dispatch 20 concurrent history additions
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(append_event, i) for i in range(20)]
        for f in futures:
            f.result()

    history = PlanningHistoryService.get_history(plan_id)
    # Assert all 20 events were recorded without concurrency loss
    assert len(history) == 20
    # Assert ordering and details are present
    details = [h.details for h in history]
    for i in range(20):
        assert any(f"Concurrent event details {i}" in d for d in details)
