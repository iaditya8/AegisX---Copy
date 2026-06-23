import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.recommendation import (
    InvestigationGuidanceResponse,
    PriorityRankingResponse,
    RecommendationResponse,
)
from src.infrastructure.database.models import Asset, Finding, User
from src.infrastructure.database.session import get_db
from src.services.investigation_assistance_service import InvestigationAssistanceService
from src.services.prioritization_service import PrioritizationService
from src.services.recommendation_service import RecommendationService
from src.services.scope_service import get_scope_by_id

router = APIRouter(tags=["recommendations"])


# --- Helper Scope Ownership Checks ---


async def check_asset_ownership(
    db: AsyncSession, asset: Asset, current_user: User
) -> None:
    """Enforce scope ownership check for non-admin operators."""
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


async def check_finding_ownership(
    db: AsyncSession, finding: Finding, current_user: User
) -> None:
    """Enforce scope ownership check for non-admin operators on finding."""
    if current_user.role == "admin":
        return
    asset = await db.get(Asset, finding.asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding asset not found",
        )
    await check_asset_ownership(db, asset, current_user)


# --- Endpoints ---


@router.get(
    "/recommendations/assets/{id}",
    response_model=List[RecommendationResponse],
)
async def get_asset_recommendations(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> List[RecommendationResponse]:
    """Retrieve recommendations for a specific asset."""
    asset = await db.get(Asset, id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )
    await check_asset_ownership(db, asset, current_user)
    return await RecommendationService.generate_asset_recommendations(db, id)


@router.get(
    "/recommendations/findings/{id}",
    response_model=List[RecommendationResponse],
)
async def get_finding_recommendations(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> List[RecommendationResponse]:
    """Retrieve recommendations for a specific finding."""
    finding = await db.get(Finding, id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found",
        )
    await check_finding_ownership(db, finding, current_user)
    return await RecommendationService.generate_finding_recommendations(db, id)


@router.get(
    "/recommendations/assets/{id}/guidance",
    response_model=InvestigationGuidanceResponse,
)
async def get_asset_guidance(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> InvestigationGuidanceResponse:
    """Retrieve structured guidance for investigating an asset."""
    asset = await db.get(Asset, id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )
    await check_asset_ownership(db, asset, current_user)
    return await InvestigationAssistanceService.generate_asset_guidance(db, id)


@router.get(
    "/recommendations/top-assets",
    response_model=List[PriorityRankingResponse],
)
async def get_top_assets(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> List[PriorityRankingResponse]:
    """Retrieve top assets prioritized by risk factors."""
    return await PrioritizationService.get_top_assets(db, limit=limit)


@router.get(
    "/recommendations/top-findings",
    response_model=List[PriorityRankingResponse],
)
async def get_top_findings(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> List[PriorityRankingResponse]:
    """Retrieve top findings prioritized by risk factors."""
    return await PrioritizationService.get_top_findings(db, limit=limit)


@router.get(
    "/recommendations/top-technologies",
    response_model=List[PriorityRankingResponse],
)
async def get_top_technologies(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> List[PriorityRankingResponse]:
    """Retrieve top technologies prioritized by risk factors."""
    return await PrioritizationService.get_top_technologies(db, limit=limit)


@router.get(
    "/recommendations/top-products",
    response_model=List[PriorityRankingResponse],
)
async def get_top_products(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> List[PriorityRankingResponse]:
    """Retrieve top products prioritized by risk factors."""
    return await PrioritizationService.get_top_products(db, limit=limit)
