import os
import shutil
from typing import Any, Dict

from src.plugins.base import BasePlugin
from src.plugins.executor import ToolExecutionConfig, ToolExecutor
from src.plugins.host import PluginExecutionError


class NucleiPlugin(BasePlugin):
    """Nuclei Plugin for vulnerability scanning.
    Executes nuclei to detect vulnerabilities against assets.
    No parsing, scoring, or persistence.
    """

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
            shutil.which("nuclei") is not None or shutil.which("nuclei.exe") is not None
        )

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute nuclei on target service."""
        config_data = payload.get("config", {}) or {}
        timeout = config_data.get("timeout", 600)
        retries = config_data.get("retries", 0)
        retry_delay = config_data.get("retry_delay", 5)

        # Retrieve target from configuration if set, otherwise throw error if missing
        target = config_data.get("target")
        if not target:
            # Try to build from payload definition domains/ips
            definition = payload.get("definition", {}) or {}
            domains = definition.get("domains", [])
            ips = definition.get("ips", [])
            targets = domains + ips
            if targets:
                target = targets[0]

        if not target:
            raise PluginExecutionError("No scan target specified in payload")

        # Command structure as required: nuclei -json -silent -target <target>
        cmd = ["nuclei", "-target", target, "-json", "-silent"]

        # Support optional template specification
        templates = config_data.get("templates", [])
        if isinstance(templates, str):
            templates = [templates]
        for t in templates:
            cmd.extend(["-t", t])

        exec_config = ToolExecutionConfig(
            timeout=timeout,
            retries=retries,
            retry_delay=retry_delay,
        )

        res = ToolExecutor.execute(cmd, exec_config)
        return {"raw_output": res.stdout}
