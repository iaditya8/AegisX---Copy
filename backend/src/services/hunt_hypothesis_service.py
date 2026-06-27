import uuid
from datetime import datetime, timezone
from typing import Dict, List

from src.domain.entities.hunt import HuntHypothesisResponse


class HuntHypothesisService:
    # in-memory store: hunt_id -> list of hypotheses
    _hypotheses: Dict[uuid.UUID, List[HuntHypothesisResponse]] = {}

    @classmethod
    def clear_hypotheses(cls) -> None:
        """Clear all hypotheses."""
        cls._hypotheses.clear()

    @classmethod
    def get_hypotheses(cls, hunt_id: uuid.UUID) -> List[HuntHypothesisResponse]:
        """Get all hypotheses for a hunt."""
        return cls._hypotheses.get(hunt_id, [])

    @classmethod
    def create_hypothesis(cls, hunt_id: uuid.UUID, description: str) -> HuntHypothesisResponse:
        """Create and add a hypothesis to a hunt."""
        hypothesis_id = uuid.uuid4()
        hyp = HuntHypothesisResponse(
            hypothesis_id=hypothesis_id,
            hunt_id=hunt_id,
            description=description,
            created_at=datetime.now(timezone.utc),
        )
        cls._hypotheses.setdefault(hunt_id, []).append(hyp)
        return hyp
