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


class ExecutiveCopilotService:
    @classmethod
    async def generate_executive_summary(
        cls, db: AsyncSession, actor_id: Optional[uuid.UUID] = None
    ) -> Dict[str, Any]:
        """Generate/retrieve cached organizational executive summary explanation."""
        now_str = datetime.now(timezone.utc).isoformat()
        fallback_response = {
            "success": False,
            "source": "fallback",
            "message": "AI explanation unavailable",
            "generated_at": now_str,
            "executive_summary": "",
            "top_risks": [],
            "notable_changes": [],
        }

        try:
            # 1. Build and sanitize context
            context = await AIContextBuilder.build_executive_context(db)
            sanitized = AIGuardrails.validate_executive_context(context)

            # 2. Build prompt and prompt hash
            prompt = AIPromptBuilder.build_executive_prompt(sanitized)
            prompt_hash = AIAuditService.calculate_hash(prompt)

            # 3. Check cache
            # Compound key: ("executive", CONTEXT_VERSION, prompt_hash)
            cache_key = ("executive", CONTEXT_VERSION, prompt_hash)
            cached_payload = AICacheService.get(cache_key)

            if cached_payload:
                return {
                    "success": True,
                    "source": "cache",
                    "message": "AI explanation retrieved from cache",
                    "generated_at": now_str,
                    "executive_summary": cached_payload.get("executive_summary", ""),
                    "top_risks": cached_payload.get("top_risks", []),
                    "notable_changes": cached_payload.get("notable_changes", []),
                }

            # 4. Resolve provider and generate
            provider = AIProviderRegistry.get_provider()
            raw_response = await provider.generate(prompt)

            # 5. Validate response structure
            validated = AIResponseValidator.validate_executive_response(raw_response)

            # 6. Set cache (asset_id = "executive")
            AICacheService.set(cache_key, validated, asset_id="executive")

            # 7. Audit log transaction (target_id is actor_id or new uuid)
            target_id = actor_id or uuid.uuid4()
            await AIAuditService.log_copilot_request(
                db=db,
                actor_id=actor_id,
                request_type="generate_executive_summary",
                target_id=target_id,
                prompt=prompt,
                response_str=raw_response,
                provider_name=provider.get_name(),
                provider_version=provider.get_version(),
            )

            return {
                "success": True,
                "source": provider.get_name(),
                "message": "AI explanation generated",
                "generated_at": now_str,
                "executive_summary": validated.get("executive_summary", ""),
                "top_risks": validated.get("top_risks", []),
                "notable_changes": validated.get("notable_changes", []),
            }

        except Exception as e:
            logger.error(
                f"Error in generate_executive_summary: {str(e)}", exc_info=True
            )
            return fallback_response
