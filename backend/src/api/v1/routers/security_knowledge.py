import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.security_knowledge import (
    KnowledgeStatus,
    KnowledgeType,
    KnowledgeRecordResponse,
    KnowledgeRelationshipResponse,
    KnowledgeRecommendationResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.security_knowledge_service import SecurityKnowledgeService
from src.services.knowledge_history_service import KnowledgeHistoryService
from src.services.knowledge_type_registry import KnowledgeTypeRegistry
from src.services.knowledge_relationship_service import KnowledgeRelationshipService
from src.services.knowledge_recommendation_service import KnowledgeRecommendationService
from src.services.knowledge_snapshot_service import KnowledgeSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/security-knowledge", tags=["security-knowledge"])


class CreateKnowledgeRequest(BaseModel):
    title: str
    content: str
    knowledge_type: KnowledgeType
    tags: List[str]
    scope_id: Optional[uuid.UUID] = None


# --- Helper Checks ---

async def check_scope_ownership(
    db: AsyncSession, scope_id: uuid.UUID, current_user: User
) -> None:
    """Enforce scope ownership check for GRC knowledge access."""
    if current_user.role == "admin":
        return

    scope = await get_scope_by_id(db, scope_id)
    if not scope or scope.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scope not found",
        )

    if scope.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not own this scope",
        )


async def get_allowed_scope_ids(db: AsyncSession, current_user: User) -> set:
    """Retrieve all scope IDs owned by the current user."""
    if current_user.role == "admin":
        return set()

    q_scopes = select(Scope).where(
        Scope.owner_id == current_user.id, Scope.deleted_at.is_(None)
    )
    res_scopes = await db.execute(q_scopes)
    scopes = res_scopes.scalars().all()
    return {s.id for s in scopes}


# --- Endpoints ---

@router.get("", response_model=StandardResponse[List[KnowledgeRecordResponse]])
async def list_knowledge(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[KnowledgeRecordResponse]]:
    """List all knowledge records."""
    records = SecurityKnowledgeService.get_all_knowledge()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [SecurityKnowledgeService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/active", response_model=StandardResponse[List[KnowledgeRecordResponse]])
async def get_active_knowledge(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[KnowledgeRecordResponse]]:
    """List active GRC knowledge base records (non-archived)."""
    records = SecurityKnowledgeService.get_all_knowledge()
    records = [r for r in records if r.status != KnowledgeStatus.ARCHIVED]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [SecurityKnowledgeService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/relationships", response_model=StandardResponse[List[KnowledgeRelationshipResponse]])
async def get_relationships(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[KnowledgeRelationshipResponse]]:
    """Get all GRC knowledge relationships."""
    data = KnowledgeRelationshipService.get_relationships()
    return StandardResponse(data=data)


@router.get("/recommendations", response_model=StandardResponse[List[KnowledgeRecommendationResponse]])
async def get_recommendations(
    knowledge_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[KnowledgeRecommendationResponse]]:
    """Retrieve recommendations for a knowledge record."""
    record = SecurityKnowledgeService.get_knowledge(knowledge_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    data = KnowledgeRecommendationService.get_recommendations(knowledge_id, record.title)
    return StandardResponse(data=data)


@router.get("/drift", response_model=StandardResponse[Dict])
async def get_drift(
    current_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[Dict]:
    """Retrieve GRC knowledge drift summaries."""
    return StandardResponse(data={"drift_logs": []})


@router.get("/summary", response_model=StandardResponse[Dict])
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Get GRC knowledge dashboard summaries snapshot."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    snap = await KnowledgeSnapshotService.generate_snapshot(db, scope_id)
    return StandardResponse(data=snap)


@router.get("/{id}", response_model=StandardResponse[KnowledgeRecordResponse])
async def get_single_knowledge(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[KnowledgeRecordResponse]:
    """Get a single knowledge record."""
    record = SecurityKnowledgeService.get_knowledge(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    return StandardResponse(data=SecurityKnowledgeService.to_response(record))


@router.post("", response_model=StandardResponse[KnowledgeRecordResponse], status_code=status.HTTP_201_CREATED)
async def create_knowledge(
    req: CreateKnowledgeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[KnowledgeRecordResponse]:
    """Create a GRC knowledge record."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    record = await SecurityKnowledgeService.create_or_sync_knowledge(
        title=req.title,
        content=req.content,
        knowledge_type=req.knowledge_type,
        tags=req.tags,
        scope_id=req.scope_id,
    )
    data = SecurityKnowledgeService.to_response(record)
    return StandardResponse(data=data)


@router.post("/{id}/review", response_model=StandardResponse[KnowledgeRecordResponse])
async def review_knowledge(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[KnowledgeRecordResponse]:
    """Transition knowledge status to REVIEW."""
    record = SecurityKnowledgeService.get_knowledge(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == KnowledgeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of an archived GRC knowledge record",
        )

    res = SecurityKnowledgeService.transition_status(id, KnowledgeStatus.REVIEW)
    return StandardResponse(data=SecurityKnowledgeService.to_response(res))


@router.post("/{id}/approve", response_model=StandardResponse[KnowledgeRecordResponse])
async def approve_knowledge(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[KnowledgeRecordResponse]:
    """Transition knowledge status to APPROVED."""
    record = SecurityKnowledgeService.get_knowledge(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == KnowledgeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of an archived GRC knowledge record",
        )

    res = SecurityKnowledgeService.transition_status(id, KnowledgeStatus.APPROVED)
    return StandardResponse(data=SecurityKnowledgeService.to_response(res))


@router.post("/{id}/archive", response_model=StandardResponse[KnowledgeRecordResponse])
async def archive_knowledge(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[KnowledgeRecordResponse]:
    """Transition knowledge status to ARCHIVED."""
    record = SecurityKnowledgeService.get_knowledge(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge record not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == KnowledgeStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of an archived GRC knowledge record",
        )

    res = SecurityKnowledgeService.transition_status(id, KnowledgeStatus.ARCHIVED)
    return StandardResponse(data=SecurityKnowledgeService.to_response(res))
