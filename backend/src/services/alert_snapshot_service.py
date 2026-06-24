from typing import Dict, Optional


class AlertSnapshotService:
    _snapshot: Optional[Dict] = None

    @classmethod
    def invalidate_cache(cls) -> None:
        """Invalidate the in-memory snapshot cache."""
        cls._snapshot = None

    @classmethod
    def clear_snapshots(cls) -> None:
        """Clear the snapshot cache."""
        cls._snapshot = None

    @classmethod
    def generate_snapshot(cls) -> Dict:
        """Derive all alert metrics directly from active alert records."""
        from src.services.alert_lifecycle_service import AlertLifecycleService

        alerts = AlertLifecycleService.get_all_alerts()

        status_counts = {
            "OPEN": 0,
            "ACKNOWLEDGED": 0,
            "IN_PROGRESS": 0,
            "ESCALATED": 0,
            "RESOLVED": 0,
            "SUPPRESSED": 0,
        }
        severity_counts = {
            "LOW": 0,
            "MEDIUM": 0,
            "HIGH": 0,
            "CRITICAL": 0,
        }

        for alert in alerts:
            status_val = (
                alert.status.value
                if hasattr(alert.status, "value")
                else str(alert.status)
            )
            severity_val = (
                alert.severity.value
                if hasattr(alert.severity, "value")
                else str(alert.severity)
            )
            status_val = status_val.upper()
            severity_val = severity_val.upper()

            if status_val in status_counts:
                status_counts[status_val] += 1
            if severity_val in severity_counts:
                severity_counts[severity_val] += 1

        cls._snapshot = {
            "total_alerts": len(alerts),
            "status_counts": status_counts,
            "severity_counts": severity_counts,
        }
        return cls._snapshot

    @classmethod
    def get_snapshot(cls) -> Dict:
        """Retrieve the alert snapshot, rebuilding it if cache lookup fails."""
        if cls._snapshot is None:
            return cls.generate_snapshot()
        return cls._snapshot
