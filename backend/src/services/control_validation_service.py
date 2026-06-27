import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.control_validation import (
    ControlSeverity,
    ControlStatus,
    ValidationStatus,
    ControlType,
    ControlResponse,
    ValidationResponse,
)
from src.infrastructure.database.models import Asset
from src.services.control_type_registry import ControlTypeRegistry
from src.services.control_severity_registry import ControlSeverityRegistry
from src.services.effectiveness_registry import EffectivenessRegistry
from src.services.control_fingerprint_service import ControlFingerprintService
from src.services.control_history_service import ControlHistoryService
from src.services.effectiveness_scoring_service import EffectivenessScoringService
from src.services.control_correlation_service import ControlCorrelationService
from src.services.detection_service import DetectionService
from src.services.purple_team_service import PurpleTeamService
from src.services.hunt_service import HuntService


class ControlRecord:
    def __init__(
        self,
        control_id: uuid.UUID,
        control_fingerprint: str,
        name: str,
        description: str,
        control_type: ControlType,
        severity: ControlSeverity,
        status: ControlStatus,
        effectiveness_score: float,
        attack_techniques: List[str],
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.control_id = control_id
        self.control_fingerprint = control_fingerprint
        self.name = name
        self.description = description
        self.control_type = control_type
        self.severity = severity
        self.status = status
        self.effectiveness_score = effectiveness_score
        self.attack_techniques = list(attack_techniques)
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class ControlValidationService:
    # in-memory store: control_id -> ControlRecord
    _controls: Dict[uuid.UUID, ControlRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    # validation store: control_id -> list of ValidationResponse
    _validations: Dict[uuid.UUID, List[ValidationResponse]] = {}

    # effectiveness history: control_id -> list of floats
    _effectiveness_history: Dict[uuid.UUID, List[float]] = {}

    @classmethod
    def clear_controls(cls) -> None:
        """Clear all control validation caches."""
        cls._controls.clear()
        cls._fingerprint_lookup.clear()
        cls._validations.clear()
        cls._effectiveness_history.clear()

    @classmethod
    def get_all_controls(cls) -> List[ControlRecord]:
        """Retrieve all control records."""
        return list(cls._controls.values())

    @classmethod
    def get_control(cls, control_id: uuid.UUID) -> Optional[ControlRecord]:
        """Retrieve a control record by ID."""
        return cls._controls.get(control_id)

    @classmethod
    def get_control_by_fingerprint(cls, fingerprint: str) -> Optional[ControlRecord]:
        """Retrieve a control record by fingerprint."""
        control_id = cls._fingerprint_lookup.get(fingerprint)
        if control_id:
            return cls.get_control(control_id)
        return None

    @classmethod
    def get_validations(cls, control_id: uuid.UUID) -> List[ValidationResponse]:
        """Retrieve validations for a control."""
        return copy.deepcopy(cls._validations.get(control_id, []))

    @classmethod
    def get_effectiveness_history(cls, control_id: uuid.UUID) -> List[float]:
        """Retrieve historical effectiveness scores."""
        return list(cls._effectiveness_history.get(control_id, []))

    @classmethod
    async def create_or_sync_control(
        cls,
        name: str,
        description: str,
        control_type: ControlType,
        severity: ControlSeverity,
        attack_techniques: List[str],
        scope_id: Optional[uuid.UUID] = None,
    ) -> ControlRecord:
        """Create a new control or synchronize with an existing one based on identity rules."""
        resolved_type = ControlTypeRegistry.resolve_type(control_type)
        resolved_severity = ControlSeverityRegistry.resolve_severity(severity)
        fingerprint = ControlFingerprintService.generate_fingerprint(name, attack_techniques, resolved_type)

        existing = cls.get_posture_by_fingerprint_safe(fingerprint)
        if existing:
            if existing.status == ControlStatus.RETIRED:
                # RETIRED is terminal. Synchronization cannot reactivate or modify retired controls.
                return existing

            # Identity preservation: preserve control_id, history, timestamps, and details
            changed = False
            if existing.description != description:
                existing.description = description
                changed = True
            if existing.severity != resolved_severity:
                existing.severity = resolved_severity
                changed = True

            # Recalculate scores and status
            validations = cls.get_validations(existing.control_id)
            scores = EffectivenessScoringService.calculate_effectiveness(validations, existing.attack_techniques)
            new_eff = scores["effectiveness_score"]

            if existing.effectiveness_score != new_eff:
                existing.effectiveness_score = new_eff
                changed = True
                cls._effectiveness_history.setdefault(existing.control_id, []).append(new_eff)
                ControlHistoryEntry_obj = ControlHistoryService.record_event(
                    existing.control_id,
                    "EFFECTIVENESS_CHANGED",
                    f"Effectiveness recalculated: {new_eff}",
                )

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                ControlHistoryService.record_event(
                    existing.control_id,
                    "DRIFT_DETECTED",
                    f"Control details synced: severity={existing.severity.value}",
                )
            return existing

        # Create new control record
        control_id = uuid.uuid4()
        record = ControlRecord(
            control_id=control_id,
            control_fingerprint=fingerprint,
            name=name,
            description=description,
            control_type=resolved_type,
            severity=resolved_severity,
            status=ControlStatus.ACTIVE,
            effectiveness_score=100.0,  # Default to 100.0 when new
            attack_techniques=attack_techniques,
            scope_id=scope_id,
        )
        cls._controls[control_id] = record
        cls._fingerprint_lookup[fingerprint] = control_id
        cls._effectiveness_history[control_id] = [100.0]

        ControlHistoryService.record_event(
            control_id,
            "CREATED",
            f"Created security control: '{name}' ({resolved_type.value})",
        )
        return record

    @classmethod
    def get_posture_by_fingerprint_safe(cls, fingerprint: str) -> Optional[ControlRecord]:
        return cls.get_control_by_fingerprint(fingerprint)

    @classmethod
    async def sync_controls(cls, db: AsyncSession) -> List[ControlRecord]:
        """Discover and sync controls based on local emulation, alerts, and detections data."""
        synced = []

        # 1. Detection-based Control
        detections = DetectionService.get_all_detections()
        if detections:
            techs = list({d.technique_id for d in detections if d.technique_id})
            post = await cls.create_or_sync_control(
                name="Endpoint Detection Control",
                description="Monitors and alerts on hostile techniques via detection rules.",
                control_type=ControlType.DETECTION,
                severity=ControlSeverity.HIGH,
                attack_techniques=techs,
            )
            synced.append(post)

        # 2. Purple Team emulation Control
        exercises = PurpleTeamService.get_all_exercises()
        if exercises:
            techs = set()
            for e in exercises:
                if hasattr(e, "related_techniques") and e.related_techniques:
                    techs.update(e.related_techniques)
            if techs:
                post = await cls.create_or_sync_control(
                    name="Purple Team Validation Control",
                    description="Prevents attacker activities verified via purple team emulations.",
                    control_type=ControlType.PREVENTIVE,
                    severity=ControlSeverity.CRITICAL,
                    attack_techniques=list(techs),
                )
                synced.append(post)

        # 3. Hunt-based Control
        hunts = HuntService.get_all_hunts()
        if hunts:
            techs = set()
            for h in hunts:
                for entity in h.related_entities:
                    if "technique" in entity.get("entity_type", "").lower():
                        techs.add(entity.get("entity_id"))
            if techs:
                post = await cls.create_or_sync_control(
                    name="Threat Hunt Monitoring Control",
                    description="Identifies evasive threat behaviors via proactive monitoring hunts.",
                    control_type=ControlType.MONITORING,
                    severity=ControlSeverity.MEDIUM,
                    attack_techniques=list(techs),
                )
                synced.append(post)

        # Build correlations
        for c in synced:
            await ControlCorrelationService.correlate_control(db, c.control_id, c.attack_techniques)

        return synced

    @classmethod
    async def execute_validation(
        cls,
        db: AsyncSession,
        control_id: uuid.UUID,
        attack_technique: str,
        status: ValidationStatus,
        evidence: str,
    ) -> ValidationResponse:
        """Execute a control validation run, record results, and recalculate effectiveness."""
        control = cls.get_control(control_id)
        if not control:
            raise ValueError(f"Control {control_id} not found")

        if control.status == ControlStatus.RETIRED:
            raise ValueError("RETIRED is a terminal state")

        validation_id = uuid.uuid4()
        
        # Calculate new validation score
        temp_validations = cls.get_validations(control_id)
        
        # Add mock validation object for scoring
        class MockValidation:
            def __init__(self, val_status, tech):
                self.validation_status = val_status
                self.attack_technique = tech
        
        mock_val = MockValidation(status, attack_technique)
        temp_validations.append(mock_val)
        
        scores = EffectivenessScoringService.calculate_effectiveness(temp_validations, control.attack_techniques)
        eff_score = scores["effectiveness_score"]

        # Instantiate real ValidationResponse
        resp = ValidationResponse(
            validation_id=validation_id,
            control_id=control_id,
            validation_status=status,
            effectiveness_score=eff_score,
            attack_technique=attack_technique,
            evidence=evidence,
            created_at=datetime.now(timezone.utc),
        )

        # Validation Preservation Rule: Existing validations are never deleted/modified.
        cls._validations.setdefault(control_id, []).append(resp)

        # Update control state
        control.effectiveness_score = eff_score
        control.updated_at = datetime.now(timezone.utc)

        # Update status based on score thresholds
        old_status = control.status
        if eff_score >= 70.0:
            control.status = ControlStatus.ACTIVE
        elif eff_score >= 20.0:
            control.status = ControlStatus.DEGRADED
        else:
            control.status = ControlStatus.FAILED

        # History Preservation Rule: existing entries must never be deleted/modified.
        cls._effectiveness_history.setdefault(control_id, []).append(eff_score)
        
        ControlHistoryService.record_event(
            control_id,
            "VALIDATED",
            f"Validation run completed. status={status.value}, tech={attack_technique}",
        )

        if old_status != control.status:
            ControlHistoryService.record_event(
                control_id,
                "DRIFT_DETECTED",
                f"Control status drifted from {old_status.value} to {control.status.value}",
            )

        # Update correlations
        await ControlCorrelationService.correlate_control(db, control_id, control.attack_techniques)

        return resp

    @classmethod
    def retire_control(cls, control_id: uuid.UUID) -> ControlRecord:
        """Transition control status to RETIRED (terminal state)."""
        control = cls.get_control(control_id)
        if not control:
            raise ValueError(f"Control {control_id} not found")

        if control.status == ControlStatus.RETIRED:
            return control

        control.status = ControlStatus.RETIRED
        control.updated_at = datetime.now(timezone.utc)
        ControlHistoryService.record_event(
            control_id, "RETIRED", "Control retired by operator. This is terminal."
        )
        return control

    @classmethod
    def to_response(cls, record: ControlRecord) -> ControlResponse:
        """Convert a ControlRecord to a ControlResponse schema."""
        return ControlResponse(
            control_id=record.control_id,
            control_fingerprint=record.control_fingerprint,
            name=record.name,
            description=record.description,
            control_type=record.control_type,
            severity=record.severity,
            status=record.status,
            effectiveness_score=record.effectiveness_score,
            attack_techniques=record.attack_techniques,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
