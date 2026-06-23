import time
import uuid
from typing import Dict, List


class AIRateLimitService:
    # In-memory dictionary mapping user ID string to list of request timestamps
    _request_logs: Dict[str, List[float]] = {}

    @classmethod
    def check_rate_limit(cls, user_id: uuid.UUID, role: str) -> bool:
        """Enforces sliding-window rate limit (1 hour) based on user role.

        Returns True if under limit (request allowed), False otherwise.
        """
        user_key = str(user_id)
        now = time.time()
        one_hour_ago = now - 3600.0

        # Define limits
        limits = {
            "admin": 1000,
            "operator": 250,
        }
        limit = limits.get(role.lower(), 0)

        # Get logs for user
        logs = cls._request_logs.get(user_key, [])

        # Filter out timestamps older than 1 hour
        logs = [ts for ts in logs if ts > one_hour_ago]

        if len(logs) >= limit:
            cls._request_logs[user_key] = logs  # Update logs list
            return False

        logs.append(now)
        cls._request_logs[user_key] = logs
        return True

    @classmethod
    def clear_limits(cls) -> None:
        """Clear logs primarily for testing purposes."""
        cls._request_logs.clear()
