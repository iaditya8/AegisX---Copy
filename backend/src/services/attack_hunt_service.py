import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.entities.hunt import HuntSeverity, HuntType
from src.domain.entities.detection import CoverageStatus
from src.infrastructure.database.models import Finding
from src.services.detection_coverage_service import DetectionCoverageService
from src.services.hunt_service import HuntService
from src.services.hunt_hypothesis_service import HuntHypothesisService
from src.services.hunt_finding_service import HuntFindingService


class AttackHuntService:
    @classmethod
    async def sync_attack_hunts(cls, db: AsyncSession) -> None:
        """Automatically generate threat hunts based on ATT&CK coverage status and detection gaps."""
        # 1. Fetch all active findings in the system
        res_findings = await db.execute(select(Finding))
        findings = list(res_findings.scalars().all())

        # 2. Get coverage status of all techniques
        coverages = DetectionCoverageService.calculate_coverage()

        for cov in coverages:
            # If the technique is already fully covered, skip
            if cov.coverage_status == CoverageStatus.COVERED:
                continue

            # Determine hunt parameters based on coverage state
            if cov.coverage_status == CoverageStatus.NOT_COVERED:
                hunt_type = HuntType.DETECTION_GAP
                severity = HuntSeverity.HIGH
                status_desc = "uncovered technique (detection gap)"
            else:
                hunt_type = HuntType.ATTACK_DRIVEN
                severity = HuntSeverity.MEDIUM
                status_desc = "partially covered technique"

            tech_id = cov.technique_id
            title = f"ATT&CK Technique Hunting: {tech_id}"
            desc = (
                f"Automatically generated threat hunt focusing on technique {tech_id} "
                f"due to status as a {status_desc}."
            )
            related_entities = [{"entity_type": "Technique", "entity_id": tech_id}]

            # Create or sync hunt
            hunt = await HuntService.create_or_sync_hunt(
                title=title,
                description=desc,
                hunt_type=hunt_type,
                severity=severity,
                related_entities=related_entities
            )

            # Auto-create standard hypothesis
            hypothesis_text = f"Verify whether malicious activity exploiting technique {tech_id} is present and undetected in the environment."
            existing_hyps = await HuntHypothesisService.get_hypotheses(hunt.hunt_id)
            if not any(h.description == hypothesis_text for h in existing_hyps):
                await HuntHypothesisService.create_hypothesis(hunt.hunt_id, hypothesis_text)

            # Correlate with existing findings referencing this technique
            for f in findings:
                metadata_str = str(f.metadata_json or "").lower()
                text_to_search = f"{f.title} {f.description} {metadata_str}".lower()
                if tech_id.lower() in text_to_search:
                    await HuntFindingService.create_finding(
                        hunt_id=hunt.hunt_id,
                        entity_type="Finding",
                        entity_id=f.id,
                        details=f"Correlated finding detected: '{f.title}' matching technique {tech_id}."
                    )
