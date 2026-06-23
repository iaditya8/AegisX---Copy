import json
from typing import Any, Dict

from src.plugins.base import BasePlugin
from src.plugins.executor import ToolExecutionConfig, ToolExecutor


class NmapPlugin(BasePlugin):
    """Nmap Plugin for Service Enumeration.
    Executes nmap -sV -oX - to identify services and versions. No persistence.
    """

    def initialize(self) -> bool:
        return True

    def validate(self) -> bool:
        return True

    def health_check(self) -> bool:
        # Check if nmap is installed
        try:
            config = ToolExecutionConfig(timeout=10, retries=0)
            res = ToolExecutor.execute(["nmap", "-V"], config)
            return "nmap" in res.stdout.lower()
        except Exception:
            return False

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute nmap on given targets."""
        config_data = payload.get("config", {})
        timeout = config_data.get("timeout", 600)
        retries = config_data.get("retries", 2)
        retry_delay = config_data.get("retry_delay", 5)

        targets = []
        definition = payload.get("definition", {})
        targets.extend(definition.get("domains", []))
        targets.extend(definition.get("ips", []))

        results = {}
        for target in targets:
            # -sV for version detection, -oX - for XML output to stdout
            cmd = ["nmap", "-sV", "-oX", "-", target]

            exec_config = ToolExecutionConfig(
                timeout=timeout,
                retries=retries,
                retry_delay=retry_delay,
            )

            res = ToolExecutor.execute(cmd, exec_config)
            results[target] = res.stdout

        return {"raw_output": json.dumps(results)}
