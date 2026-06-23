import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from src.services.ai_audit_service import AIAuditService
from src.services.ai_cache_service import AICacheService
from src.services.ai_context_builder import CONTEXT_VERSION, AIContextBuilder
from src.services.ai_guardrails import AIGuardrails
from src.services.ai_prompt_builder import AIPromptBuilder
from src.services.ai_provider_registry import AIProviderRegistry
from src.services.ai_response_validator import AIResponseValidator

logger = logging.getLogger(__name__)


class AssetCopilotService:
    @classmethod
    async def explain_asset(
        cls, db: AsyncSession, asset_id: uuid.UUID, actor_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Generate or retrieve a cached security explanation for the given asset."""
        now_str = datetime.now(timezone.utc).isoformat()
        fallback_response = {
            "success": False,
            "source": "fallback",
            "message": "AI explanation unavailable",
            "generated_at": now_str,
            "summary": "",
            "risk_analysis": "",
            "priority_reasons": [],
        }

        try:
            # 1. Build and sanitize context
            context = await AIContextBuilder.build_asset_context(db, asset_id)
            sanitized = AIGuardrails.validate_asset_context(context)

            # 2. Build prompt and prompt hash
            prompt = AIPromptBuilder.build_asset_prompt(sanitized)
            prompt_hash = AIAuditService.calculate_hash(prompt)

            # 3. Check cache
            cache_key = (asset_id, CONTEXT_VERSION, prompt_hash)
            cached_payload = AICacheService.get(cache_key)

            if cached_payload:
                return {
                    "success": True,
                    "source": "cache",
                    "message": "AI explanation retrieved from cache",
                    "generated_at": now_str,
                    "summary": cached_payload.get("summary", ""),
                    "risk_analysis": cached_payload.get("risk_analysis", ""),
                    "priority_reasons": cached_payload.get("priority_reasons", []),
                }

            # 4. Resolve provider and generate
            provider = AIProviderRegistry.get_provider()
            raw_response = await provider.generate(prompt)

            # 5. Validate response structure
            validated = AIResponseValidator.validate_asset_response(raw_response)

            # 6. Set cache
            AICacheService.set(cache_key, validated, asset_id=asset_id)

            # 7. Audit log the transaction
            await AIAuditService.log_copilot_request(
                db=db,
                actor_id=actor_id,
                request_type="explain_asset",
                target_id=asset_id,
                prompt=prompt,
                response_str=raw_response,
                provider_name=provider.get_name(),
                provider_version=provider.get_version(),
                asset_id=asset_id,
            )

            return {
                "success": True,
                "source": provider.get_name(),
                "message": "AI explanation generated",
                "generated_at": now_str,
                "summary": validated.get("summary", ""),
                "risk_analysis": validated.get("risk_analysis", ""),
                "priority_reasons": validated.get("priority_reasons", []),
            }

        except Exception as e:
            logger.error(
                f"Error in explain_asset for asset {asset_id}: {str(e)}", exc_info=True
            )
            return fallback_response
