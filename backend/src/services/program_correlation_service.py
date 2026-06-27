import uuid
import copy
from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.incident_service import IncidentService
from src.services.case_service import CaseService


class ProgramCorrelationService:
    # in-memory store: program_id -> list of correlations
    # Program Correlation/History Preservation Rule: must never be deleted/modified.
    _correlations: Dict[uuid.UUID, List[dict]] = {}

    @classmethod
    def clear_correlations(cls) -> None:
        """Clear all program correlations."""
        cls._correlations.clear()

    @classmethod
    def get_correlations(cls, program_id: uuid.UUID) -> List[dict]:
        """Retrieve correlations for a security program."""
        return copy.deepcopy(cls._correlations.get(program_id, []))

    @classmethod
    async def correlate_program(
        cls, db: AsyncSession, program_id: uuid.UUID, scope_id: Optional[uuid.UUID] = None
    ) -> List[dict]:
        """Correlate security program against incidents, cases, and active alerts."""
        # 1. Incidents
        incidents = IncidentService.get_all_incidents()
        if scope_id:
            # Check if incident is linked to asset in scope
            from src.infrastructure.database.models import Asset
            # Retrieve assets in scope
            assets = (await db.execute(
                # Simple select
                f"select id from assets where scope_id = '{scope_id}'"
            )).scalars().all()
            asset_set = set(assets)
            incidents = [inc for inc in incidents if any(asid in asset_set for asid in inc.asset_ids)]

        # 2. Cases
        cases = CaseService.get_all_cases()
        if scope_id:
            from src.infrastructure.database.models import Asset
            assets = (await db.execute(
                f"select id from assets where scope_id = '{scope_id}'"
            )).scalars().all()
            asset_set = set(assets)
            cases = [c for c in cases if any(asid in asset_set for asid in c.asset_ids)]

        current = cls._correlations.setdefault(program_id, [])
        existing_signatures = {f"{c['entity_type']}:{c['entity_id']}" for c in current}

        new_correlations = []

        for inc in incidents:
            sig = f"Incident:{str(inc.incident_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Incident", "entity_id": str(inc.incident_id), "details": inc.title})

        for c in cases:
            sig = f"Case:{str(c.case_id)}"
            if sig not in existing_signatures:
                new_correlations.append({"entity_type": "Case", "entity_id": str(c.case_id), "details": c.title})

        # Append new correlations
        current.extend(new_correlations)
        return current
