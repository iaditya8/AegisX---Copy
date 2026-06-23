import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.services.audit_service import create_audit_entry


class AIAuditService:
    @staticmethod
    def calculate_hash(text: str) -> str:
        """Compute SHA-256 hash of a string."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    async def log_copilot_request(
        cls,
        db: AsyncSession,
        actor_id: Optional[uuid.UUID],
        request_type: str,  # explain_asset, explain_finding, generate_executive
        target_id: uuid.UUID,
        prompt: str,
        response_str: str,
        provider_name: str,
        provider_version: str,
        asset_id: Optional[uuid.UUID] = None,
        finding_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Log request metadata inside the audit logs table."""
        prompt_hash = cls.calculate_hash(prompt)
        response_hash = cls.calculate_hash(response_str)

        metadata = {
            "request_type": request_type,
            "asset_id": str(asset_id) if asset_id else None,
            "finding_id": str(finding_id) if finding_id else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "prompt_hash": prompt_hash,
            "response_hash": response_hash,
            "provider": provider_name,
            "provider_version": provider_version,
        }

        # Target ID can be the asset or finding, target_type is "copilot"
        await create_audit_entry(
            db=db,
            actor_id=actor_id,
            action="copilot.requested",
            target_type="copilot",
            target_id=target_id,
            metadata=metadata,
        )
