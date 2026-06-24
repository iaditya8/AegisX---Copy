import json
import uuid
from typing import Any, Dict, Optional


class BaselineStateService:
    _asset_baselines: Dict[uuid.UUID, Dict[str, Any]] = {}
    _finding_baselines: Dict[uuid.UUID, Dict[str, Any]] = {}
    _risk_baselines: Dict[uuid.UUID, float] = {}
    _governance_baselines: Dict[uuid.UUID, str] = {}

    @classmethod
    def clear_baselines(cls) -> None:
        """Clear all in-memory baseline caches."""
        cls._asset_baselines.clear()
        cls._finding_baselines.clear()
        cls._risk_baselines.clear()
        cls._governance_baselines.clear()

    @classmethod
    def capture_asset_baseline(cls, asset_id: uuid.UUID, data: Dict[str, Any]) -> None:
        """Cache baseline details for a specific asset."""
        cls._asset_baselines[asset_id] = data

    @classmethod
    def get_asset_baseline(cls, asset_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Retrieve baseline for a specific asset. Rebuilds if not cached."""
        if asset_id not in cls._asset_baselines:
            cls.rebuild_baselines_from_history(asset_id=asset_id)
        return cls._asset_baselines.get(asset_id)

    @classmethod
    def capture_finding_baseline(
        cls, finding_id: uuid.UUID, data: Dict[str, Any]
    ) -> None:
        """Cache baseline details for a specific finding."""
        cls._finding_baselines[finding_id] = data

    @classmethod
    def get_finding_baseline(cls, finding_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Retrieve baseline for a specific finding. Rebuilds if not cached."""
        if finding_id not in cls._finding_baselines:
            cls.rebuild_baselines_from_history(finding_id=finding_id)
        return cls._finding_baselines.get(finding_id)

    @classmethod
    def capture_risk_baseline(cls, asset_id: uuid.UUID, risk_score: float) -> None:
        """Cache risk baseline for a specific asset."""
        cls._risk_baselines[asset_id] = risk_score

    @classmethod
    def get_risk_baseline(cls, asset_id: uuid.UUID) -> Optional[float]:
        """Retrieve risk baseline for a specific asset. Rebuilds if not cached."""
        if asset_id not in cls._risk_baselines:
            cls.rebuild_baselines_from_history(asset_id=asset_id)
        return cls._risk_baselines.get(asset_id)

    @classmethod
    def capture_governance_baseline(
        cls, asset_id: uuid.UUID, governance_status: str
    ) -> None:
        """Cache governance baseline status for a specific asset."""
        cls._governance_baselines[asset_id] = governance_status

    @classmethod
    def get_governance_baseline(cls, asset_id: uuid.UUID) -> Optional[str]:
        """Retrieve governance baseline status for a specific asset. Rebuilds if not cached."""
        if asset_id not in cls._governance_baselines:
            cls.rebuild_baselines_from_history(asset_id=asset_id)
        return cls._governance_baselines.get(asset_id)

    @classmethod
    def rebuild_baselines_from_history(
        cls,
        asset_id: Optional[uuid.UUID] = None,
        finding_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Reconstruct caches dynamically by traversing past monitoring events history."""
        from src.services.continuous_refresh_service import ContinuousRefreshService

        events = ContinuousRefreshService.get_all_events()

        for event in events:
            # Asset Rebuild
            if asset_id and event.asset_id == asset_id and not event.finding_id:
                if event.change_type == "ASSET_REMOVED":
                    cls._asset_baselines.pop(asset_id, None)
                elif event.change_type in ["ASSET_ADDED", "ASSET_MODIFIED"]:
                    if event.current_state:
                        try:
                            cls._asset_baselines[asset_id] = json.loads(
                                event.current_state
                            )
                        except Exception:
                            pass

            # Finding Rebuild
            if finding_id and event.finding_id == finding_id:
                if event.change_type in [
                    "FINDING_ADDED",
                    "FINDING_RESOLVED",
                    "FINDING_REDISCOVERED",
                    "FINDING_MODIFIED",
                ]:
                    if event.current_state:
                        try:
                            cls._finding_baselines[finding_id] = json.loads(
                                event.current_state
                            )
                        except Exception:
                            pass

            # Risk Rebuild
            if (
                asset_id
                and event.asset_id == asset_id
                and event.change_type
                in ["RISK_INCREASED", "RISK_DECREASED", "RISK_DRIFT"]
            ):
                if event.current_state:
                    try:
                        cls._risk_baselines[asset_id] = float(event.current_state)
                    except Exception:
                        pass

            # Governance Rebuild
            if (
                asset_id
                and event.asset_id == asset_id
                and event.change_type
                in [
                    "COMPLIANCE_FAILED",
                    "COMPLIANCE_RESTORED",
                    "RISK_ACCEPTANCE_EXPIRED",
                    "GOVERNANCE_DRIFT",
                ]
            ):
                if event.current_state:
                    cls._governance_baselines[asset_id] = event.current_state
