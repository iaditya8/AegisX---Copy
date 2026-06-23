import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import Finding
from src.services.ai_audit_service import AIAuditService
from src.services.ai_cache_service import AICacheService
from src.services.ai_context_builder import CONTEXT_VERSION, AIContextBuilder
from src.services.ai_guardrails import AIGuardrails
from src.services.ai_prompt_builder import AIPromptBuilder
from src.services.ai_provider_registry import AIProviderRegistry
from src.services.ai_response_validator import AIResponseValidator

logger = logging.getLogger(__name__)


class FindingCopilotService:
    @classmethod
    async def explain_finding(
        cls,
        db: AsyncSession,
        finding_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Generate or retrieve a cached explanation for the given finding."""
        now_str = datetime.now(timezone.utc).isoformat()
        fallback_response = {
            "success": False,
            "source": "fallback",
            "message": "AI explanation unavailable",
            "generated_at": now_str,
            "summary": "",
            "impact": "",
            "priority": "",
            "investigation_guidance": "",
        }

        try:
            # 1. Fetch finding to get asset_id
            finding = await db.get(Finding, finding_id)
            if not finding:
                logger.warning(f"Finding {finding_id} not found in DB")
                return fallback_response

            asset_id = finding.asset_id

            # 2. Build and sanitize context
            context = await AIContextBuilder.build_finding_context(db, finding_id)
            sanitized = AIGuardrails.validate_finding_context(context)

            # 3. Build prompt and prompt hash
            prompt = AIPromptBuilder.build_finding_prompt(sanitized)
            prompt_hash = AIAuditService.calculate_hash(prompt)

            # 4. Check cache
            cache_key = (finding_id, CONTEXT_VERSION, prompt_hash)
            cached_payload = AICacheService.get(cache_key)

            if cached_payload:
                return {
                    "success": True,
                    "source": "cache",
                    "message": "AI explanation retrieved from cache",
                    "generated_at": now_str,
                    "summary": cached_payload.get("summary", ""),
                    "impact": cached_payload.get("impact", ""),
                    "priority": cached_payload.get("priority", ""),
                    "investigation_guidance": cached_payload.get(
                        "investigation_guidance", ""
                    ),
                }

            # 5. Resolve provider and generate
            provider = AIProviderRegistry.get_provider()
            raw_response = await provider.generate(prompt)

            # 6. Validate response structure
            validated = AIResponseValidator.validate_finding_response(raw_response)

            # 7. Set cache
            AICacheService.set(cache_key, validated, asset_id=asset_id)

            # 8. Audit log the transaction
            await AIAuditService.log_copilot_request(
                db=db,
                actor_id=actor_id,
                request_type="explain_finding",
                target_id=finding_id,
                prompt=prompt,
                response_str=raw_response,
                provider_name=provider.get_name(),
                provider_version=provider.get_version(),
                asset_id=asset_id,
                finding_id=finding_id,
            )

            return {
                "success": True,
                "source": provider.get_name(),
                "message": "AI explanation generated",
                "generated_at": now_str,
                "summary": validated.get("summary", ""),
                "impact": validated.get("impact", ""),
                "priority": validated.get("priority", ""),
                "investigation_guidance": validated.get("investigation_guidance", ""),
            }

        except Exception as e:
            logger.error(
                f"Error in explain_finding for finding {finding_id}: {str(e)}",
                exc_info=True,
            )
            return fallback_response
