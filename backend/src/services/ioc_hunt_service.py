import uuid
from typing import List

from src.domain.entities.hunt import HuntType
from src.services.ioc_service import IOCService
from src.services.ioc_correlation_service import IOCCorrelationService
from src.services.hunt_service import HuntService
from src.services.hunt_hypothesis_service import HuntHypothesisService
from src.services.hunt_finding_service import HuntFindingService


class IOCHuntService:
    @classmethod
    def sync_ioc_hunts(cls) -> None:
        """Automatically generate threat hunts based on active correlated IOCs."""
        iocs = IOCService.get_all_iocs()
        correlations = IOCCorrelationService.get_all_correlations()

        for ioc in iocs:
            # Find correlations for this specific IOC
            ioc_corrs = [c for c in correlations if c.ioc_id == ioc.ioc_id]
            if not ioc_corrs:
                continue

            # Generate Hunt details
            title = f"IOC Hunting: {ioc.value}"
            desc = (
                f"Automatically generated threat hunt based on active indicator of compromise "
                f"(type: {ioc.ioc_type.value}, value: {ioc.value}) matching correlated entities."
            )
            # Create list of related entities starting with the IOC itself
            related_entities = [{"entity_type": "IOC", "entity_id": str(ioc.ioc_id)}]
            for corr in ioc_corrs:
                related_entities.append({
                    "entity_type": corr.entity_type,
                    "entity_id": str(corr.entity_id)
                })

            # Create or sync the hunt
            hunt = HuntService.create_or_sync_hunt(
                title=title,
                description=desc,
                hunt_type=HuntType.IOC_DRIVEN,
                severity=ioc.severity,
                scope_id=ioc.scope_id,
                related_entities=related_entities
            )

            # Auto-create standard hypothesis
            hypothesis_text = f"Verify whether the correlated indicator {ioc.value} indicates active intrusion or malware execution."
            # Only add if not already present
            existing_hyps = HuntHypothesisService.get_hypotheses(hunt.hunt_id)
            if not any(h.description == hypothesis_text for h in existing_hyps):
                HuntHypothesisService.create_hypothesis(hunt.hunt_id, hypothesis_text)

            # Auto-create findings from active correlations
            for corr in ioc_corrs:
                finding_details = f"Active correlation match found: IOC {ioc.value} matched with {corr.entity_type} ({corr.entity_id})."
                HuntFindingService.create_finding(
                    hunt_id=hunt.hunt_id,
                    entity_type=corr.entity_type,
                    entity_id=corr.entity_id,
                    details=finding_details
                )
