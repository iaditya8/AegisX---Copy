import hashlib
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import FindingEvidence


class FindingEvidenceService:
    """Service to persist finding evidence records as append-only versions."""

    @staticmethod
    def calculate_evidence_hash(
        raw_request: Optional[str],
        raw_response: Optional[str],
        matcher_name: Optional[str],
        matcher_value: Optional[str],
    ) -> str:
        """Generate a SHA-256 hash of the evidence fields."""
        req = raw_request or ""
        res = raw_response or ""
        m_name = matcher_name or ""
        m_val = matcher_value or ""

        raw_str = f"{req}{res}{m_name}{m_val}"
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    @classmethod
    async def create_evidence(
        cls,
        db: AsyncSession,
        finding_id: uuid.UUID,
        evidence_type: str,
        raw_request: Optional[str],
        raw_response: Optional[str],
        matched_at: Optional[str],
        matcher_name: Optional[str],
        matcher_value: Optional[str],
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> FindingEvidence:
        """Create a new FindingEvidence record if it doesn't exist."""
        evidence_hash = cls.calculate_evidence_hash(
            raw_request, raw_response, matcher_name, matcher_value
        )

        # Check for existence of this exact evidence
        q = select(FindingEvidence).where(
            FindingEvidence.evidence_hash == evidence_hash
        )
        res = await db.execute(q)
        existing = res.scalar_one_or_none()

        if existing:
            return existing

        # Create new version
        new_evidence = FindingEvidence(
            finding_id=finding_id,
            evidence_type=evidence_type,
            raw_request=raw_request,
            raw_response=raw_response,
            matched_at=matched_at,
            matcher_name=matcher_name,
            matcher_value=matcher_value,
            metadata_json=metadata_json or {},
            evidence_hash=evidence_hash,
        )

        db.add(new_evidence)
        await db.commit()
        await db.refresh(new_evidence)
        return new_evidence
