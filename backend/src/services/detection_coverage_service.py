import uuid
from typing import List, Optional, Set, Union

from src.domain.entities.detection import CoverageStatus, DetectionCoverageResponse, DetectionStatus
from src.services.attack_registry import AttackRegistry
from src.services.detection_service import DetectionService


class DetectionCoverageService:
    @classmethod
    def calculate_coverage(
        cls, scope_id: Optional[Union[uuid.UUID, Set[uuid.UUID]]] = None
    ) -> List[DetectionCoverageResponse]:
        """Evaluate coverage status and count for each pre-seeded MITRE ATT&CK technique."""
        registered = AttackRegistry.get_registered_techniques()
        detections = DetectionService.get_all_detections()

        # Scope filtering
        if scope_id:
            if isinstance(scope_id, uuid.UUID):
                allowed_scopes = {scope_id}
            else:
                allowed_scopes = set(scope_id)
            detections = [d for d in detections if d.scope_id in allowed_scopes]

        # Map each technique to its associated detections
        tech_map = {t: [] for t in registered}
        for d in detections:
            for t in d.attack_techniques:
                if t in tech_map:
                    tech_map[t].append(d)

        results = []
        covered_count = 0

        for t in registered:
            matched_detections = tech_map[t]
            count = len(matched_detections)

            if count == 0:
                status = CoverageStatus.NOT_COVERED
            else:
                has_active = any(d.status == DetectionStatus.ACTIVE for d in matched_detections)
                if has_active:
                    status = CoverageStatus.COVERED
                else:
                    status = CoverageStatus.PARTIALLY_COVERED

            if status == CoverageStatus.COVERED:
                covered_count += 1

            results.append((t, status, count))

        # Overall coverage score: covered techniques / total techniques
        total_techniques = len(registered)
        score = (covered_count / total_techniques) if total_techniques > 0 else 0.0

        return [
            DetectionCoverageResponse(
                technique_id=t,
                coverage_status=status,
                detection_count=count,
                coverage_score=score,
            )
            for t, status, count in sorted(results, key=lambda x: x[0])
        ]

    @classmethod
    def calculate_overall_score(
        cls, scope_id: Optional[Union[uuid.UUID, Set[uuid.UUID]]] = None
    ) -> float:
        """Calculate overall coverage score."""
        coverage = cls.calculate_coverage(scope_id)
        if not coverage:
            return 0.0
        return coverage[0].coverage_score
