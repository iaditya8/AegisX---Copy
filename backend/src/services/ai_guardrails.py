from typing import Any


class AIGuardrails:
    SENSITIVE_KEYS = {
        "password",
        "pass",
        "api_key",
        "apikey",
        "secret",
        "token",
        "cookie",
        "session",
        "auth",
        "authorization",
        "raw_request",
        "raw_response",
    }

    @classmethod
    def sanitize_context(cls, context: Any) -> Any:
        """Recursively scan context structures to redact credentials and secrets."""
        if isinstance(context, dict):
            sanitized = {}
            for k, v in context.items():
                k_lower = k.lower()
                # Check if the key indicates sensitivity
                is_sensitive_key = any(s in k_lower for s in cls.SENSITIVE_KEYS)
                if is_sensitive_key:
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = cls.sanitize_context(v)
            return sanitized
        elif isinstance(context, list):
            return [cls.sanitize_context(item) for item in context]
        elif isinstance(context, str):
            # Check string value for Bearer/Basic headers
            val_lower = context.strip().lower()
            if val_lower.startswith("bearer ") or val_lower.startswith("basic "):
                return "[REDACTED]"
            return context
        return context

    @classmethod
    def validate_asset_context(cls, context: dict) -> dict:
        """Validate structure and sanitize asset context."""
        if not isinstance(context, dict):
            raise ValueError("Asset context must be a dictionary")
        return cls.sanitize_context(context)

    @classmethod
    def validate_finding_context(cls, context: dict) -> dict:
        """Validate structure and sanitize finding context."""
        if not isinstance(context, dict):
            raise ValueError("Finding context must be a dictionary")
        return cls.sanitize_context(context)

    @classmethod
    def validate_executive_context(cls, context: dict) -> dict:
        """Validate structure and sanitize executive context."""
        if not isinstance(context, dict):
            raise ValueError("Executive context must be a dictionary")
        return cls.sanitize_context(context)
