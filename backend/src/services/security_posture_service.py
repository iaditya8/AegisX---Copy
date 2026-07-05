import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.security_posture import (
    PostureSeverity,
    RiskStatus,
    RiskCategory,
    SecurityPostureResponse,
)
from src.infrastructure.database.models import Asset, Finding, SecurityPosture as DBPosture, IntelligenceEvent
from src.services.security_posture_registry import SecurityPostureRegistry
from src.services.risk_category_registry import RiskCategoryRegistry
from src.services.risk_severity_registry import RiskSeverityRegistry
from src.services.posture_fingerprint_service import PostureFingerprintService
from src.services.posture_history_service import PostureHistoryService
from src.services.risk_intelligence_service import RiskIntelligenceService
from src.services.risk_prioritization_service import RiskPrioritizationService
from src.services.risk_correlation_service import RiskCorrelationService
from src.services.exposure_service import ExposureService
from src.services.alert_lifecycle_service import AlertLifecycleService
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class PostureRecord:
    def __init__(
        self,
        posture_id: uuid.UUID,
        posture_fingerprint: str,
        title: str,
        description: str,
        posture_score: float,
        risk_score: float,
        severity: PostureSeverity,
        category: RiskCategory,
        status: RiskStatus,
        asset_id: uuid.UUID,
        risk_source: str,
        owner: Optional[str] = None,
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.posture_id = posture_id
        self.posture_fingerprint = posture_fingerprint
        self.title = title
        self.description = description
        self.posture_score = posture_score
        self.risk_score = risk_score
        self.severity = severity
        self.category = category
        self.status = status
        self.asset_id = asset_id
        self.risk_source = risk_source
        self.owner = owner
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class SecurityPostureService:
    # in-memory store: posture_id -> PostureRecord
    _postures: Dict[uuid.UUID, PostureRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_postures(cls) -> None:
        """Clear all posture records."""
        cls._postures.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    async def bootstrap(cls, db: AsyncSession) -> None:
        """Bootstrap the L2 cache from PostgreSQL database."""
        cls.clear_postures()
        async with UnitOfWork() as uow:
            db_postures = await uow.posture_repo.list()
            for db_p in db_postures:
                record = PostureRecord(
                    posture_id=db_p.id,
                    posture_fingerprint=db_p.posture_fingerprint,
                    title=db_p.title,
                    description=db_p.description,
                    posture_score=float(db_p.posture_score),
                    risk_score=float(db_p.risk_score),
                    severity=PostureSeverity(db_p.severity),
                    category=RiskCategory(db_p.category),
                    status=RiskStatus(db_p.status),
                    asset_id=db_p.asset_id,
                    risk_source=db_p.risk_source,
                    owner=db_p.owner,
                    scope_id=db_p.scope_id,
                    created_at=db_p.created_at,
                    updated_at=db_p.updated_at,
                )
                cls._postures[db_p.id] = record
                cls._fingerprint_lookup[db_p.posture_fingerprint] = db_p.id

    @classmethod
    def get_all_postures(cls) -> List[PostureRecord]:
        """Retrieve all security posture records."""
        return list(cls._postures.values())

    @classmethod
    def get_posture(cls, posture_id: uuid.UUID) -> Optional[PostureRecord]:
        """Retrieve a posture record by ID."""
        return cls._postures.get(posture_id)

    @classmethod
    def get_posture_by_fingerprint(cls, fingerprint: str) -> Optional[PostureRecord]:
        """Retrieve a posture record by fingerprint."""
        posture_id = cls._fingerprint_lookup.get(fingerprint)
        if posture_id:
            return cls.get_posture(posture_id)
        return None

    @classmethod
    async def create_or_sync_posture(
        cls,
        title: str,
        description: str,
        category: RiskCategory,
        severity: PostureSeverity,
        asset_id: uuid.UUID,
        risk_source: str,
        owner: Optional[str] = None,
        scope_id: Optional[uuid.UUID] = None,
    ) -> PostureRecord:
        """Create a new security posture or synchronize with an existing one based on fingerprint rules."""
        if not SecurityPostureRegistry.is_valid_category(category):
            raise ValueError(f"Invalid category: {category}")

        resolved_cat = SecurityPostureRegistry.resolve_category(category)
        resolved_severity = RiskSeverityRegistry.resolve_severity(severity)
        fingerprint = PostureFingerprintService.generate_fingerprint(resolved_cat, asset_id, risk_source)

        existing = cls.get_posture_by_fingerprint(fingerprint)
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        if existing:
            if existing.status == RiskStatus.CLOSED:
                # CLOSED is terminal. Subsequent refreshes or updates cannot modify it.
                return existing

            # Identity preservation: preserve ID, history, ownership, score updates, timestamps, and drift
            changed = False
            if existing.description != description:
                existing.description = description
                changed = True
            if owner and existing.owner != owner:
                existing.owner = owner
                changed = True
            if existing.severity != resolved_severity:
                existing.severity = resolved_severity
                changed = True

            # Calculate deterministic risk scores
            r_data = RiskIntelligenceService.calculate_risk(asset_id, resolved_cat, resolved_severity)
            new_risk_score = r_data["risk_score"]
            new_posture_score = r_data["posture_score"]

            if existing.risk_score != new_risk_score:
                existing.risk_score = new_risk_score
                existing.posture_score = new_posture_score
                changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                async with UnitOfWork() as uow:
                    db_p = await uow.posture_repo.get(existing.posture_id)
                    if db_p:
                        db_p.description = existing.description
                        db_p.owner = existing.owner
                        db_p.severity = existing.severity.value
                        db_p.risk_score = existing.risk_score
                        db_p.posture_score = existing.posture_score
                        db_p.updated_at = existing.updated_at

                        await PostureHistoryService.record_event(
                            existing.posture_id,
                            "SCORE_CHANGED",
                            f"Risk score updated: {new_risk_score}, Posture score updated: {new_posture_score}",
                            uow=uow,
                        )
                        await PostureHistoryService.record_event(
                            existing.posture_id,
                            "DRIFT_DETECTED",
                            f"Posture sync updated: severity={existing.severity.value}, status={existing.status.value}",
                            uow=uow,
                        )

                        # Stage outbox event
                        outbox_evt = IntelligenceEvent(
                            tenant_id=tenant_id,
                            event_type="posture.updated",
                            payload={
                                "posture_id": str(existing.posture_id),
                                "status": existing.status.value,
                            }
                        )
                        uow.session.add(outbox_evt)
                        await uow.commit()

            return existing

        # Create new open posture record
        posture_id = uuid.uuid4()
        r_data = RiskIntelligenceService.calculate_risk(asset_id, resolved_cat, resolved_severity)

        record = PostureRecord(
            posture_id=posture_id,
            posture_fingerprint=fingerprint,
            title=title,
            description=description,
            posture_score=r_data["posture_score"],
            risk_score=r_data["risk_score"],
            severity=resolved_severity,
            category=resolved_cat,
            status=RiskStatus.OPEN,
            asset_id=asset_id,
            risk_source=risk_source,
            owner=owner,
            scope_id=scope_id,
        )
        cls._postures[posture_id] = record
        cls._fingerprint_lookup[fingerprint] = posture_id

        async with UnitOfWork() as uow:
            db_p = DBPosture(
                tenant_id=tenant_id,
                id=posture_id,
                posture_fingerprint=fingerprint,
                title=title,
                description=description,
                posture_score=record.posture_score,
                risk_score=record.risk_score,
                severity=resolved_severity.value,
                category=resolved_cat.value,
                status=RiskStatus.OPEN.value,
                asset_id=asset_id,
                risk_source=risk_source,
                owner=owner,
                scope_id=scope_id,
            )
            await uow.posture_repo.save(db_p)

            await PostureHistoryService.record_event(
                posture_id,
                "CREATED",
                f"Created security posture: '{title}' ({resolved_cat.value})",
                uow=uow,
            )

            # Stage outbox event
            outbox_evt = IntelligenceEvent(
                tenant_id=tenant_id,
                event_type="posture.created",
                payload={
                    "posture_id": str(posture_id),
                    "status": RiskStatus.OPEN.value,
                }
            )
            uow.session.add(outbox_evt)
            await uow.commit()

        return record

    @classmethod
    async def sync_postures(cls, db: AsyncSession) -> List[PostureRecord]:
        """Automatically synchronize and discover postures across assets, findings, and exposures."""
        q_assets = select(Asset).where(Asset.deleted_at.is_(None))
        assets = (await db.execute(q_assets)).scalars().all()

        synced = []

        for asset in assets:
            # 1. ATTACK_SURFACE posture
            exposures = ExposureService.get_all_exposures()
            asset_exps = [e for e in exposures if e.asset_id == asset.id]
            if asset_exps:
                highest_sev = RiskSeverityRegistry.get_highest_severity([e.severity for e in asset_exps])
                post = await cls.create_or_sync_posture(
                    title=f"Attack Surface Exposure - {asset.host or asset.ip}",
                    description=f"Exposed services and open ports detected on host.",
                    category=RiskCategory.ATTACK_SURFACE,
                    severity=highest_sev,
                    asset_id=asset.id,
                    risk_source="exposures:attack_surface",
                    scope_id=asset.scope_id,
                )
                synced.append(post)

            # 2. VULNERABILITY posture
            q_findings = select(Finding).where(Finding.asset_id == asset.id)
            findings = (await db.execute(q_findings)).scalars().all()
            if findings:
                # Map finding severity to PostureSeverity
                sevs = []
                for f in findings:
                    sev_str = str(f.severity).upper()
                    if "CRIT" in sev_str:
                        sevs.append(PostureSeverity.CRITICAL)
                    elif "HIGH" in sev_str:
                        sevs.append(PostureSeverity.HIGH)
                    elif "MED" in sev_str:
                        sevs.append(PostureSeverity.MEDIUM)
                    else:
                        sevs.append(PostureSeverity.LOW)

                highest_sev = RiskSeverityRegistry.get_highest_severity(sevs)
                post = await cls.create_or_sync_posture(
                    title=f"Software Vulnerability - {asset.host or asset.ip}",
                    description=f"System findings indicate active software vulnerabilities.",
                    category=RiskCategory.VULNERABILITY,
                    severity=highest_sev,
                    asset_id=asset.id,
                    risk_source="findings:vulnerability",
                    scope_id=asset.scope_id,
                )
                synced.append(post)

            # 3. CONFIGURATION posture
            misconfig_exps = [e for e in asset_exps if e.exposure_type.value in ["MISCONFIGURATION", "WEAK_CONTROL"]]
            if misconfig_exps:
                highest_sev = RiskSeverityRegistry.get_highest_severity([e.severity for e in misconfig_exps])
                post = await cls.create_or_sync_posture(
                    title=f"Security Misconfiguration - {asset.host or asset.ip}",
                    description=f"Active misconfigurations or compliance gaps detected.",
                    category=RiskCategory.CONFIGURATION,
                    severity=highest_sev,
                    asset_id=asset.id,
                    risk_source="exposures:misconfiguration",
                    scope_id=asset.scope_id,
                )
                synced.append(post)

            # 4. OPERATIONAL posture
            alerts = AlertLifecycleService.get_all_alerts()
            asset_alerts = [a for a in alerts if a.asset_id == asset.id]
            if asset_alerts:
                # Map alerts to PostureSeverity
                sevs = []
                for a in asset_alerts:
                    sev_str = str(a.severity).upper()
                    if "CRIT" in sev_str:
                        sevs.append(PostureSeverity.CRITICAL)
                    elif "HIGH" in sev_str:
                        sevs.append(PostureSeverity.HIGH)
                    elif "MED" in sev_str:
                        sevs.append(PostureSeverity.MEDIUM)
                    else:
                        sevs.append(PostureSeverity.LOW)
                highest_sev = RiskSeverityRegistry.get_highest_severity(sevs)
                post = await cls.create_or_sync_posture(
                    title=f"Operational Security Incident - {asset.host or asset.ip}",
                    description=f"Asset has active security alerts or operational incidents.",
                    category=RiskCategory.OPERATIONAL,
                    severity=highest_sev,
                    asset_id=asset.id,
                    risk_source="alerts:operational",
                    scope_id=asset.scope_id,
                )
                synced.append(post)

        # Build correlations
        for p in synced:
            await RiskCorrelationService.correlate_posture(db, p.posture_id, p.asset_id)

        return synced

    @classmethod
    async def accept_risk(cls, posture_id: uuid.UUID) -> PostureRecord:
        """Transition security posture status to ACCEPTED."""
        posture = cls.get_posture(posture_id)
        if not posture:
            raise ValueError(f"Posture record {posture_id} not found")

        if posture.status == RiskStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state")

        if posture.status == RiskStatus.ACCEPTED:
            return posture

        posture.status = RiskStatus.ACCEPTED
        posture.updated_at = datetime.now(timezone.utc)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_p = await uow.posture_repo.get(posture_id)
            if db_p:
                db_p.status = RiskStatus.ACCEPTED.value
                db_p.updated_at = posture.updated_at
                await PostureHistoryService.record_event(
                    posture_id, "ACCEPTED", "Risk accepted by operator", uow=uow
                )
                # Stage outbox event
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type="posture.accepted",
                    payload={
                        "posture_id": str(posture_id),
                        "status": RiskStatus.ACCEPTED.value,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

        return posture

    @classmethod
    async def mitigate_risk(cls, posture_id: uuid.UUID) -> PostureRecord:
        """Transition security posture status to MITIGATED."""
        posture = cls.get_posture(posture_id)
        if not posture:
            raise ValueError(f"Posture record {posture_id} not found")

        if posture.status == RiskStatus.CLOSED:
            raise ValueError("CLOSED is a terminal state")

        if posture.status == RiskStatus.MITIGATED:
            return posture

        posture.status = RiskStatus.MITIGATED
        posture.updated_at = datetime.now(timezone.utc)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_p = await uow.posture_repo.get(posture_id)
            if db_p:
                db_p.status = RiskStatus.MITIGATED.value
                db_p.updated_at = posture.updated_at
                await PostureHistoryService.record_event(
                    posture_id, "MITIGATED", "Risk mitigated successfully", uow=uow
                )
                # Stage outbox event
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type="posture.mitigated",
                    payload={
                        "posture_id": str(posture_id),
                        "status": RiskStatus.MITIGATED.value,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

        return posture

    @classmethod
    async def close_posture(cls, posture_id: uuid.UUID) -> PostureRecord:
        """Transition security posture status to CLOSED (terminal state)."""
        posture = cls.get_posture(posture_id)
        if not posture:
            raise ValueError(f"Posture record {posture_id} not found")

        if posture.status == RiskStatus.CLOSED:
            return posture

        posture.status = RiskStatus.CLOSED
        posture.updated_at = datetime.now(timezone.utc)

        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_p = await uow.posture_repo.get(posture_id)
            if db_p:
                db_p.status = RiskStatus.CLOSED.value
                db_p.updated_at = posture.updated_at
                await PostureHistoryService.record_event(
                    posture_id, "CLOSED", "Posture closed. This is a terminal state.", uow=uow
                )
                # Stage outbox event
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type="posture.closed",
                    payload={
                        "posture_id": str(posture_id),
                        "status": RiskStatus.CLOSED.value,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

        return posture

    @classmethod
    def to_response(cls, record: PostureRecord) -> SecurityPostureResponse:
        """Convert a PostureRecord into a SecurityPostureResponse schema."""
        return SecurityPostureResponse(
            posture_id=record.posture_id,
            posture_fingerprint=record.posture_fingerprint,
            title=record.title,
            description=record.description,
            posture_score=record.posture_score,
            risk_score=record.risk_score,
            severity=record.severity,
            category=record.category,
            status=record.status,
            owner=record.owner,
            asset_id=record.asset_id,
            risk_source=record.risk_source,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
