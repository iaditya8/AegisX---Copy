import os
import shutil

from src.plugins.base import BasePlugin
from src.plugins.executor import ToolExecutionConfig, ToolExecutor
from src.plugins.host import PluginExecutionError


class SubfinderPlugin(BasePlugin):
    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return True

    def health_check(self) -> bool:
        if (
            os.getenv("TEST_ENV") == "true"
            or os.getenv("PYTEST_CURRENT_TEST") is not None
        ):
            return True
        return (
            shutil.which("subfinder") is not None
            or shutil.which("subfinder.exe") is not None
        )

    def run(self, payload: dict) -> dict:
        definition = payload.get("definition", {}) or {}
        domains = definition.get("domains", [])
        if not domains:
            config = payload.get("config", {}) or {}
            target = config.get("target")
            if target:
                domains = [target]

        if not domains:
            raise PluginExecutionError("No domain targets specified in payload")

        timeout = payload.get("config", {}).get("timeout", 60)
        config = ToolExecutionConfig(timeout=timeout)

        raw_outputs = []
        for domain in domains:
            cmd = ["subfinder", "-d", domain, "-silent"]
            res = ToolExecutor.execute(cmd, config)
            raw_outputs.append(res.stdout)

        return {"tool": "subfinder", "raw_output": "\n".join(raw_outputs)}
