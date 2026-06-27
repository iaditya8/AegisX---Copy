import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.cyber_risk_quantification import (
    RiskQuantificationStatus,
    RiskScenarioType,
    CyberRiskResponse,
)
from src.services.risk_quantification_fingerprint_service import RiskQuantificationFingerprintService
from src.services.quantified_risk_history_service import QuantifiedRiskHistoryService
from src.services.risk_frequency_registry import RiskFrequencyRegistry
from src.services.risk_impact_registry import RiskImpactRegistry
from src.services.loss_expectancy_service import LossExpectancyService
from src.services.residual_risk_service import ResidualRiskService
from src.services.risk_trend_service import RiskTrendService


class QuantifiedRiskRecord:
    def __init__(
        self,
        risk_id: uuid.UUID,
        risk_fingerprint: str,
        scenario_type: RiskScenarioType,
        title: str,
        description: str,
        exposure_value: float,
        single_loss_expectancy: float,
        annualized_loss_expectancy: float,
        inherent_risk_score: float,
        residual_risk_score: float,
        mitigation_effectiveness: float,
        status: RiskQuantificationStatus,
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.risk_id = risk_id
        self.risk_fingerprint = risk_fingerprint
        self.scenario_type = scenario_type
        self.title = title
        self.description = description
        self.exposure_value = exposure_value
        self.single_loss_expectancy = single_loss_expectancy
        self.annualized_loss_expectancy = annualized_loss_expectancy
        self.inherent_risk_score = inherent_risk_score
        self.residual_risk_score = residual_risk_score
        self.mitigation_effectiveness = mitigation_effectiveness
        self.status = status
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class CyberRiskQuantificationService:
    # in-memory store: risk_id -> QuantifiedRiskRecord
    _risks: Dict[uuid.UUID, QuantifiedRiskRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    ALLOWED_TRANSITIONS = {
        RiskQuantificationStatus.ACTIVE: {
            RiskQuantificationStatus.ACCEPTED,
            RiskQuantificationStatus.MITIGATED,
            RiskQuantificationStatus.CLOSED,
        },
        RiskQuantificationStatus.ACCEPTED: {RiskQuantificationStatus.CLOSED},
        RiskQuantificationStatus.MITIGATED: {RiskQuantificationStatus.CLOSED},
        RiskQuantificationStatus.CLOSED: set(),  # Terminal
    }

    @classmethod
    def clear_risks(cls) -> None:
        """Clear all risk records and lookup cache."""
        cls._risks.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_risks(cls) -> List[QuantifiedRiskRecord]:
        """Retrieve all risk records."""
        return list(cls._risks.values())

    @classmethod
    def get_risk(cls, risk_id: uuid.UUID) -> Optional[QuantifiedRiskRecord]:
        """Retrieve a risk record by ID."""
        return cls._risks.get(risk_id)

    @classmethod
    def get_risk_by_fingerprint(cls, fingerprint: str) -> Optional[QuantifiedRiskRecord]:
        """Retrieve a risk record by fingerprint."""
        risk_id = cls._fingerprint_lookup.get(fingerprint)
        if risk_id:
            return cls.get_risk(risk_id)
        return None

    @classmethod
    async def create_or_sync_risk(
        cls,
        title: str,
        description: str,
        scenario_type: RiskScenarioType,
        frequency_label: str,
        impact_label: str,
        exposure_value: float,
        scope_id: Optional[uuid.UUID] = None,
    ) -> QuantifiedRiskRecord:
        """Create or synchronize a quantified risk record based on identity rules."""
        fingerprint = RiskQuantificationFingerprintService.generate_fingerprint(
            scenario_type.value, title, scope_id
        )
        existing = cls.get_risk_by_fingerprint(fingerprint)

        aro = RiskFrequencyRegistry.get_aro(frequency_label)
        factor = RiskImpactRegistry.get_factor(impact_label)

        sle = LossExpectancyService.calculate_sle(exposure_value, factor)
        ale = LossExpectancyService.calculate_ale(sle, aro)

        inherent = ResidualRiskService.calculate_inherent_risk_score(exposure_value, factor, aro)
        mitigation_eff = 75.0  # standard effectiveness
        residual = ResidualRiskService.calculate_residual_risk_score(inherent, mitigation_eff)

        if existing:
            if existing.status == RiskQuantificationStatus.CLOSED:
                # Terminal State Rule
                return existing

            changed = False
            if existing.exposure_value != exposure_value:
                existing.exposure_value = exposure_value
                changed = True
            if existing.single_loss_expectancy != sle:
                existing.single_loss_expectancy = sle
                changed = True
            if existing.annualized_loss_expectancy != ale:
                existing.annualized_loss_expectancy = ale
                changed = True
                QuantifiedRiskHistoryService.record_event(
                    existing.risk_id, "ALE_CHANGED", f"Annualized Loss Expectancy updated to {ale}"
                )
            if existing.inherent_risk_score != inherent or existing.residual_risk_score != residual:
                existing.inherent_risk_score = inherent
                existing.residual_risk_score = residual
                changed = True
                QuantifiedRiskHistoryService.record_event(
                    existing.risk_id, "RESIDUAL_RISK_CHANGED", f"Residual risk score updated to {residual}"
                )

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
            return existing

        # Create new record
        risk_id = uuid.uuid4()

        record = QuantifiedRiskRecord(
            risk_id=risk_id,
            risk_fingerprint=fingerprint,
            scenario_type=scenario_type,
            title=title,
            description=description,
            exposure_value=exposure_value,
            single_loss_expectancy=sle,
            annualized_loss_expectancy=ale,
            inherent_risk_score=inherent,
            residual_risk_score=residual,
            mitigation_effectiveness=mitigation_eff,
            status=RiskQuantificationStatus.ACTIVE,
            scope_id=scope_id,
        )

        cls._risks[risk_id] = record
        cls._fingerprint_lookup[fingerprint] = risk_id

        # Cache baseline trend
        RiskTrendService.calculate_trends(risk_id, exposure_value)

        QuantifiedRiskHistoryService.record_event(
            risk_id, "CREATED", f"Quantified risk record created: '{title}'"
        )
        return record

    @classmethod
    async def sync_risks(cls, db: AsyncSession) -> List[QuantifiedRiskRecord]:
        """Continuous sync loop discovering cyber risks posture."""
        synced = []

        # 1. Cloud S3 Bucket Leaks
        rec1 = await cls.create_or_sync_risk(
            title="Cloud S3 Bucket Leaks",
            description="Exposes sensitive corporate backups.",
            scenario_type=RiskScenarioType.CLOUD_COMPROMISE,
            frequency_label="OCCASIONAL",
            impact_label="HIGH",
            exposure_value=120000.0,
        )
        synced.append(rec1)

        # 2. Ransomware Hostage Crypt
        rec2 = await cls.create_or_sync_risk(
            title="Ransomware Hostage Crypt",
            description="Cryptolocker infection on local servers.",
            scenario_type=RiskScenarioType.RANSOMWARE,
            frequency_label="RARE",
            impact_label="CRITICAL",
            exposure_value=250000.0,
        )
        synced.append(rec2)

        return synced

    @classmethod
    def transition_status(
        cls, risk_id: uuid.UUID, new_status: RiskQuantificationStatus
    ) -> QuantifiedRiskRecord:
        """Safely transition report status enforcing forward-only rules and terminal states."""
        record = cls.get_risk(risk_id)
        if not record:
            raise ValueError(f"Risk record {risk_id} not found")

        if record.status == RiskQuantificationStatus.CLOSED:
            # Terminal State Rule
            return record

        allowed = cls.ALLOWED_TRANSITIONS.get(record.status, set())
        if new_status not in allowed:
            raise ValueError(f"Invalid transition from {record.status.value} to {new_status.value}")

        old_status = record.status
        record.status = new_status
        record.updated_at = datetime.now(timezone.utc)

        event_map = {
            RiskQuantificationStatus.ACCEPTED: "ACCEPTED",
            RiskQuantificationStatus.MITIGATED: "MITIGATED",
            RiskQuantificationStatus.CLOSED: "CLOSED",
        }
        event_type = event_map.get(new_status, "STATUS_CHANGED")

        QuantifiedRiskHistoryService.record_event(
            risk_id,
            event_type,
            f"Status transitioned from {old_status.value} to {new_status.value}",
        )
        return record

    @classmethod
    def to_response(cls, record: QuantifiedRiskRecord) -> CyberRiskResponse:
        return CyberRiskResponse(
            risk_id=record.risk_id,
            risk_fingerprint=record.risk_fingerprint,
            scenario_type=record.scenario_type,
            title=record.title,
            description=record.description,
            exposure_value=record.exposure_value,
            single_loss_expectancy=record.single_loss_expectancy,
            annualized_loss_expectancy=record.annualized_loss_expectancy,
            inherent_risk_score=record.inherent_risk_score,
            residual_risk_score=record.residual_risk_score,
            mitigation_effectiveness=record.mitigation_effectiveness,
            status=record.status,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
