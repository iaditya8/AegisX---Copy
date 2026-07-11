import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.correlation import CorrelationResponse, RiskResponse
from src.domain.entities.user import StandardResponse
from src.infrastructure.database.models import User
from src.infrastructure.database.session import get_db
from src.services.asset_risk_snapshot_service import AssetRiskSnapshotService
from src.services.asset_service import get_asset_by_id
from src.services.correlation_snapshot_service import CorrelationSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/assets", tags=["correlations"])


async def check_asset_ownership(db: AsyncSession, asset, current_user: User):
    """Verify that a non-admin user owns the scope containing the asset."""
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


@router.get("/{id}/correlation", response_model=StandardResponse[CorrelationResponse])
async def get_asset_correlation(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[CorrelationResponse]:
    """Retrieve details of a specific asset's correlation snapshot."""
    asset = await get_asset_by_id(db, id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)

    # Retrieve from cache or generate on demand if not cached
    snapshot = CorrelationSnapshotService.get_snapshot(id)
    if snapshot.get("exposure") == "UNKNOWN" and not snapshot.get("ports"):
        snapshot = await CorrelationSnapshotService.generate_snapshot(db, id)

    return StandardResponse(data=CorrelationResponse(**snapshot))


@router.get("/{id}/risk", response_model=StandardResponse[RiskResponse])
async def get_asset_risk_details(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[RiskResponse]:
    """Retrieve computed risk context and exposure details for the asset."""
    asset = await get_asset_by_id(db, id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    await check_asset_ownership(db, asset, current_user)

    # Retrieve from cache or generate on demand if not cached
    snapshot = AssetRiskSnapshotService.get_snapshot(id)
    if snapshot.get("exposure") == "UNKNOWN" and snapshot.get("risk_score") == 0:
        snapshot = await AssetRiskSnapshotService.generate_snapshot(db, id)

    return StandardResponse(data=RiskResponse(**snapshot))


# ==============================================================================
# UNIFIED CORRELATION ENGINE V1 ENDPOINTS
# ==============================================================================

from fastapi import APIRouter
from src.domain.entities.correlation import (
    CorrelationRuleCreate,
    CorrelationRuleResponse,
    CorrelationClusterResponse,
    CorrelationClusterSignalResponse,
    CorrelationHistoryResponse,
    ClusterEscalateRequest,
)
from src.services.correlation_service import CorrelationService
from typing import List, Optional

router2 = APIRouter(prefix="/correlations", tags=["correlations"])

@router2.post("/rules", response_model=StandardResponse[CorrelationRuleResponse])
async def create_rule(
    body: CorrelationRuleCreate,
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[CorrelationRuleResponse]:
    """Create a new Correlation Rule."""
    rule = await CorrelationService.create_rule(
        name=body.name,
        description=body.description,
        condition_expression=body.condition_expression,
        priority_level=body.priority_level,
    )
    return StandardResponse(data=CorrelationRuleResponse.model_validate(rule))


@router2.get("/rules", response_model=StandardResponse[List[CorrelationRuleResponse]])
async def list_rules(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[CorrelationRuleResponse]]:
    """List all active Correlation Rules."""
    rules = await CorrelationService.list_rules()
    return StandardResponse(data=[CorrelationRuleResponse.model_validate(r) for r in rules])


@router2.get("/rules/{rule_id}", response_model=StandardResponse[CorrelationRuleResponse])
async def get_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[CorrelationRuleResponse]:
    """Get a specific Correlation Rule."""
    rule = await CorrelationService.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return StandardResponse(data=CorrelationRuleResponse.model_validate(rule))


@router2.get("/clusters", response_model=StandardResponse[List[CorrelationClusterResponse]])
async def list_clusters(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[CorrelationClusterResponse]]:
    """List all Correlation Clusters sorted by unified priority score descending."""
    clusters = await CorrelationService.list_clusters()
    data = []
    for c in clusters:
        signals = [CorrelationClusterSignalResponse.model_validate(s) for s in c.signals]
        history = [CorrelationHistoryResponse.model_validate(h) for h in c.history]
        data.append(
            CorrelationClusterResponse(
                id=c.id,
                asset_id=c.asset_id,
                unified_score=c.unified_score,
                score_breakdown_json=c.score_breakdown_json,
                status=c.status,
                fingerprint=c.fingerprint,
                associated_incident_id=c.associated_incident_id,
                signals=signals,
                history=history,
            )
        )
    return StandardResponse(data=data)


@router2.get("/clusters/{cluster_id}", response_model=StandardResponse[CorrelationClusterResponse])
async def get_cluster(
    cluster_id: uuid.UUID,
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[CorrelationClusterResponse]:
    """Fetch detailed Correlation Cluster including signals list and history trail."""
    c = await CorrelationService.get_cluster(cluster_id)
    if not c:
        raise HTTPException(status_code=404, detail="Cluster not found")
    signals = [CorrelationClusterSignalResponse.model_validate(s) for s in c.signals]
    history = [CorrelationHistoryResponse.model_validate(h) for h in c.history]
    return StandardResponse(
        data=CorrelationClusterResponse(
            id=c.id,
            asset_id=c.asset_id,
            unified_score=c.unified_score,
            score_breakdown_json=c.score_breakdown_json,
            status=c.status,
            fingerprint=c.fingerprint,
            associated_incident_id=c.associated_incident_id,
            signals=signals,
            history=history,
        )
    )


@router2.get("/clusters/{cluster_id}/provenance", response_model=StandardResponse[List[dict]])
async def get_cluster_provenance(
    cluster_id: uuid.UUID,
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[dict]]:
    """Eagerly loaded details of matching rules and evidence behind the cluster score."""
    from src.infrastructure.database.unit_of_work import UnitOfWork
    async with UnitOfWork() as uow:
        matches = await uow.correlation_repo.list_rule_matches_for_cluster(cluster_id)
        provenance = []
        for m in matches:
            rule = await uow.correlation_repo.get_rule(m.rule_id)
            provenance.append({
                "match_id": str(m.id),
                "rule_id": str(m.rule_id),
                "rule_name": rule.name if rule else "Unknown Rule",
                "rule_version_used": m.rule_version_used,
                "confidence": m.confidence,
                "evidence": m.evidence_json,
                "matched_at": m.matched_at.isoformat() if m.matched_at else None
            })
        return StandardResponse(data=provenance)


@router2.post("/clusters/{cluster_id}/escalate", response_model=StandardResponse[dict])
async def escalate_cluster(
    cluster_id: uuid.UUID,
    body: Optional[ClusterEscalateRequest] = None,
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[dict]:
    """Escalate the cluster into a formal incident using the CorrelationIncidentBridge."""
    title = body.incident_title if body else None
    description = body.incident_description if body else None
    incident = await CorrelationService.escalate_cluster(
        cluster_id=cluster_id,
        title=title,
        description=description,
    )
    return StandardResponse(data={"incident_id": str(incident.id)})
