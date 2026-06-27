import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.threat_intelligence import IOCType
from src.infrastructure.database.models import Asset, Finding
from src.services.alert_lifecycle_service import AlertLifecycleService
from src.services.case_service import CaseService
from src.services.detection_service import DetectionService
from src.services.incident_service import IncidentService
from src.services.ioc_service import IOCService


class IOCCorrelationRecord:
    def __init__(
        self,
        correlation_id: uuid.UUID,
        ioc_id: uuid.UUID,
        ioc_fingerprint: str,
        entity_type: str,
        entity_id: uuid.UUID,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        scope_id: Optional[uuid.UUID] = None,
    ):
        self.correlation_id = correlation_id
        self.ioc_id = ioc_id
        self.ioc_fingerprint = ioc_fingerprint
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.scope_id = scope_id


class IOCCorrelationService:
    _correlations: Dict[uuid.UUID, IOCCorrelationRecord] = {}
    _correlation_lookup: Dict[Tuple[str, uuid.UUID], uuid.UUID] = {}

    @classmethod
    def clear_correlations(cls) -> None:
        """Clear all correlated IOC groups."""
        cls._correlations.clear()
        cls._correlation_lookup.clear()

    @classmethod
    def get_all_correlations(cls, scope_id: Optional[uuid.UUID] = None) -> List[IOCCorrelationRecord]:
        """Retrieve all current IOC correlations."""
        records = list(cls._correlations.values())
        if scope_id:
            records = [r for r in records if r.scope_id == scope_id]
        return records

    @classmethod
    async def correlate_iocs(cls, db: AsyncSession) -> None:
        """Run the IOC correlation engine against all system entities."""
        iocs = IOCService.get_all_iocs()
        if not iocs:
            return

        # 1. Fetch Assets
        res_assets = await db.execute(select(Asset).where(Asset.deleted_at.is_(None)))
        assets = res_assets.scalars().all()

        # 2. Fetch Findings
        res_findings = await db.execute(select(Finding))
        findings = res_findings.scalars().all()

        # 3. Fetch Alerts
        alerts = AlertLifecycleService.get_all_alerts()

        # 4. Fetch Incidents
        incidents = IncidentService.get_all_incidents()

        # 5. Fetch Cases
        cases = CaseService.get_all_cases()

        # 6. Fetch Detections
        detections = DetectionService.get_all_detections()

        new_lookup = {}
        new_correlations = {}

        # Run correlation matching
        for ioc in iocs:
            val_lower = ioc.value.lower()

            # Correlate Assets
            for asset in assets:
                match = False
                if ioc.ioc_type == IOCType.IP_ADDRESS and asset.ip == ioc.value:
                    match = True
                elif ioc.ioc_type == IOCType.DOMAIN and asset.host and asset.host.lower() == val_lower:
                    match = True

                if match:
                    cls._upsert_correlation(
                        ioc_id=ioc.ioc_id,
                        ioc_fingerprint=ioc.ioc_fingerprint,
                        entity_type="Asset",
                        entity_id=asset.id,
                        scope_id=asset.scope_id,
                        new_lookup=new_lookup,
                        new_correlations=new_correlations,
                    )

            # Correlate Findings
            for finding in findings:
                match = False
                if (
                    val_lower in finding.title.lower()
                    or (finding.description and val_lower in finding.description.lower())
                    or (finding.metadata_json and val_lower in str(finding.metadata_json).lower())
                ):
                    match = True

                if match:
                    cls._upsert_correlation(
                        ioc_id=ioc.ioc_id,
                        ioc_fingerprint=ioc.ioc_fingerprint,
                        entity_type="Finding",
                        entity_id=finding.id,
                        scope_id=ioc.scope_id,
                        new_lookup=new_lookup,
                        new_correlations=new_correlations,
                    )

            # Correlate Alerts
            for alert in alerts:
                match = False
                if (
                    val_lower in alert.title.lower()
                    or (alert.description and val_lower in alert.description.lower())
                ):
                    match = True

                if match:
                    cls._upsert_correlation(
                        ioc_id=ioc.ioc_id,
                        ioc_fingerprint=ioc.ioc_fingerprint,
                        entity_type="Alert",
                        entity_id=alert.alert_id,
                        scope_id=ioc.scope_id,
                        new_lookup=new_lookup,
                        new_correlations=new_correlations,
                    )

            # Correlate Incidents
            for incident in incidents:
                match = False
                if (
                    val_lower in incident.title.lower()
                    or (incident.description and val_lower in incident.description.lower())
                ):
                    match = True

                if match:
                    cls._upsert_correlation(
                        ioc_id=ioc.ioc_id,
                        ioc_fingerprint=ioc.ioc_fingerprint,
                        entity_type="Incident",
                        entity_id=incident.incident_id,
                        scope_id=ioc.scope_id,
                        new_lookup=new_lookup,
                        new_correlations=new_correlations,
                    )

            # Correlate Cases
            for case in cases:
                match = False
                if (
                    val_lower in case.title.lower()
                    or (case.description and val_lower in case.description.lower())
                ):
                    match = True

                if match:
                    cls._upsert_correlation(
                        ioc_id=ioc.ioc_id,
                        ioc_fingerprint=ioc.ioc_fingerprint,
                        entity_type="Case",
                        entity_id=case.case_id,
                        scope_id=ioc.scope_id,
                        new_lookup=new_lookup,
                        new_correlations=new_correlations,
                    )

            # Correlate Detections
            for det in detections:
                match = False
                if (
                    val_lower in det.name.lower()
                    or (det.description and val_lower in det.description.lower())
                ):
                    match = True

                if match:
                    cls._upsert_correlation(
                        ioc_id=ioc.ioc_id,
                        ioc_fingerprint=ioc.ioc_fingerprint,
                        entity_type="Detection",
                        entity_id=det.detection_id,
                        scope_id=det.scope_id or ioc.scope_id,
                        new_lookup=new_lookup,
                        new_correlations=new_correlations,
                    )

        # Replace class dictionaries with updated correlations
        cls._correlations = new_correlations
        cls._correlation_lookup = new_lookup

    @classmethod
    def _upsert_correlation(
        cls,
        ioc_id: uuid.UUID,
        ioc_fingerprint: str,
        entity_type: str,
        entity_id: uuid.UUID,
        scope_id: Optional[uuid.UUID],
        new_lookup: Dict[Tuple[str, uuid.UUID], uuid.UUID],
        new_correlations: Dict[uuid.UUID, IOCCorrelationRecord],
    ) -> None:
        lookup_key = (ioc_fingerprint, entity_id)
        old_id = cls._correlation_lookup.get(lookup_key)

        if old_id and old_id in cls._correlations:
            # Identity Preservation Rule: preserve correlation_id and timestamps
            existing = cls._correlations[old_id]
            new_correlations[existing.correlation_id] = existing
            new_lookup[lookup_key] = existing.correlation_id
        else:
            correlation_id = uuid.uuid4()
            record = IOCCorrelationRecord(
                correlation_id=correlation_id,
                ioc_id=ioc_id,
                ioc_fingerprint=ioc_fingerprint,
                entity_type=entity_type,
                entity_id=entity_id,
                scope_id=scope_id,
            )
            new_correlations[correlation_id] = record
            new_lookup[lookup_key] = correlation_id
