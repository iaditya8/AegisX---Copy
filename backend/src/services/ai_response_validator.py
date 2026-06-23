import json
from typing import Any, Dict

from pydantic import ValidationError
from src.domain.entities.copilot_response_schema import (
    AssetExplanationSchema,
    ExecutiveSummarySchema,
    FindingExplanationSchema,
)


class AIResponseValidator:
    @classmethod
    def _parse_and_validate(cls, response_str: str, schema_class) -> Dict[str, Any]:
        try:
            # Clean possible markdown wrapping if any slipped through
            cleaned = response_str.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed_json = json.loads(cleaned)
            validated_model = schema_class(**parsed_json)
            return validated_model.model_dump()
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as e:
            raise ValueError(f"AI response validation failed: {str(e)}") from e

    @classmethod
    def validate_asset_response(cls, response_str: str) -> Dict[str, Any]:
        """Validate and return asset explanation response."""
        return cls._parse_and_validate(response_str, AssetExplanationSchema)

    @classmethod
    def validate_finding_response(cls, response_str: str) -> Dict[str, Any]:
        """Validate and return finding explanation response."""
        return cls._parse_and_validate(response_str, FindingExplanationSchema)

    @classmethod
    def validate_executive_response(cls, response_str: str) -> Dict[str, Any]:
        """Validate and return executive summary response."""
        return cls._parse_and_validate(response_str, ExecutiveSummarySchema)
