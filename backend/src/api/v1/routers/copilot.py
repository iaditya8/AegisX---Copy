import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.infrastructure.database.models import (
    Asset,
    Finding,
    User,
    Workflow,
    WorkflowEvent,
)
from src.infrastructure.database.session import get_db
from src.services.ai_rate_limit_service import AIRateLimitService
from src.services.asset_copilot_service import AssetCopilotService
from src.services.executive_copilot_service import ExecutiveCopilotService
from src.services.finding_copilot_service import FindingCopilotService
from src.services.scope_service import get_scope_by_id

router = APIRouter(tags=["copilot"])


# --- Pydantic Response Models ---


class AssetExplanationResponse(BaseModel):
    success: bool
    source: str
    message: str
    generated_at: str
    summary: str
    risk_analysis: str
    priority_reasons: List[str]


class FindingExplanationResponse(BaseModel):
    success: bool
    source: str
    message: str
    generated_at: str
    summary: str
    impact: str
    priority: str
    investigation_guidance: str


class ExecutiveSummaryResponse(BaseModel):
    success: bool
    source: str
    message: str
    generated_at: str
    executive_summary: str
    top_risks: List[str]
    notable_changes: List[str]


class CopilotAskRequest(BaseModel):
    prompt: str
    scope_id: str | None = None


class CopilotCitation(BaseModel):
    id: str
    type: str
    label: str
    link_url: str


class CopilotAskResponse(BaseModel):
    answer: str
    citations: List[CopilotCitation]


class CopilotHistoryResponse(BaseModel):
    id: str
    user_id: str
    scope_id: str | None
    prompt: str
    response_text: str
    created_at: str


# --- Helper Enforcements & Event Emission ---


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


async def emit_copilot_event(
    db: AsyncSession,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """Emit a workflow event for copilot tracking."""
    # Retrieve the latest workflow to bind the event to
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


# --- Endpoints ---


@router.get(
    "/copilot/assets/{id}",
    response_model=AssetExplanationResponse,
)
async def explain_asset(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> AssetExplanationResponse:
    """Explain asset posture and risk."""
    # 1. Enforce rate limiting
    if not AIRateLimitService.check_rate_limit(current_user.id, current_user.role):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too Many Requests: Copilot rate limit exceeded",
        )

    # 2. Enforce scope ownership validation
    asset = await db.get(Asset, id)
    if not asset or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )
    await check_asset_ownership(db, asset, current_user)

    # 3. Emit requested event
    await emit_copilot_event(
        db,
        "copilot.requested",
        {"user_id": str(current_user.id), "target_id": str(id), "type": "asset"},
    )

    # 4. Invoke service
    result = await AssetCopilotService.explain_asset(db, id, actor_id=current_user.id)

    # 5. Emit generated/cached event
    if result["success"]:
        if result["source"] == "cache":
            await emit_copilot_event(
                db,
                "copilot.cached",
                {
                    "user_id": str(current_user.id),
                    "target_id": str(id),
                    "type": "asset",
                },
            )
        elif result["source"] != "fallback":
            await emit_copilot_event(
                db,
                "copilot.generated",
                {
                    "user_id": str(current_user.id),
                    "target_id": str(id),
                    "type": "asset",
                },
            )

    return AssetExplanationResponse(**result)


@router.get(
    "/copilot/findings/{id}",
    response_model=FindingExplanationResponse,
)
async def explain_finding(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> FindingExplanationResponse:
    """Explain finding details and remediation."""
    # 1. Enforce rate limiting
    if not AIRateLimitService.check_rate_limit(current_user.id, current_user.role):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too Many Requests: Copilot rate limit exceeded",
        )

    # 2. Enforce scope ownership validation
    finding = await db.get(Finding, id)
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found",
        )
    await check_finding_ownership(db, finding, current_user)

    # 3. Emit requested event
    await emit_copilot_event(
        db,
        "copilot.requested",
        {"user_id": str(current_user.id), "target_id": str(id), "type": "finding"},
    )

    # 4. Invoke service
    result = await FindingCopilotService.explain_finding(
        db, id, actor_id=current_user.id
    )

    # 5. Emit generated/cached event
    if result["success"]:
        if result["source"] == "cache":
            await emit_copilot_event(
                db,
                "copilot.cached",
                {
                    "user_id": str(current_user.id),
                    "target_id": str(id),
                    "type": "finding",
                },
            )
        elif result["source"] != "fallback":
            await emit_copilot_event(
                db,
                "copilot.generated",
                {
                    "user_id": str(current_user.id),
                    "target_id": str(id),
                    "type": "finding",
                },
            )

    return FindingExplanationResponse(**result)


@router.get(
    "/copilot/executive",
    response_model=ExecutiveSummaryResponse,
)
async def generate_executive_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> ExecutiveSummaryResponse:
    """Explain organizational executive posture."""
    # 1. Enforce rate limiting
    if not AIRateLimitService.check_rate_limit(current_user.id, current_user.role):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too Many Requests: Copilot rate limit exceeded",
        )

    target_id = current_user.id

    # 2. Emit requested event
    await emit_copilot_event(
        db,
        "copilot.requested",
        {
            "user_id": str(current_user.id),
            "target_id": str(target_id),
            "type": "executive",
        },
    )

    # 3. Invoke service
    result = await ExecutiveCopilotService.generate_executive_summary(
        db, actor_id=current_user.id
    )

    # 4. Emit generated/cached event
    if result["success"]:
        if result["source"] == "cache":
            await emit_copilot_event(
                db,
                "copilot.cached",
                {
                    "user_id": str(current_user.id),
                    "target_id": str(target_id),
                    "type": "executive",
                },
            )
        elif result["source"] != "fallback":
            await emit_copilot_event(
                db,
                "copilot.generated",
                {
                    "user_id": str(current_user.id),
                    "target_id": str(target_id),
                    "type": "executive",
                },
            )

    return ExecutiveSummaryResponse(**result)


@router.post(
    "/copilot/ask",
    response_model=CopilotAskResponse,
)
async def ask_copilot(
    request: CopilotAskRequest,
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """
    Chat with the AI Copilot Workspace.
    """
    # Mocking a static response just like the MSW version, to prevent 404
    return CopilotAskResponse(
        answer="Based on risk audits, I recommend verifying [MFA Disabled on Admin Account](finding:posture-123) which exposes the [Primary DB Instance](asset:asset-456).",
        citations=[
            CopilotCitation(id="posture-123", type="finding", label="MFA Disabled on Admin Account", link_url="/posture"),
            CopilotCitation(id="asset-456", type="asset", label="Primary DB Instance", link_url="/inventory")
        ]
    )


@router.get(
    "/copilot/history",
    response_model=List[CopilotHistoryResponse],
)
async def get_copilot_history(
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """
    Get the current user's AI Copilot chat history.
    """
    return [
        CopilotHistoryResponse(
            id="audit-123",
            user_id="user-admin",
            scope_id="scope-123",
            prompt="Show posture issues",
            response_text="Verify MFA Disabled finding.",
            created_at="2026-06-20T12:00:00Z"
        )
    ]
