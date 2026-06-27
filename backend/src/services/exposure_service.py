import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.exposure import (
    ExposureSeverity,
    ExposureStatus,
    ExposureType,
    ExposureResponse,
)
from src.infrastructure.database.models import Asset, Finding, AssetPort
from src.services.exposure_type_registry import ExposureTypeRegistry
from src.services.exposure_severity_registry import ExposureSeverityRegistry
from src.services.exposure_fingerprint_service import ExposureFingerprintService
from src.services.exposure_history_service import ExposureHistoryService
from src.services.exposure_prioritization_service import ExposurePrioritizationService
from src.services.exposure_correlation_service import ExposureCorrelationService
from src.services.risk_acceptance_service import RiskAcceptanceService


class ExposureRecord:
    def __init__(
        self,
        exposure_id: uuid.UUID,
        exposure_fingerprint: str,
        title: str,
        description: str,
        severity: ExposureSeverity,
        status: ExposureStatus,
        exposure_type: ExposureType,
        asset_id: uuid.UUID,
        owner: Optional[str] = None,
        risk_score: float = 0.0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        target: str = "",
    ):
        self.exposure_id = exposure_id
        self.exposure_fingerprint = exposure_fingerprint
        self.title = title
        self.description = description
        self.severity = severity
        self.status = status
        self.exposure_type = exposure_type
        self.asset_id = asset_id
        self.owner = owner
        self.risk_score = risk_score
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.target = target


class ExposureService:
    # in-memory store: exposure_id -> ExposureRecord
    _exposures: Dict[uuid.UUID, ExposureRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_exposures(cls) -> None:
        """Clear all exposures."""
        cls._exposures.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_exposures(cls) -> List[ExposureRecord]:
        """Retrieve all exposures."""
        return list(cls._exposures.values())

    @classmethod
    def get_exposure(cls, exposure_id: uuid.UUID) -> Optional[ExposureRecord]:
        """Retrieve an exposure by ID."""
        return cls._exposures.get(exposure_id)

    @classmethod
    def get_exposure_by_fingerprint(cls, fingerprint: str) -> Optional[ExposureRecord]:
        """Retrieve an exposure by fingerprint."""
        exposure_id = cls._fingerprint_lookup.get(fingerprint)
        if exposure_id:
            return cls.get_exposure(exposure_id)
        return None

    @classmethod
    async def create_or_sync_exposure(
        cls,
        db: AsyncSession,
        title: str,
        description: str,
        exposure_type: ExposureType,
        severity: ExposureSeverity,
        asset_id: uuid.UUID,
        target: str,
        owner: Optional[str] = None,
    ) -> ExposureRecord:
        """Create or synchronize an exposure based on fingerprint stability rules."""
        if not ExposureTypeRegistry.is_valid_type(exposure_type):
            raise ValueError(f"Invalid exposure type: {exposure_type}")

        resolved_type = ExposureTypeRegistry.resolve_type(exposure_type)
        resolved_severity = ExposureSeverityRegistry.resolve_severity(severity)
        fingerprint = ExposureFingerprintService.generate_fingerprint(resolved_type, asset_id, target)

        existing = cls.get_exposure_by_fingerprint(fingerprint)
        if existing:
            if existing.status == ExposureStatus.CLOSED:
                # CLOSED is a terminal state. Sync should not modify closed exposures.
                return existing

            # Sync rules: preserve exposure_id, status, history, ownership, timestamps, and drift
            changed = False
            if existing.description != description:
                existing.description = description
                changed = True
            if existing.severity != resolved_severity:
                existing.severity = resolved_severity
                changed = True
            if owner and existing.owner != owner:
                existing.owner = owner
                changed = True

            # Recalculate risk score
            p_data = await ExposurePrioritizationService.calculate_exposure_priority(
                db, asset_id, resolved_severity
            )
            new_risk_score = p_data["risk_score"]
            if existing.risk_score != new_risk_score:
                existing.risk_score = new_risk_score
                changed = True
                ExposureHistoryService.record_event(
                    existing.exposure_id,
                    "PRIORITY_CHANGED",
                    f"Risk score updated: {new_risk_score}",
                )

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                ExposureHistoryService.record_event(
                    existing.exposure_id,
                    "DRIFT_DETECTED",
                    f"Exposure updated: severity={existing.severity.value}, status={existing.status.value}",
                )
            return existing

        # Create new open exposure
        exposure_id = uuid.uuid4()
        p_data = await ExposurePrioritizationService.calculate_exposure_priority(
            db, asset_id, resolved_severity
        )
        risk_score = p_data["risk_score"]

        record = ExposureRecord(
            exposure_id=exposure_id,
            exposure_fingerprint=fingerprint,
            title=title,
            description=description,
            severity=resolved_severity,
            status=ExposureStatus.OPEN,
            exposure_type=resolved_type,
            asset_id=asset_id,
            owner=owner,
            risk_score=risk_score,
            target=target,
        )
        cls._exposures[exposure_id] = record
        cls._fingerprint_lookup[fingerprint] = exposure_id

        ExposureHistoryService.record_event(
            exposure_id,
            "CREATED",
            f"Created open exposure: '{title}' ({resolved_type.value})",
        )
        return record

    @classmethod
    async def sync_exposures(cls, db: AsyncSession) -> List[ExposureRecord]:
        """Automatically scan current database assets, ports, services, misconfigurations, and findings."""
        # 1. Query active assets
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        assets = (await db.execute(q_assets)).scalars().all()

        synced = []

        for asset in assets:
            # 2. Query open ports for EXPOSED_PORT exposure
            q_ports = select(AssetPort).where(
                AssetPort.asset_id == asset.id, AssetPort.state == "open"
            )
            ports = (await db.execute(q_ports)).scalars().all()
            for p in ports:
                port_severity = ExposureSeverity.MEDIUM
                if p.port in [22, 3389, 445]:
                    port_severity = ExposureSeverity.HIGH
                elif p.port in [80, 8080]:
                    port_severity = ExposureSeverity.LOW

                exp = await cls.create_or_sync_exposure(
                    db=db,
                    title=f"Exposed Port {p.port}",
                    description=f"Open TCP port {p.port} detected on host {asset.host or asset.ip}",
                    exposure_type=ExposureType.EXPOSED_PORT,
                    severity=port_severity,
                    asset_id=asset.id,
                    target=f"port:{p.port}",
                )
                synced.append(exp)

            # 3. Query Findings for MISCONFIGURATION exposure
            q_findings = select(Finding).where(Finding.asset_id == asset.id)
            findings = (await db.execute(q_findings)).scalars().all()
            for f in findings:
                # Map finding severity to ExposureSeverity
                sev_str = str(f.severity).upper()
                if "CRIT" in sev_str:
                    f_severity = ExposureSeverity.CRITICAL
                elif "HIGH" in sev_str:
                    f_severity = ExposureSeverity.HIGH
                elif "MED" in sev_str:
                    f_severity = ExposureSeverity.MEDIUM
                else:
                    f_severity = ExposureSeverity.LOW

                exp = await cls.create_or_sync_exposure(
                    db=db,
                    title=f.title,
                    description=f.description or "Asset misconfiguration detected",
                    exposure_type=ExposureType.MISCONFIGURATION,
                    severity=f_severity,
                    asset_id=asset.id,
                    target=f"finding:{str(f.id)}",
                )
                synced.append(exp)

            # 4. Check RiskAcceptances for WEAK_CONTROL exposure
            accepts = RiskAcceptanceService.get_acceptances_by_asset(asset.id)
            if accepts:
                exp = await cls.create_or_sync_exposure(
                    db=db,
                    title="Accepted Compliance Risks",
                    description=f"Asset has {len(accepts)} active compliance acceptances",
                    exposure_type=ExposureType.WEAK_CONTROL,
                    severity=ExposureSeverity.LOW,
                    asset_id=asset.id,
                    target="risk_acceptance:active",
                )
                synced.append(exp)

        # 5. Build correlations for all exposures
        for e in synced:
            await ExposureCorrelationService.correlate_exposure(db, e.exposure_id, e.asset_id)

        return synced

    @classmethod
    def validate_exposure(cls, exposure_id: uuid.UUID) -> ExposureRecord:
        """Transition exposure to VALIDATED (from OPEN)."""
        exposure = cls.get_exposure(exposure_id)
        if not exposure:
            raise ValueError(f"Exposure {exposure_id} not found")

        if exposure.status == ExposureStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state")

        if exposure.status == ExposureStatus.VALIDATED:
            return exposure

        if exposure.status != ExposureStatus.OPEN:
            raise ValueError(f"Cannot transition to VALIDATED from {exposure.status.value}")

        exposure.status = ExposureStatus.VALIDATED
        exposure.updated_at = datetime.now(timezone.utc)
        ExposureHistoryService.record_event(
            exposure_id, "VALIDATED", "Exposure validated by operator"
        )
        return exposure

    @classmethod
    def accept_exposure(cls, exposure_id: uuid.UUID) -> ExposureRecord:
        """Transition exposure to ACCEPTED (from VALIDATED)."""
        exposure = cls.get_exposure(exposure_id)
        if not exposure:
            raise ValueError(f"Exposure {exposure_id} not found")

        if exposure.status == ExposureStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state")

        if exposure.status == ExposureStatus.ACCEPTED:
            return exposure

        if exposure.status != ExposureStatus.VALIDATED:
            raise ValueError(f"Cannot transition to ACCEPTED from {exposure.status.value}")

        exposure.status = ExposureStatus.ACCEPTED
        exposure.updated_at = datetime.now(timezone.utc)
        ExposureHistoryService.record_event(
            exposure_id, "ACCEPTED", "Exposure risk accepted"
        )
        return exposure

    @classmethod
    def mitigate_exposure(cls, exposure_id: uuid.UUID) -> ExposureRecord:
        """Transition exposure to MITIGATED (from VALIDATED)."""
        exposure = cls.get_exposure(exposure_id)
        if not exposure:
            raise ValueError(f"Exposure {exposure_id} not found")

        if exposure.status == ExposureStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state")

        if exposure.status == ExposureStatus.MITIGATED:
            return exposure

        if exposure.status != ExposureStatus.VALIDATED:
            raise ValueError(f"Cannot transition to MITIGATED from {exposure.status.value}")

        exposure.status = ExposureStatus.MITIGATED
        exposure.updated_at = datetime.now(timezone.utc)
        ExposureHistoryService.record_event(
            exposure_id, "MITIGATED", "Exposure mitigated successfully"
        )
        return exposure

    @classmethod
    def close_exposure(cls, exposure_id: uuid.UUID) -> ExposureRecord:
        """Transition exposure to CLOSED (terminal state, from ACCEPTED or MITIGATED)."""
        exposure = cls.get_exposure(exposure_id)
        if not exposure:
            raise ValueError(f"Exposure {exposure_id} not found")

        if exposure.status == ExposureStatus.CLOSED:
            return exposure

        if exposure.status not in [ExposureStatus.ACCEPTED, ExposureStatus.MITIGATED]:
            raise ValueError(f"Cannot transition to CLOSED from {exposure.status.value}")

        exposure.status = ExposureStatus.CLOSED
        exposure.updated_at = datetime.now(timezone.utc)
        ExposureHistoryService.record_event(
            exposure_id, "CLOSED", "Exposure closed. This is a terminal state."
        )
        return exposure

    @classmethod
    def to_response(cls, record: ExposureRecord) -> ExposureResponse:
        """Convert an ExposureRecord into an ExposureResponse schema."""
        return ExposureResponse(
            exposure_id=record.exposure_id,
            exposure_fingerprint=record.exposure_fingerprint,
            title=record.title,
            description=record.description,
            severity=record.severity,
            status=record.status,
            exposure_type=record.exposure_type,
            asset_id=record.asset_id,
            owner=record.owner,
            risk_score=record.risk_score,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
