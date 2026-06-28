import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.domain.entities.security_decision import (
    DecisionResponse,
    DecisionStatus,
    DecisionType,
)
from src.services.decision_type_registry import DecisionTypeRegistry
from src.services.decision_fingerprint_service import DecisionFingerprintService
from src.services.decision_history_service import DecisionHistoryService


class SecurityDecisionService:
    # in-memory store: decision_id -> DecisionResponse
    _decisions: Dict[uuid.UUID, DecisionResponse] = {}
    # fingerprint -> decision_id
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_decisions(cls) -> None:
        """Clear all in-memory decisions and registry caches."""
        cls._decisions.clear()
        cls._fingerprint_lookup.clear()
        DecisionHistoryService.clear_history()

    @classmethod
    def get_all_decisions(cls) -> List[DecisionResponse]:
        """Retrieve all decisions currently tracked."""
        return list(cls._decisions.values())

    @classmethod
    def get_decision(cls, decision_id: uuid.UUID) -> Optional[DecisionResponse]:
        """Retrieve a specific decision by ID."""
        return cls._decisions.get(decision_id)

    @classmethod
    def get_decision_by_fingerprint(cls, fingerprint: str) -> Optional[DecisionResponse]:
        """Retrieve a decision by fingerprint."""
        did = cls._fingerprint_lookup.get(fingerprint)
        if did:
            return cls.get_decision(did)
        return None

    @classmethod
    def _get_uuid(cls, val) -> Optional[uuid.UUID]:
        if isinstance(val, uuid.UUID):
            return val
        if isinstance(val, str):
            try:
                return uuid.UUID(val)
            except ValueError:
                pass
        return None

    @classmethod
    def create_or_sync_decision(
        cls,
        decision_type: DecisionType,
        target_entity_id: uuid.UUID,
        option_name: str,
        scope_id: Optional[uuid.UUID] = None,
    ) -> DecisionResponse:
        """Create or synchronize a security decision option enforcing terminal state protection."""
        # Validate decision type
        type_str = decision_type.value if hasattr(decision_type, "value") else str(decision_type)
        if not DecisionTypeRegistry.validate(type_str):
            raise ValueError(f"Invalid Decision Type: {decision_type}")

        decision_type_enum = DecisionType(type_str)

        # Generate stable fingerprint
        fingerprint = DecisionFingerprintService.generate_fingerprint(
            decision_type_enum, target_entity_id, option_name
        )

        existing = cls.get_decision_by_fingerprint(fingerprint)
        if existing:
            # Enforce Decision Terminal State Rule: sync cannot reactivate ARCHIVED decisions
            if existing.status == DecisionStatus.ARCHIVED:
                return existing
            return existing

        # Create new decision recommendation
        decision_id = uuid.uuid4()
        decision = DecisionResponse(
            decision_id=decision_id,
            decision_fingerprint=fingerprint,
            decision_type=decision_type_enum,
            target_entity_id=target_entity_id,
            option_name=option_name,
            status=DecisionStatus.ACTIVE,
            scope_id=cls._get_uuid(scope_id),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            tradeoff_matrix=None,
            impact_metrics=None,
        )

        cls._decisions[decision_id] = decision
        cls._fingerprint_lookup[fingerprint] = decision_id

        # Record history event
        DecisionHistoryService.record_event(
            decision_id, "CREATED", f"Created decision recommendation: {option_name}"
        )

        return decision

    @classmethod
    def recommend_decision(cls, decision_id: uuid.UUID) -> DecisionResponse:
        """Transition decision to RECOMMENDED status."""
        decision = cls.get_decision(decision_id)
        if not decision:
            raise ValueError(f"Decision with ID {decision_id} not found")

        # Enforce Decision Terminal State Rule
        if decision.status == DecisionStatus.ARCHIVED:
            return decision

        if decision.status != DecisionStatus.RECOMMENDED:
            decision.status = DecisionStatus.RECOMMENDED
            decision.updated_at = datetime.now(timezone.utc)
            DecisionHistoryService.record_event(
                decision_id, "RECOMMENDED", "Decision option status changed to RECOMMENDED"
            )

        return decision

    @classmethod
    def commit_decision(cls, decision_id: uuid.UUID) -> DecisionResponse:
        """Transition decision to COMMITTED status."""
        decision = cls.get_decision(decision_id)
        if not decision:
            raise ValueError(f"Decision with ID {decision_id} not found")

        # Enforce Decision Terminal State Rule
        if decision.status == DecisionStatus.ARCHIVED:
            return decision

        if decision.status != DecisionStatus.COMMITTED:
            decision.status = DecisionStatus.COMMITTED
            decision.updated_at = datetime.now(timezone.utc)
            DecisionHistoryService.record_event(
                decision_id, "COMMITTED", "Decision option status changed to COMMITTED"
            )

        return decision

    @classmethod
    def archive_decision(cls, decision_id: uuid.UUID) -> DecisionResponse:
        """Transition decision to ARCHIVED status."""
        decision = cls.get_decision(decision_id)
        if not decision:
            raise ValueError(f"Decision with ID {decision_id} not found")

        if decision.status != DecisionStatus.ARCHIVED:
            decision.status = DecisionStatus.ARCHIVED
            decision.updated_at = datetime.now(timezone.utc)
            DecisionHistoryService.record_event(
                decision_id, "ARCHIVED", "Decision option status changed to ARCHIVED"
            )

        return decision

    @classmethod
    async def sync_decision_recommendations(cls, db=None) -> None:
        """Query GRC assessments and other active domains to sync decision recommendations."""
        # 1. GRC Assessments
        from src.services.governance_risk_compliance_service import GovernanceRiskComplianceService
        assessments = GovernanceRiskComplianceService.get_all_assessments()
        for assess in assessments:
            if isinstance(assess, dict):
                fw_type = assess.get("framework_type") or assess.get("framework_name") or "Framework"
                target_id = assess.get("assessment_id")
                scope_id = assess.get("scope_id")
            else:
                fw_val = getattr(assess, "framework_type", None)
                if fw_val and hasattr(fw_val, "value"):
                    fw_type = fw_val.value
                elif fw_val:
                    fw_type = str(fw_val)
                else:
                    fw_type = "Framework"
                target_id = assess.assessment_id
                scope_id = assess.scope_id

            # Apply framework name mapping formatting (replace _ with space) (Finding 3 fix)
            fw_formatted = fw_type.replace("_", " ")
            option_name = f"Implement Control: {fw_formatted}"

            cls.create_or_sync_decision(
                decision_type=DecisionType.COMPLIANCE_CONTROL,
                target_entity_id=target_id,
                option_name=option_name,
                scope_id=scope_id,
            )

        # 2. Remediations
        from src.services.remediation_service import RemediationService
        for rem in RemediationService.get_all_remediations():
            scope_id = None
            if db:
                try:
                    from src.infrastructure.database.models import Asset
                    asset = await db.get(Asset, rem.asset_id)
                    if asset:
                        scope_id = asset.scope_id
                except Exception:
                    pass
            cls.create_or_sync_decision(
                decision_type=DecisionType.REMEDIATION,
                target_entity_id=rem.remediation_id,
                option_name=f"Remediate Vulnerability: {rem.remediation_id}",
                scope_id=scope_id,
            )
