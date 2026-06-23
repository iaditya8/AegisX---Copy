import asyncio
import importlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Type

from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.database.models import PluginEvent
from src.plugins.base import BasePlugin


class PluginExecutionError(Exception):
    """Raised when plugin execution encounters a runtime exception or timeout."""

    pass


class PluginValidationError(Exception):
    """Raised when a plugin fails validation.

    Fails during manifest check, dynamic loading, or method verification.
    """

    pass


class PluginHost:
    @staticmethod
    def load_plugin_class(entry_point: str) -> Type[BasePlugin]:
        """Dynamically load the plugin class using importlib."""
        try:
            if ":" not in entry_point:
                raise PluginValidationError(
                    "Entry point must be in format 'module.path:ClassName'"
                )
            module_path, class_name = entry_point.split(":")
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            return plugin_class
        except (ImportError, AttributeError, ValueError) as e:
            raise PluginValidationError(
                f"Failed to load entry point '{entry_point}': {str(e)}"
            )

    @staticmethod
    def verify_interface(plugin_class: Type[Any]) -> bool:
        """Verify that the plugin class implements required BasePlugin methods."""
        required_methods = ["initialize", "validate", "health_check", "run"]
        for method in required_methods:
            if not hasattr(plugin_class, method) or not callable(
                getattr(plugin_class, method)
            ):
                return False
        return True

    @classmethod
    def validate_plugin(cls, entry_point: str, manifest: Dict[str, Any]) -> bool:
        """Validate the plugin manifest, load the class, verify the interface,
        and optionally run initialize() and health_check().
        MUST NOT call run().
        """
        # Validate manifest schema requirements
        required_keys = [
            "name",
            "version",
            "entry_point",
            "capabilities",
            "permissions",
            "timeout",
        ]
        for key in required_keys:
            if key not in manifest:
                raise PluginValidationError(f"Missing required manifest field: {key}")

        timeout = manifest.get("timeout")
        if not isinstance(timeout, int) or timeout <= 0:
            raise PluginValidationError(
                "Invalid timeout value: must be a positive integer"
            )

        if (
            not isinstance(manifest.get("capabilities"), list)
            or len(manifest.get("capabilities")) == 0
        ):
            raise PluginValidationError(
                "Invalid capabilities: must be a non-empty list of strings"
            )

        if not isinstance(manifest.get("permissions"), list):
            raise PluginValidationError(
                "Invalid permissions: must be a list of strings"
            )

        # Load class
        plugin_class = cls.load_plugin_class(entry_point)

        # Verify interface
        if not cls.verify_interface(plugin_class):
            raise PluginValidationError(
                "Plugin does not implement standard BasePlugin interface methods"
            )

        # Instantiate
        try:
            plugin_instance = plugin_class()
        except Exception as e:
            raise PluginValidationError(f"Failed to instantiate plugin: {str(e)}")

        # Call initialize and health_check
        try:
            init_success = plugin_instance.initialize()
            if not init_success:
                raise PluginValidationError("Plugin initialize() returned False")
        except Exception as e:
            raise PluginValidationError(f"Plugin initialize() crashed: {str(e)}")

        try:
            health_success = plugin_instance.health_check()
            if not health_success:
                raise PluginValidationError("Plugin health_check() returned False")
        except Exception as e:
            raise PluginValidationError(f"Plugin health_check() crashed: {str(e)}")

        return True

    @classmethod
    async def run_plugin(
        cls,
        db: AsyncSession,
        plugin_id: uuid.UUID,
        entry_point: str,
        payload: Dict[str, Any],
        timeout: int,
        correlation_id: Optional[uuid.UUID] = None,
        workflow_id: Optional[uuid.UUID] = None,
        scan_run_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Instantiate and run the plugin with the payload.

        Enforces timeouts, execution boundaries, and records logs.
        """

        # Extension point for OS-level seccomp/namespace/container sandboxing
        cls._apply_sandbox_constraints()

        # Extension point for CPU/RAM/Resource controls
        cls._apply_resource_limits()

        # Log plugin.started
        await cls.log_event(
            db,
            plugin_id,
            "plugin.started",
            correlation_id,
            workflow_id,
            scan_run_id,
        )

        try:
            plugin_class = cls.load_plugin_class(entry_point)
            if not cls.verify_interface(plugin_class):
                raise PluginExecutionError(
                    "Plugin does not implement standard interface"
                )

            plugin_instance = plugin_class()

            # Execute run method with timeout enforcement
            run_func = plugin_instance.run
            if asyncio.iscoroutinefunction(run_func):
                run_coro = run_func(payload)
            else:
                loop = asyncio.get_running_loop()
                run_coro = loop.run_in_executor(None, run_func, payload)

            result = await asyncio.wait_for(run_coro, timeout=timeout)

            # Log plugin.completed
            await cls.log_event(
                db,
                plugin_id,
                "plugin.completed",
                correlation_id,
                workflow_id,
                scan_run_id,
                payload={
                    "result_keys": (
                        list(result.keys()) if isinstance(result, dict) else []
                    )
                },
            )
            return result

        except asyncio.TimeoutError as e:
            error_msg = f"Plugin execution timed out after {timeout} seconds"
            await cls.log_event(
                db,
                plugin_id,
                "plugin.failed",
                correlation_id,
                workflow_id,
                scan_run_id,
                payload={"error": error_msg},
            )
            raise PluginExecutionError(error_msg) from e
        except Exception as e:
            error_msg = f"Plugin execution failed with exception: {str(e)}"
            await cls.log_event(
                db,
                plugin_id,
                "plugin.failed",
                correlation_id,
                workflow_id,
                scan_run_id,
                payload={"error": error_msg},
            )
            raise PluginExecutionError(error_msg) from e

    @staticmethod
    async def log_event(
        db: AsyncSession,
        plugin_id: uuid.UUID,
        event_type: str,
        correlation_id: Optional[uuid.UUID] = None,
        workflow_id: Optional[uuid.UUID] = None,
        scan_run_id: Optional[uuid.UUID] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> PluginEvent:
        """Create and persist a plugin event log."""
        db_evt = PluginEvent(
            plugin_id=plugin_id,
            event_type=event_type,
            correlation_id=correlation_id,
            workflow_id=workflow_id,
            scan_run_id=scan_run_id,
            payload=payload or {},
            timestamp=datetime.now(timezone.utc),
        )
        db.add(db_evt)
        await db.commit()
        await db.refresh(db_evt)
        return db_evt

    @staticmethod
    def _apply_sandbox_constraints() -> None:
        """Extension point for future sandbox implementation (e.g. seccomp, Docker)."""
        pass

    @staticmethod
    def _apply_resource_limits() -> None:
        """Extension point for future CPU, RAM, and other hardware resource limits."""
        pass
