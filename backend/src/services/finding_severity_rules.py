from typing import Union

# Severity Rank Mapping
SEVERITY_RANKINGS = {
    "info": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
}


class FindingSeverityRules:
    @staticmethod
    def normalize_severity(value: Union[str, int]) -> str:
        """Normalize a severity input to its lowercase canonical representation."""
        if not value:
            return "info"

        if isinstance(value, int):
            # Map rank back to string if needed
            rank_to_sev = {v: k for k, v in SEVERITY_RANKINGS.items()}
            return rank_to_sev.get(value, "info")

        val_lower = str(value).strip().lower()
        if val_lower in SEVERITY_RANKINGS:
            return val_lower

        return "info"

    @staticmethod
    def severity_rank(value: Union[str, int]) -> int:
        """Retrieve the integer rank of a severity level (1-5)."""
        normalized = FindingSeverityRules.normalize_severity(value)
        return SEVERITY_RANKINGS.get(normalized, 1)

    @staticmethod
    def is_valid_severity(value: Union[str, int]) -> bool:
        """Check if the given value represents a valid supported severity level."""
        if not value:
            return False
        if isinstance(value, int):
            return value in SEVERITY_RANKINGS.values()

        return str(value).strip().lower() in SEVERITY_RANKINGS
