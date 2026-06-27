from typing import Set


class AttackSurfaceRegistry:
    CATEGORIES = {
        "WEB_APPLICATION": "Web application target systems",
        "API": "Application programming interfaces",
        "HOST": "Operating system and host assets",
        "IDENTITY": "User roles and directories",
        "EMAIL": "E-mail servers and gateways",
        "CLOUD_RESOURCE": "Virtual machines and cloud stores",
        "NETWORK_SERVICE": "Exposed generic network services",
    }

    @classmethod
    def get_registered_categories(cls) -> Set[str]:
        """Retrieve all pre-seeded attack surface categories."""
        return set(cls.CATEGORIES.keys())

    @classmethod
    def is_valid_category(cls, category: str) -> bool:
        """Check if an attack surface category is registered."""
        return str(category).strip().upper() in cls.CATEGORIES
