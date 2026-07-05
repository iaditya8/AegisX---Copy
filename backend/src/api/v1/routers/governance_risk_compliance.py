import uuid
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.user import StandardResponse
from src.domain.entities.governance_risk_compliance import (
    ComplianceStatus,
    FrameworkType,
    ComplianceAssessmentResponse,
    ComplianceEvidenceResponse,
    ComplianceGapResponse,
)
from src.infrastructure.database.models import Scope, User
from src.infrastructure.database.session import get_db
from src.services.governance_risk_compliance_service import GovernanceRiskComplianceService
from src.services.compliance_history_service import ComplianceHistoryService
from src.services.compliance_framework_registry import ComplianceFrameworkRegistry
from src.services.compliance_gap_service import ComplianceGapService
from src.services.control_mapping_registry import ControlMappingRegistry
from src.services.compliance_snapshot_service import ComplianceSnapshotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/governance-risk-compliance", tags=["governance-risk-compliance"])


class CreateAssessmentRequest(BaseModel):
    name: str
    description: str
    framework_type: FrameworkType
    scope_id: Optional[uuid.UUID] = None


class UploadEvidenceRequest(BaseModel):
    file_name: str
    file_hash: str


# --- Helper Checks ---

async def check_scope_ownership(
    db: AsyncSession, scope_id: uuid.UUID, current_user: User
) -> None:
    """Enforce scope ownership check for non-admin users."""
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

@router.get("", response_model=StandardResponse[List[ComplianceAssessmentResponse]])
async def list_assessments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ComplianceAssessmentResponse]]:
    """List all compliance assessments."""
    records = await GovernanceRiskComplianceService.get_all_assessments()

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [GovernanceRiskComplianceService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/active", response_model=StandardResponse[List[ComplianceAssessmentResponse]])
async def get_active_assessments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ComplianceAssessmentResponse]]:
    """List active compliance assessments (non-closed)."""
    records = await GovernanceRiskComplianceService.get_all_assessments()
    records = [r for r in records if r.status != ComplianceStatus.CLOSED]

    if current_user.role != "admin":
        allowed_scopes = await get_allowed_scope_ids(db, current_user)
        records = [r for r in records if r.scope_id is None or r.scope_id in allowed_scopes]

    data = [GovernanceRiskComplianceService.to_response(r) for r in records]
    return StandardResponse(data=data)


@router.get("/frameworks", response_model=StandardResponse[List[str]])
async def get_frameworks(
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[str]]:
    """List supported GRC frameworks."""
    data = list(ComplianceFrameworkRegistry.list_frameworks())
    return StandardResponse(data=data)


@router.get("/gaps", response_model=StandardResponse[List[ComplianceGapResponse]])
async def get_gaps(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[List[ComplianceGapResponse]]:
    """Retrieve compliance gap log for an assessment."""
    record = await GovernanceRiskComplianceService.get_assessment(assessment_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    controls = ControlMappingRegistry.get_controls(record.framework_type)
    data = ComplianceGapService.get_gaps(assessment_id, len(controls), len(record.evidence_list))
    return StandardResponse(data=data)


@router.get("/drift", response_model=StandardResponse[Dict])
async def get_drift(
    current_user: User = Depends(RoleChecker(["admin"])),
) -> StandardResponse[Dict]:
    """Retrieve GRC compliance drift summary logs."""
    return StandardResponse(data={"drift_logs": []})


@router.get("/summary", response_model=StandardResponse[Dict])
async def get_summary(
    scope_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[Dict]:
    """Get GRC dashboard summary metrics."""
    if scope_id:
        await check_scope_ownership(db, scope_id, current_user)
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Non-admin users must specify scope_id",
            )
    snap = await ComplianceSnapshotService.generate_snapshot(db, scope_id)
    return StandardResponse(data=snap)


@router.get("/{id}", response_model=StandardResponse[ComplianceAssessmentResponse])
async def get_single_assessment(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
) -> StandardResponse[ComplianceAssessmentResponse]:
    """Get a single compliance assessment."""
    record = await GovernanceRiskComplianceService.get_assessment(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    return StandardResponse(data=GovernanceRiskComplianceService.to_response(record))


@router.post("", response_model=StandardResponse[ComplianceAssessmentResponse], status_code=status.HTTP_201_CREATED)
async def create_assessment(
    req: CreateAssessmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ComplianceAssessmentResponse]:
    """Create a GRC compliance assessment."""
    if req.scope_id:
        await check_scope_ownership(db, req.scope_id, current_user)

    record = await GovernanceRiskComplianceService.create_or_sync_assessment(
        name=req.name,
        description=req.description,
        framework_type=req.framework_type,
        scope_id=req.scope_id,
    )
    data = GovernanceRiskComplianceService.to_response(record)
    return StandardResponse(data=data)


@router.post("/{id}/review", response_model=StandardResponse[ComplianceAssessmentResponse])
async def review_assessment(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ComplianceAssessmentResponse]:
    """Transition assessment status to IN_REVIEW."""
    record = await GovernanceRiskComplianceService.get_assessment(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == ComplianceStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a closed GRC assessment",
        )

    res = await GovernanceRiskComplianceService.transition_status(id, ComplianceStatus.IN_REVIEW)
    return StandardResponse(data=GovernanceRiskComplianceService.to_response(res))


@router.post("/{id}/compliant", response_model=StandardResponse[ComplianceAssessmentResponse])
async def compliant_assessment(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ComplianceAssessmentResponse]:
    """Transition assessment status to COMPLIANT."""
    record = await GovernanceRiskComplianceService.get_assessment(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == ComplianceStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a closed GRC assessment",
        )

    res = await GovernanceRiskComplianceService.transition_status(id, ComplianceStatus.COMPLIANT)
    return StandardResponse(data=GovernanceRiskComplianceService.to_response(res))


@router.post("/{id}/non-compliant", response_model=StandardResponse[ComplianceAssessmentResponse])
async def non_compliant_assessment(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ComplianceAssessmentResponse]:
    """Transition assessment status to NON_COMPLIANT."""
    record = await GovernanceRiskComplianceService.get_assessment(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == ComplianceStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a closed GRC assessment",
        )

    res = await GovernanceRiskComplianceService.transition_status(id, ComplianceStatus.NON_COMPLIANT)
    return StandardResponse(data=GovernanceRiskComplianceService.to_response(res))


@router.post("/{id}/close", response_model=StandardResponse[ComplianceAssessmentResponse])
async def close_assessment(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ComplianceAssessmentResponse]:
    """Transition assessment status to CLOSED."""
    record = await GovernanceRiskComplianceService.get_assessment(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == ComplianceStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot transition status of a closed GRC assessment",
        )

    res = await GovernanceRiskComplianceService.transition_status(id, ComplianceStatus.CLOSED)
    return StandardResponse(data=GovernanceRiskComplianceService.to_response(res))


@router.post("/{id}/evidence", response_model=StandardResponse[ComplianceEvidenceResponse])
async def upload_evidence(
    id: uuid.UUID,
    req: UploadEvidenceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> StandardResponse[ComplianceEvidenceResponse]:
    """Upload compliance evidence document/hash mapping."""
    record = await GovernanceRiskComplianceService.get_assessment(id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found",
        )
    if record.scope_id:
        await check_scope_ownership(db, record.scope_id, current_user)

    if record.status == ComplianceStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot upload evidence to a closed GRC assessment",
        )

    res = await GovernanceRiskComplianceService.add_evidence(
        assessment_id=id, file_name=req.file_name, file_hash=req.file_hash
    )
    return StandardResponse(data=res)
