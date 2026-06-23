import subprocess
import time
from typing import Any, Dict, List, Optional

from src.plugins.host import PluginExecutionError


class ToolExecutionConfig:
    def __init__(
        self,
        timeout: int,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        retries: int = 0,
        retry_delay: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.timeout = timeout
        self.args = args or []
        self.env = env or {}
        self.retries = retries
        self.retry_delay = retry_delay
        self.metadata = metadata or {}


class ToolExecutor:
    @staticmethod
    def execute(
        cmd: List[str], config: ToolExecutionConfig
    ) -> subprocess.CompletedProcess:
        attempts = 0
        max_attempts = config.retries + 1
        last_error = None

        while attempts < max_attempts:
            attempts += 1
            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=config.timeout,
                    env=config.env or None,
                )
                if res.returncode != 0:
                    raise PluginExecutionError(
                        f"Tool execution failed with code {res.returncode}. "
                        f"Stderr: {res.stderr}"
                    )
                return res
            except subprocess.TimeoutExpired as e:
                last_error = PluginExecutionError(f"Tool execution timed out: {str(e)}")
            except Exception as e:
                # If it's already a PluginExecutionError from return code check, catch it here
                if isinstance(e, PluginExecutionError):
                    last_error = e
                else:
                    last_error = PluginExecutionError(
                        f"Tool subprocess execution error: {str(e)}"
                    )

            if attempts < max_attempts and config.retry_delay > 0:
                time.sleep(config.retry_delay)

        raise last_error
