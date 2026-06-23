from abc import ABC, abstractmethod


class BasePlugin(ABC):
    @abstractmethod
    def initialize(self) -> bool:
        """Perform self-checks, initialize connections/dependencies.
        Must not execute plugin business logic.
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate settings, configuration parameters, and inputs.
        Must not execute plugin business logic.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check system environment and verify tools availability.
        Must not execute plugin business logic.
        """
        pass

    @abstractmethod
    def run(self, payload: dict) -> dict:
        """Run the plugin's main execution task with the payload and return results."""
        pass
