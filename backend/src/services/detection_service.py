import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from src.domain.entities.detection import DetectionSeverity, DetectionStatus
from src.services.detection_fingerprint_service import DetectionFingerprintService
from src.services.detection_history_service import DetectionHistoryService
from src.services.detection_severity_registry import DetectionSeverityRegistry


class DetectionRecord:
    def __init__(
        self,
        detection_id: uuid.UUID,
        detection_fingerprint: str,
        name: str,
        description: str,
        severity: DetectionSeverity,
        status: DetectionStatus,
        attack_techniques: List[str],
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        scope_id: Optional[uuid.UUID] = None,
    ):
        self.detection_id = detection_id
        self.detection_fingerprint = detection_fingerprint
        self.name = name
        self.description = description
        self.severity = severity
        self.status = status
        self.attack_techniques = attack_techniques
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
        self.scope_id = scope_id


class DetectionService:
    # in-memory store: detection_id -> DetectionRecord
    _detections: Dict[uuid.UUID, DetectionRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_detections(cls) -> None:
        """Clear all in-memory detection records and references."""
        cls._detections.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    def get_all_detections(cls) -> List[DetectionRecord]:
        """Retrieve all detections."""
        return list(cls._detections.values())

    @classmethod
    def get_detection(cls, detection_id: uuid.UUID) -> Optional[DetectionRecord]:
        """Retrieve a specific detection by ID."""
        return cls._detections.get(detection_id)

    @classmethod
    def get_detection_by_fingerprint(cls, fingerprint: str) -> Optional[DetectionRecord]:
        """Retrieve a detection by its fingerprint."""
        det_id = cls._fingerprint_lookup.get(fingerprint)
        if det_id:
            return cls.get_detection(det_id)
        return None

    @classmethod
    def create_or_sync_detection(
        cls,
        name: str,
        description: str,
        severity: Union[DetectionSeverity, str],
        attack_techniques: List[str],
        scope_id: Optional[uuid.UUID] = None,
    ) -> DetectionRecord:
        """Create a new detection or synchronize with an existing one based on fingerprint stability rules."""
        resolved_sev = DetectionSeverityRegistry.resolve_severity(severity)
        fingerprint = DetectionFingerprintService.generate_fingerprint(name, attack_techniques)

        existing = cls.get_detection_by_fingerprint(fingerprint)
        if existing:
            # Sync rules: preserve detection_id, fingerprint, history, created_at, and terminal state
            changed = False
            if existing.description != description:
                existing.description = description
                changed = True
            if existing.severity != resolved_sev:
                existing.severity = resolved_sev
                changed = True
            if existing.scope_id != scope_id:
                existing.scope_id = scope_id
                changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                # If we're updating a terminal state, ensure status is preserved
                DetectionHistoryService.record_event(
                    existing.detection_id,
                    "UPDATED",
                    f"Updated metadata: severity={existing.severity.value}, scope_id={existing.scope_id}",
                )
            return existing

        # Create new active detection
        det_id = uuid.uuid4()
        record = DetectionRecord(
            detection_id=det_id,
            detection_fingerprint=fingerprint,
            name=name,
            description=description,
            severity=resolved_sev,
            status=DetectionStatus.ACTIVE,
            attack_techniques=attack_techniques,
            scope_id=scope_id,
        )
        cls._detections[det_id] = record
        cls._fingerprint_lookup[fingerprint] = det_id

        DetectionHistoryService.record_event(
            det_id, "CREATED", f"Created active detection rule: {name}"
        )
        return record

    @classmethod
    def disable_detection(cls, detection_id: uuid.UUID) -> DetectionRecord:
        """Transition a detection status to DISABLED (terminal status)."""
        det = cls.get_detection(detection_id)
        if not det:
            raise ValueError(f"Detection {detection_id} not found")

        if det.status == DetectionStatus.DISABLED:
            return det

        # DISABLED is terminal
        det.status = DetectionStatus.DISABLED
        det.updated_at = datetime.now(timezone.utc)
        DetectionHistoryService.record_event(
            detection_id, "DISABLED", "Detection rule status set to DISABLED (terminal)"
        )
        return det

    @classmethod
    def deprecate_detection(cls, detection_id: uuid.UUID) -> DetectionRecord:
        """Transition a detection status to DEPRECATED (terminal status)."""
        det = cls.get_detection(detection_id)
        if not det:
            raise ValueError(f"Detection {detection_id} not found")

        if det.status == DetectionStatus.DEPRECATED:
            return det

        # DEPRECATED is terminal
        det.status = DetectionStatus.DEPRECATED
        det.updated_at = datetime.now(timezone.utc)
        DetectionHistoryService.record_event(
            detection_id, "DEPRECATED", "Detection rule status set to DEPRECATED (terminal)"
        )
        return det

    @classmethod
    def update_detection_mapping(cls, detection_id: uuid.UUID, attack_techniques: List[str]) -> DetectionRecord:
        """Update detection attack techniques and append to history."""
        det = cls.get_detection(detection_id)
        if not det:
            raise ValueError(f"Detection {detection_id} not found")

        old_techniques = sorted(det.attack_techniques)
        new_techniques = sorted(list(set(attack_techniques)))
        if old_techniques != new_techniques:
            old_str = ", ".join(old_techniques)
            new_str = ", ".join(new_techniques)
            details = f"ATT&CK techniques updated from [{old_str}] to [{new_str}]"
            DetectionHistoryService.record_event(detection_id, "ATTACK_MAPPING_CHANGED", details)

            # Remove old fingerprint lookup
            old_fp = det.detection_fingerprint
            if old_fp in cls._fingerprint_lookup:
                del cls._fingerprint_lookup[old_fp]

            # Generate new fingerprint
            new_fp = DetectionFingerprintService.generate_fingerprint(det.name, new_techniques)
            det.detection_fingerprint = new_fp
            det.attack_techniques = new_techniques
            det.updated_at = datetime.now(timezone.utc)
            cls._fingerprint_lookup[new_fp] = detection_id

        return det

