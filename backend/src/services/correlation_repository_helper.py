import uuid
from datetime import datetime, timezone
from src.infrastructure.database.models import CorrelationHistory
from src.core.tenant import require_current_tenant_id


async def append_history_helper(db, cluster_id: uuid.UUID, event_type: str, details: dict) -> None:
    tenant_id = require_current_tenant_id()
    history_entry = CorrelationHistory(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        cluster_id=cluster_id,
        event_type=event_type,
        details_json=details,
        timestamp=datetime.now(timezone.utc)
    )
    db.add(history_entry)
