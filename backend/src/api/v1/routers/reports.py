import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.report import (
    AssetReportResponse,
    DashboardSummaryResponse,
    DashboardTrendResponse,
    ExecutiveReportResponse,
    ExposureReportResponse,
    FindingReportResponse,
    RiskReportResponse,
)
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import Asset, User, Workflow, WorkflowEvent
from src.infrastructure.database.session import get_db
from src.services.asset_report_service import AssetReportService
from src.services.dashboard_service import DashboardService
from src.services.dashboard_trend_service import DashboardTrendService
from src.services.executive_report_service import ExecutiveReportService
from src.services.export_service import ExportService
from src.services.exposure_report_service import ExposureReportService
from src.services.finding_report_service import FindingReportService
from src.services.risk_report_service import RiskReportService
from src.services.scope_service import get_scope_by_id

router = APIRouter(tags=["reports"])


async def check_asset_ownership(db: AsyncSession, asset: Asset, current_user: User):
    """Enforce ownership: non-admin users must own the scope containing the asset."""
    if current_user.role == "admin":
        return
    if not asset.scope_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this asset",
        )
    scope = await get_scope_by_id(db, asset.scope_id)
    if not scope or scope.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this asset",
        )


async def emit_report_event(
    db: AsyncSession,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """Helper to emit report.generated or export.generated workflow events

    without failing if no workflow is registered in the database yet.
    """
    # Find latest workflow to bind event to (workflow_id is non-nullable)
    q_wf = select(Workflow).order_by(Workflow.created_at.desc()).limit(1)
    res_wf = await db.execute(q_wf)
    wf = res_wf.scalar_one_or_none()

    if wf:
        event_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        full_payload = {
            "event_id": str(event_id),
            "correlation_id": None,
            "workflow_id": str(wf.id),
            "scan_run_id": None,
            "timestamp": now.isoformat(),
        }
        full_payload.update(payload)

        event = WorkflowEvent(
            id=event_id,
            workflow_id=wf.id,
            event_type=event_type,
            correlation_id=None,
            payload=full_payload,
            timestamp=now,
        )
        db.add(event)
        await db.commit()


@router.get(
    "/reports/executive", response_model=StandardResponse[ExecutiveReportResponse]
)
async def get_executive_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[ExecutiveReportResponse]:
    """Retrieve the platform-wide executive report."""
    report = await ExecutiveReportService.get_executive_report(db)
    await emit_report_event(db, "report.generated", {"report_type": "executive"})
    return StandardResponse(data=ExecutiveReportResponse(**report))


@router.get(
    "/reports/assets/{id}", response_model=StandardResponse[AssetReportResponse]
)
async def get_asset_report(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[AssetReportResponse]:
    """Retrieve detailed report for a specific asset with ownership check."""
    asset = await db.get(Asset, id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)

    report = await AssetReportService.generate_asset_report(db, id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset report could not be generated",
        )

    await emit_report_event(
        db, "report.generated", {"report_type": "asset", "asset_id": str(id)}
    )
    return StandardResponse(data=AssetReportResponse(**report))


@router.get("/reports/findings", response_model=StandardResponse[FindingReportResponse])
async def get_findings_report(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    template: Optional[str] = None,
    asset_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[FindingReportResponse]:
    """Retrieve filtered findings report with ownership checks applied."""
    # If a specific asset ID is requested, verify its ownership first
    if asset_id:
        asset = await db.get(Asset, asset_id)
        if not asset or asset.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
            )
        await check_asset_ownership(db, asset, current_user)

    report = await FindingReportService.generate_finding_report(
        db=db,
        severity=severity,
        status=status,
        template=template,
        asset_id=asset_id,
        user_role=current_user.role,
        user_id=current_user.id,
    )
    await emit_report_event(db, "report.generated", {"report_type": "findings"})
    return StandardResponse(data=FindingReportResponse(**report))


@router.get("/reports/risk", response_model=StandardResponse[RiskReportResponse])
async def get_risk_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[RiskReportResponse]:
    """Retrieve detailed risk intelligence report."""
    report = await RiskReportService.generate_risk_report(db)
    await emit_report_event(db, "report.generated", {"report_type": "risk"})
    return StandardResponse(data=RiskReportResponse(**report))


@router.get(
    "/reports/exposure", response_model=StandardResponse[ExposureReportResponse]
)
async def get_exposure_report(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[ExposureReportResponse]:
    """Retrieve asset distribution by exposure classification."""
    report = await ExposureReportService.generate_exposure_report(db)
    await emit_report_event(db, "report.generated", {"report_type": "exposure"})
    return StandardResponse(data=ExposureReportResponse(**report))


@router.get(
    "/dashboard/summary", response_model=StandardResponse[DashboardSummaryResponse]
)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[DashboardSummaryResponse]:
    """Retrieve platform-wide dashboard summary metrics."""
    summary = await DashboardService.get_dashboard_summary(db)
    return StandardResponse(data=DashboardSummaryResponse(**summary))


@router.get(
    "/dashboard/trends", response_model=StandardResponse[DashboardTrendResponse]
)
async def get_dashboard_trends(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[DashboardTrendResponse]:
    """Retrieve dashboard historical trends."""
    if days not in [7, 30, 90, 365]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid trend window days parameter",
        )
    try:
        trends = await DashboardTrendService.generate_trends(db, days)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    return StandardResponse(data=DashboardTrendResponse(window_days=days, **trends))


# --- Export Endpoints ---


@router.get("/reports/executive/export/json")
async def export_executive_json(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Download executive report in JSON format."""
    report = await ExecutiveReportService.get_executive_report(db)
    json_data = ExportService.export_executive_report_json(report)
    await emit_report_event(
        db, "export.generated", {"report_type": "executive", "format": "json"}
    )
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="executive_report.json"'},
    )


@router.get("/reports/executive/export/csv")
async def export_executive_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Download executive report in CSV format."""
    report = await ExecutiveReportService.get_executive_report(db)
    csv_data = ExportService.export_executive_report_csv(report)
    await emit_report_event(
        db, "export.generated", {"report_type": "executive", "format": "csv"}
    )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="executive_report.csv"'},
    )


@router.get("/reports/assets/{id}/export/json")
async def export_asset_json(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Download asset report in JSON format."""
    asset = await db.get(Asset, id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)

    report = await AssetReportService.generate_asset_report(db, id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset report could not be generated",
        )

    json_data = ExportService.export_asset_report_json(report)
    await emit_report_event(
        db,
        "export.generated",
        {"report_type": "asset", "asset_id": str(id), "format": "json"},
    )
    return Response(
        content=json_data,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="asset_report_{id}.json"'
        },
    )


@router.get("/reports/assets/{id}/export/csv")
async def export_asset_csv(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Download asset report in CSV format."""
    asset = await db.get(Asset, id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)

    report = await AssetReportService.generate_asset_report(db, id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset report could not be generated",
        )

    csv_data = ExportService.export_asset_report_csv(report)
    await emit_report_event(
        db,
        "export.generated",
        {"report_type": "asset", "asset_id": str(id), "format": "csv"},
    )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="asset_report_{id}.csv"'
        },
    )
