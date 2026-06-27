import uuid
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.detection import DetectionStatus
from src.infrastructure.database.models import Asset, Finding
from src.services.detection_service import DetectionService


class DetectionValidationService:
    @classmethod
    async def validate_detection_effectiveness(cls, db: AsyncSession, scope_id: uuid.UUID) -> Dict[str, Any]:
        """Assess the validation status and effectiveness of registered detection rules in a scope."""
        # Get active findings
        q_findings = (
            select(Finding)
            .join(Asset)
            .where(Asset.scope_id == scope_id, Asset.deleted_at.is_(None))
        )
        res_findings = await db.execute(q_findings)
        findings = list(res_findings.scalars().all())

        # Get all detections
        detections = DetectionService.get_all_detections()
        scope_detections = [
            d for d in detections
            if not d.scope_id or d.scope_id == scope_id
        ]

        total_rules = len(scope_detections)
        active_rules = [d for d in scope_detections if d.status == DetectionStatus.ACTIVE]
        total_active = len(active_rules)

        effective_rules = 0
        ineffective_rules = 0

        for rule in active_rules:
            # A rule is effective if there is any active finding matching its signature/techniques
            is_effective = False
            for tech in rule.attack_techniques:
                for f in findings:
                    if tech in str(f.title) or tech in str(f.description):
                        is_effective = True
                        break
                if is_effective:
                    break

            if is_effective:
                effective_rules += 1
            else:
                ineffective_rules += 1

        effectiveness_rate = (effective_rules / total_active * 100.0) if total_active > 0 else 100.0

        return {
            "total_rules": total_rules,
            "total_active": total_active,
            "effective_rules": effective_rules,
            "ineffective_rules": ineffective_rules,
            "effectiveness_rate": round(effectiveness_rate, 2),
        }
