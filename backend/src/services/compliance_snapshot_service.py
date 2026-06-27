import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession


class ComplianceSnapshotService:
    # Cache store: scope_id -> Snapshot dictionary
    _snapshots: Dict[Optional[uuid.UUID], dict] = {}

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the GRC snapshot cache."""
        cls._snapshots.clear()

    @classmethod
    def get_snapshot(cls, scope_id: Optional[uuid.UUID] = None) -> dict:
        """Retrieve the cached GRC snapshot, defaulting to a minimal fallback if missing or corrupted."""
        snap = cls._snapshots.get(scope_id)
        if not snap or not isinstance(snap, dict) or "summary" not in snap:
            return {
                "summary": {
                    "total_assessments": 0,
                    "active_assessments": 0,
                    "closed_assessments": 0,
                    "average_compliance_score": 0.0,
                    "average_framework_coverage": 0.0,
                    "average_control_coverage": 0.0,
                    "average_evidence_completeness": 0.0,
                    "average_audit_readiness": 0.0,
                },
                "records": {},
            }
        return snap

    @classmethod
    async def generate_snapshot(
        cls, db: AsyncSession, scope_id: Optional[uuid.UUID] = None
    ) -> dict:
        """Dynamically rebuild GRC snapshot stats from active assessments."""
        from src.services.governance_risk_compliance_service import GovernanceRiskComplianceService
        from src.domain.entities.governance_risk_compliance import ComplianceStatus

        all_recs = GovernanceRiskComplianceService.get_all_assessments()
        if scope_id:
            all_recs = [r for r in all_recs if r.scope_id == scope_id]

        total_recs = len(all_recs)
        active_count = sum(1 for r in all_recs if r.status in (ComplianceStatus.ACTIVE, ComplianceStatus.IN_REVIEW, ComplianceStatus.COMPLIANT, ComplianceStatus.NON_COMPLIANT))
        closed_count = sum(1 for r in all_recs if r.status == ComplianceStatus.CLOSED)

        avg_score = (
            round(sum(r.compliance_score for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )
        avg_framework = (
            round(sum(r.framework_coverage for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )
        avg_control = (
            round(sum(r.control_coverage for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )
        avg_evidence = (
            round(sum(r.evidence_completeness for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )
        avg_readiness = (
            round(sum(r.audit_readiness for r in all_recs) / total_recs, 2)
            if total_recs > 0
            else 0.0
        )

        records_track = {}
        for r in all_recs:
            records_track[str(r.assessment_id)] = {
                "assessment_id": str(r.assessment_id),
                "name": r.name,
                "framework_type": r.framework_type.value,
                "status": r.status.value,
                "compliance_score": r.compliance_score,
                "audit_readiness": r.audit_readiness,
            }

        snapshot = {
            "summary": {
                "total_assessments": total_recs,
                "active_assessments": active_count,
                "closed_assessments": closed_count,
                "average_compliance_score": avg_score,
                "average_framework_coverage": avg_framework,
                "average_control_coverage": avg_control,
                "average_evidence_completeness": avg_evidence,
                "average_audit_readiness": avg_readiness,
            },
            "records": records_track,
        }

        cls._snapshots[scope_id] = snapshot
        return snapshot
