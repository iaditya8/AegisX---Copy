import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.v1.dependencies.auth import RoleChecker
from src.domain.entities.incident import (
    IncidentHistoryEntry,
    IncidentResponse,
    IncidentSeverity,
    IncidentStatus,
    InvestigationEntry,
)
from src.infrastructure.database.models import Asset, Scope, User
from src.infrastructure.database.session import get_db
from src.services.incident_escalation_service import IncidentEscalationService
from src.services.incident_evidence_service import IncidentEvidenceService
from src.services.incident_history_service import IncidentHistoryService
from src.services.incident_service import IncidentRecord, IncidentService
from src.services.investigation_service import InvestigationService
from src.services.scope_service import get_scope_by_id

router = APIRouter(prefix="/incidents", tags=["incidents"])


class AssignIncidentRequest(BaseModel):
    owner_id: Optional[uuid.UUID] = None


class IncidentCreate(BaseModel):
    title: str
    description: str
    severity: str
    alert_ids: List[uuid.UUID] = []
    asset_ids: List[uuid.UUID] = []
    finding_ids: List[uuid.UUID] = []


class StartInvestigationRequest(BaseModel):
    notes: str


class ContainInvestigationRequest(BaseModel):
    notes: str


class AddNoteRequest(BaseModel):
    notes: str


class EscalateTeamRequest(BaseModel):
    team: str


class EscalateOwnerRequest(BaseModel):
    owner_id: Optional[uuid.UUID] = None


# --- Helper Checks ---


async def get_allowed_asset_ids(db: AsyncSession, current_user: User) -> Optional[set]:
    """Retrieve allowed asset IDs for non-admin users based on scope ownership."""
    if current_user.role == "admin":
        return None

    q_scopes = select(Scope).where(
        Scope.owner_id == current_user.id, Scope.deleted_at.is_(None)
    )
    res_scopes = await db.execute(q_scopes)
    scopes = res_scopes.scalars().all()
    scope_ids = {s.id for s in scopes}

    if not scope_ids:
        return set()

    q_assets = select(Asset.id).where(
        Asset.scope_id.in_(scope_ids), Asset.deleted_at.is_(None)
    )
    res_assets = await db.execute(q_assets)
    return set(res_assets.scalars().all())


async def check_incident_ownership(
    db: AsyncSession, incident: IncidentRecord, current_user: User
) -> None:
    """Enforce scope ownership check for non-admin operators on a specific incident."""
    if current_user.role == "admin":
        return

    if not incident.asset_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permissions to access this incident",
        )

    for asset_id in incident.asset_ids:
        asset = await db.get(Asset, asset_id)
        if not asset or asset.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Linked asset not found",
            )

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


def to_incident_response(inc: IncidentRecord) -> IncidentResponse:
    """Map IncidentRecord to Pydantic IncidentResponse."""
    return IncidentResponse(
        incident_id=inc.incident_id,
        incident_fingerprint=inc.incident_fingerprint,
        title=inc.title,
        description=inc.description,
        severity=inc.severity,
        status=inc.status,
        owner=inc.owner,
        created_at=inc.created_at,
        updated_at=inc.updated_at,
        alert_ids=inc.alert_ids,
        asset_ids=inc.asset_ids,
        finding_ids=inc.finding_ids,
        recommendation_ids=inc.recommendation_ids,
        remediation_ids=inc.remediation_ids,
    )


# --- API Routes ---


@router.get("", response_model=List[IncidentResponse])
async def list_incidents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all incidents, applying scope-filtering for non-admins."""
    incidents = IncidentService.get_all_incidents()
    if current_user.role == "admin":
        return [to_incident_response(i) for i in incidents]

    allowed_asset_ids = await get_allowed_asset_ids(db, current_user) or set()
    filtered = []
    for inc in incidents:
        if not inc.asset_ids:
            continue
        if all(aid in allowed_asset_ids for aid in inc.asset_ids):
            filtered.append(to_incident_response(inc))
    return filtered


@router.get("/open", response_model=List[IncidentResponse])
async def list_open_incidents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all OPEN or TRIAGED incidents."""
    incidents = IncidentService.get_all_incidents()
    open_incidents = [
        i
        for i in incidents
        if i.status in [IncidentStatus.OPEN, IncidentStatus.TRIAGED]
    ]

    if current_user.role == "admin":
        return [to_incident_response(i) for i in open_incidents]

    allowed_asset_ids = await get_allowed_asset_ids(db, current_user) or set()
    filtered = []
    for inc in open_incidents:
        if not inc.asset_ids:
            continue
        if all(aid in allowed_asset_ids for aid in inc.asset_ids):
            filtered.append(to_incident_response(inc))
    return filtered


@router.get("/escalated", response_model=List[IncidentResponse])
async def list_escalated_incidents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all ESCALATED incidents."""
    incidents = IncidentService.get_all_incidents()
    escalated_incidents = [i for i in incidents if i.status == IncidentStatus.ESCALATED]

    if current_user.role == "admin":
        return [to_incident_response(i) for i in escalated_incidents]

    allowed_asset_ids = await get_allowed_asset_ids(db, current_user) or set()
    filtered = []
    for inc in escalated_incidents:
        if not inc.asset_ids:
            continue
        if all(aid in allowed_asset_ids for aid in inc.asset_ids):
            filtered.append(to_incident_response(inc))
    return filtered


@router.get("/critical", response_model=List[IncidentResponse])
async def list_critical_incidents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve all CRITICAL severity incidents."""
    incidents = IncidentService.get_all_incidents()
    critical_incidents = [
        i for i in incidents if i.severity == IncidentSeverity.CRITICAL
    ]

    if current_user.role == "admin":
        return [to_incident_response(i) for i in critical_incidents]

    allowed_asset_ids = await get_allowed_asset_ids(db, current_user) or set()
    filtered = []
    for inc in critical_incidents:
        if not inc.asset_ids:
            continue
        if all(aid in allowed_asset_ids for aid in inc.asset_ids):
            filtered.append(to_incident_response(inc))
    return filtered


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve a specific incident by ID, enforcing scope checks."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)
    return to_incident_response(incident)


@router.post("/{incident_id}/assign", response_model=IncidentResponse)
async def assign_incident(
    incident_id: uuid.UUID,
    request: AssignIncidentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Assign incident owner."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        updated = await IncidentService.assign_incident(
            db=db,
            incident_id=incident_id,
            owner_id=request.owner_id,
            actor_id=current_user.id,
        )
        return to_incident_response(updated)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{incident_id}/triage", response_model=IncidentResponse)
async def triage_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Triage the incident."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        updated = await IncidentService.transition_status(
            db=db,
            incident_id=incident_id,
            new_status=IncidentStatus.TRIAGED,
            actor_id=current_user.id,
        )
        return to_incident_response(updated)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{incident_id}/start", response_model=IncidentResponse)
async def start_investigation(
    incident_id: uuid.UUID,
    request: StartInvestigationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Start investigation on the incident."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        await InvestigationService.start_investigation(
            db=db,
            incident_id=incident_id,
            analyst_id=current_user.id,
            notes=request.notes,
        )
        return to_incident_response(incident)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{incident_id}/contain", response_model=IncidentResponse)
async def contain_incident(
    incident_id: uuid.UUID,
    request: ContainInvestigationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Mark investigation complete and set incident as CONTAINED."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        await InvestigationService.complete_investigation(
            db=db,
            incident_id=incident_id,
            analyst_id=current_user.id,
            notes=request.notes,
        )
        return to_incident_response(incident)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Mark incident as RESOLVED."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        updated = await IncidentService.transition_status(
            db=db,
            incident_id=incident_id,
            new_status=IncidentStatus.RESOLVED,
            actor_id=current_user.id,
        )
        return to_incident_response(updated)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{incident_id}/close", response_model=IncidentResponse)
async def close_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Mark incident as CLOSED."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        updated = await IncidentService.transition_status(
            db=db,
            incident_id=incident_id,
            new_status=IncidentStatus.CLOSED,
            actor_id=current_user.id,
        )
        return to_incident_response(updated)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{incident_id}/notes", response_model=InvestigationEntry)
async def add_incident_note(
    incident_id: uuid.UUID,
    request: AddNoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Add an analyst note to the investigation timeline."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        entry = await InvestigationService.add_investigation_note(
            db=db,
            incident_id=incident_id,
            analyst_id=current_user.id,
            notes=request.notes,
        )
        return entry
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{incident_id}/timeline", response_model=List[IncidentHistoryEntry])
async def get_incident_timeline(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve investigation timeline entries for an incident."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)
    return await IncidentHistoryService.get_history(incident_id)


@router.get("/{incident_id}/evidence")
async def get_incident_evidence(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator", "reader"])),
):
    """Retrieve linked evidence for an incident."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)
    return await IncidentEvidenceService.get_evidence(incident_id)


@router.post("/{incident_id}/escalate/team", response_model=IncidentResponse)
async def escalate_incident_team(
    incident_id: uuid.UUID,
    request: EscalateTeamRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Escalate incident to a team."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        await IncidentEscalationService.escalate_to_team(
            db=db,
            incident_id=incident_id,
            team_name=request.team,
            actor_id=current_user.id,
        )
        return to_incident_response(incident)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{incident_id}/escalate/owner", response_model=IncidentResponse)
async def escalate_incident_owner(
    incident_id: uuid.UUID,
    request: EscalateOwnerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Escalate incident to asset owner."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        await IncidentEscalationService.escalate_to_owner(
            db=db,
            incident_id=incident_id,
            owner_id=request.owner_id,
            actor_id=current_user.id,
        )
        return to_incident_response(incident)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/{incident_id}/escalate/management", response_model=IncidentResponse)
async def escalate_incident_management(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
):
    """Escalate incident to management."""
    incident = IncidentService.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found",
        )

    await check_incident_ownership(db, incident, current_user)

    try:
        await IncidentEscalationService.escalate_to_management(
            db=db,
            incident_id=incident_id,
            actor_id=current_user.id,
        )
        return to_incident_response(incident)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    inc_in: IncidentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "operator"])),
) -> IncidentResponse:
    from datetime import datetime, timezone
    incident_id = uuid.uuid4()
    fingerprint = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # Save to database
    from src.infrastructure.database.models import Incident
    db_inc = Incident(
        tenant_id=current_user.tenant_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
        id=incident_id,
        title=inc_in.title,
        description=inc_in.description,
        severity=IncidentSeverity(inc_in.severity.upper()),
        status=IncidentStatus.OPEN,
        incident_fingerprint=fingerprint,
        alert_ids=inc_in.alert_ids,
        asset_ids=inc_in.asset_ids,
        finding_ids=inc_in.finding_ids,
        created_at=now,
        updated_at=now,
    )
    db.add(db_inc)
    await db.commit()
    
    # Save to in-memory cache
    new_inc = IncidentRecord(
        incident_id=incident_id,
        incident_fingerprint=fingerprint,
        title=inc_in.title,
        description=inc_in.description,
        severity=IncidentSeverity(inc_in.severity.upper()),
        status=IncidentStatus.OPEN,
        alert_ids=inc_in.alert_ids,
        asset_ids=inc_in.asset_ids,
        finding_ids=inc_in.finding_ids,
    )
    IncidentService._incidents[incident_id] = new_inc
    IncidentService._fingerprint_lookup[fingerprint] = incident_id
    
    return to_incident_response(new_inc)
