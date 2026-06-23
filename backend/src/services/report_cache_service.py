import uuid


class ReportCacheService:
    """Service to centralize and cascade report cache invalidations."""

    @classmethod
    def invalidate_dashboard_cache(cls) -> None:
        """Clear Dashboard cache."""
        from src.services.dashboard_service import DashboardService

        DashboardService.clear_cache()

    @classmethod
    def invalidate_executive_cache(cls) -> None:
        """Clear Executive Report cache."""
        from src.services.ai_cache_service import AICacheService
        from src.services.executive_report_service import ExecutiveReportService

        ExecutiveReportService.clear_cache()
        AICacheService.invalidate_for_asset("executive")

    @classmethod
    def invalidate_asset_report_cache(cls, asset_id: uuid.UUID) -> None:
        """Clear cached Asset report for the given asset."""
        from src.services.asset_report_service import AssetReportService

        if hasattr(AssetReportService, "_cache"):
            AssetReportService._cache.pop(asset_id, None)
            AssetReportService._cache.pop(str(asset_id), None)
            try:
                AssetReportService._cache.pop(uuid.UUID(str(asset_id)), None)
            except Exception:
                pass

    @classmethod
    def invalidate_for_asset(cls, asset_id: uuid.UUID) -> None:
        """Cascades invalidation for all report caches associated with the asset."""
        cls.invalidate_dashboard_cache()
        cls.invalidate_executive_cache()
        cls.invalidate_asset_report_cache(asset_id)
        from src.services.ai_cache_service import AICacheService

        AICacheService.invalidate_for_asset(asset_id)

    @classmethod
    def invalidate_all(cls) -> None:
        """Clear all report caches."""
        cls.invalidate_dashboard_cache()
        cls.invalidate_executive_cache()
        from src.services.ai_cache_service import AICacheService
        from src.services.asset_report_service import AssetReportService

        if hasattr(AssetReportService, "_cache"):
            AssetReportService._cache.clear()
        AICacheService.invalidate_all()
