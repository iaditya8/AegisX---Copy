import asyncio

from src.plugins.base import BasePlugin


class MockDiscoveryPlugin(BasePlugin):
    # Used to track if run() was called (validation must NOT call run)
    run_called = False

    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    def run(self, payload: dict) -> dict:
        MockDiscoveryPlugin.run_called = True
        return {"status": "success", "discovered_hosts": ["10.0.0.1", "10.0.0.2"]}


class MockFailingPlugin(BasePlugin):
    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    def run(self, payload: dict) -> dict:
        raise ValueError("Simulated tool crash during plugin execution")


class MockTimeoutPlugin(BasePlugin):
    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    async def run(self, payload: dict) -> dict:
        # Long running task to exceed timeout
        await asyncio.sleep(5.0)
        return {"status": "completed"}


class MockInvalidPlugin:
    # Does not subclass BasePlugin and is missing initialize/validate/health_check/run
    pass
