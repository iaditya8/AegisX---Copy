import uuid
import copy
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.security_program import (
    ProgramSeverity,
    ProgramStatus,
    KPIStatus,
    KRIStatus,
    SecurityProgramResponse,
    ProgramObjectiveResponse,
    ProgramInitiativeResponse,
    KPIResponse,
    KRIResponse,
)
from src.services.security_program_registry import SecurityProgramRegistry
from src.services.program_fingerprint_service import ProgramFingerprintService
from src.services.program_history_service import ProgramHistoryService
from src.services.kpi_service import KPIService
from src.services.kri_service import KRIService
from src.services.program_health_service import ProgramHealthService
from src.services.program_correlation_service import ProgramCorrelationService
from src.infrastructure.database.models import (
    SecurityProgram as DBProgram,
    SecurityProgramObjective,
    SecurityProgramInitiative,
    IntelligenceEvent
)
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.core.tenant import get_current_tenant_id


class ProgramObjectiveRecord:
    def __init__(self, objective_id: uuid.UUID, name: str, description: str, completion_percentage: float):
        self.objective_id = objective_id
        self.name = name
        self.description = description
        self.completion_percentage = completion_percentage


class ProgramInitiativeRecord:
    def __init__(self, initiative_id: uuid.UUID, name: str, description: str, status: str, completion_percentage: float):
        self.initiative_id = initiative_id
        self.name = name
        self.description = description
        self.status = status
        self.completion_percentage = completion_percentage


class SecurityProgramRecord:
    def __init__(
        self,
        program_id: uuid.UUID,
        program_fingerprint: str,
        name: str,
        description: str,
        category: str,
        severity: ProgramSeverity,
        status: ProgramStatus,
        program_score: float,
        objectives: List[ProgramObjectiveRecord],
        initiatives: List[ProgramInitiativeRecord],
        scope_id: Optional[uuid.UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.program_id = program_id
        self.program_fingerprint = program_fingerprint
        self.name = name
        self.description = description
        self.category = category
        self.severity = severity
        self.status = status
        self.program_score = program_score
        self.objectives = list(objectives)
        self.initiatives = list(initiatives)
        self.scope_id = scope_id
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)


class SecurityProgramService:
    # in-memory store: program_id -> SecurityProgramRecord
    _programs: Dict[uuid.UUID, SecurityProgramRecord] = {}
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_programs(cls) -> None:
        """Clear all security program caches."""
        cls._programs.clear()
        cls._fingerprint_lookup.clear()

    @classmethod
    async def bootstrap(cls, db: AsyncSession) -> None:
        """Bootstrap the L2 cache from PostgreSQL database."""
        cls.clear_programs()
        async with UnitOfWork() as uow:
            db_programs = await uow.program_repo.list()
            for db_p in db_programs:
                db_objs = await uow.program_repo.list_objectives(db_p.id)
                db_inits = await uow.program_repo.list_initiatives(db_p.id)

                objs = [
                    ProgramObjectiveRecord(
                        objective_id=o.objective_id,
                        name=o.name,
                        description=o.description,
                        completion_percentage=float(o.completion_percentage),
                    )
                    for o in db_objs
                ]

                inits = [
                    ProgramInitiativeRecord(
                        initiative_id=i.initiative_id,
                        name=i.name,
                        description=i.description,
                        status=i.status,
                        completion_percentage=float(i.completion_percentage),
                    )
                    for i in db_inits
                ]

                record = SecurityProgramRecord(
                    program_id=db_p.id,
                    program_fingerprint=db_p.program_fingerprint,
                    name=db_p.name,
                    description=db_p.description,
                    category=db_p.category,
                    severity=ProgramSeverity(db_p.severity),
                    status=ProgramStatus(db_p.status),
                    program_score=float(db_p.program_score),
                    objectives=objs,
                    initiatives=inits,
                    scope_id=db_p.scope_id,
                    created_at=db_p.created_at,
                    updated_at=db_p.updated_at,
                )
                cls._programs[db_p.id] = record
                cls._fingerprint_lookup[db_p.program_fingerprint] = db_p.id

    @classmethod
    def get_all_programs(cls) -> List[SecurityProgramRecord]:
        """Retrieve all security program records."""
        return list(cls._programs.values())

    @classmethod
    def get_program(cls, program_id: uuid.UUID) -> Optional[SecurityProgramRecord]:
        """Retrieve a security program record by ID."""
        return cls._programs.get(program_id)

    @classmethod
    def get_program_by_fingerprint(cls, fingerprint: str) -> Optional[SecurityProgramRecord]:
        """Retrieve a security program by fingerprint."""
        program_id = cls._fingerprint_lookup.get(fingerprint)
        if program_id:
            return cls.get_program(program_id)
        return None

    @classmethod
    async def create_or_sync_program(
        cls,
        name: str,
        description: str,
        category: str,
        severity: ProgramSeverity,
        objectives: List[ProgramObjectiveRecord],
        initiatives: List[ProgramInitiativeRecord],
        scope_id: Optional[uuid.UUID] = None,
    ) -> SecurityProgramRecord:
        """Create a new program or synchronize with an existing one based on identity rules."""
        if not SecurityProgramRegistry.is_valid_category(category):
            raise ValueError(f"Invalid category: {category}")

        fingerprint = ProgramFingerprintService.generate_fingerprint(name, category, severity)
        existing = cls.get_program_by_fingerprint(fingerprint)
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")

        if existing:
            if existing.status in [ProgramStatus.COMPLETED, ProgramStatus.CLOSED]:
                # Terminal State Rule: COMPLETED and CLOSED cannot be reactivated or modified by sync
                return existing

            # Identity preservation: preserve program_id, history, timestamps, and details
            changed = False
            if existing.description != description:
                existing.description = description
                changed = True

            # Recalculate health
            kpis = KPIService.calculate_kpis(existing.scope_id)
            kris = KRIService.calculate_kris(existing.scope_id)
            
            # Map objective/initiative records to response models for health calculation
            obj_res = [ProgramObjectiveResponse(objective_id=o.objective_id, name=o.name, description=o.description, completion_percentage=o.completion_percentage) for o in existing.objectives]
            init_res = [ProgramInitiativeResponse(initiative_id=i.initiative_id, name=i.name, description=i.description, status=i.status, completion_percentage=i.completion_percentage) for i in existing.initiatives]
            
            health = ProgramHealthService.calculate_health(obj_res, init_res, kpis, kris)
            new_score = health["program_score"]

            if existing.program_score != new_score:
                existing.program_score = new_score
                changed = True

            if changed:
                existing.updated_at = datetime.now(timezone.utc)
                async with UnitOfWork() as uow:
                    db_p = await uow.program_repo.get(existing.program_id)
                    if db_p:
                        db_p.description = existing.description
                        db_p.program_score = existing.program_score
                        db_p.updated_at = existing.updated_at
                        await ProgramHistoryService.record_event(
                            existing.program_id,
                            "EFFECTIVENESS_CHANGED",
                            f"Health score recalculated: {new_score}",
                            uow=uow,
                        )
                        await ProgramHistoryService.record_event(
                            existing.program_id,
                            "DRIFT_DETECTED",
                            f"Program synced: score={existing.program_score}",
                            uow=uow,
                        )
                        # Stage outbox event
                        outbox_evt = IntelligenceEvent(
                            tenant_id=tenant_id,
                            event_type="program.updated",
                            payload={
                                "program_id": str(existing.program_id),
                                "status": existing.status.value,
                            }
                        )
                        uow.session.add(outbox_evt)
                        await uow.commit()

            return existing

        # Create new security program record
        program_id = uuid.uuid4()
        
        # Determine initial score
        kpis = KPIService.calculate_kpis(scope_id)
        kris = KRIService.calculate_kris(scope_id)
        obj_res = [ProgramObjectiveResponse(objective_id=o.objective_id, name=o.name, description=o.description, completion_percentage=o.completion_percentage) for o in objectives]
        init_res = [ProgramInitiativeResponse(initiative_id=i.initiative_id, name=i.name, description=i.description, status=i.status, completion_percentage=i.completion_percentage) for i in initiatives]
        health = ProgramHealthService.calculate_health(obj_res, init_res, kpis, kris)
        prog_score = health["program_score"]

        record = SecurityProgramRecord(
            program_id=program_id,
            program_fingerprint=fingerprint,
            name=name,
            description=description,
            category=category,
            severity=severity,
            status=ProgramStatus.PLANNED,
            program_score=prog_score,
            objectives=objectives,
            initiatives=initiatives,
            scope_id=scope_id,
        )
        cls._programs[program_id] = record
        cls._fingerprint_lookup[fingerprint] = program_id

        async with UnitOfWork() as uow:
            db_p = DBProgram(
                tenant_id=tenant_id,
                id=program_id,
                program_fingerprint=fingerprint,
                name=name,
                description=description,
                category=category,
                severity=severity.value,
                status=ProgramStatus.PLANNED.value,
                program_score=prog_score,
                scope_id=scope_id,
            )
            await uow.program_repo.save(db_p)
            await uow.session.flush()

            for o in objectives:
                db_o = SecurityProgramObjective(
                    tenant_id=tenant_id,
                    objective_id=o.objective_id,
                    program_id=program_id,
                    name=o.name,
                    description=o.description,
                    completion_percentage=o.completion_percentage,
                )
                await uow.program_repo.save_objective(db_o)

            for i in initiatives:
                db_i = SecurityProgramInitiative(
                    tenant_id=tenant_id,
                    initiative_id=i.initiative_id,
                    program_id=program_id,
                    name=i.name,
                    description=i.description,
                    status=i.status,
                    completion_percentage=i.completion_percentage,
                )
                await uow.program_repo.save_initiative(db_i)

            await ProgramHistoryService.record_event(
                program_id,
                "CREATED",
                f"Created security program: '{name}' ({category})",
                uow=uow,
            )

            # Stage outbox event
            outbox_evt = IntelligenceEvent(
                tenant_id=tenant_id,
                event_type="program.created",
                payload={
                    "program_id": str(program_id),
                    "status": ProgramStatus.PLANNED.value,
                }
            )
            uow.session.add(outbox_evt)
            await uow.commit()

        return record

    @classmethod
    async def sync_programs(cls, db: AsyncSession) -> List[SecurityProgramRecord]:
        """Discover and sync programs based on local detections and control validation states."""
        synced = []

        # 1. Vulnerability Management Program
        # Create standard objectives and initiatives
        o1 = ProgramObjectiveRecord(uuid.uuid4(), "Reduce Mean Time To Respond", "Ensure rapid mitigation of identified issues.", 80.0)
        o2 = ProgramObjectiveRecord(uuid.uuid4(), "Increase Control Effectiveness", "Improve validation scores across controls.", 90.0)
        i1 = ProgramInitiativeRecord(uuid.uuid4(), "Implement Automated Control Validation", "Setup automated execution schedules.", "ACTIVE", 70.0)
        i2 = ProgramInitiativeRecord(uuid.uuid4(), "Deploy Realtime Monitoring Detections", "Install rules inside scope endpoints.", "ACTIVE", 50.0)

        prog = await cls.create_or_sync_program(
            name="Vulnerability Management Program",
            description="Manages core security posture and vulnerability remediation workflows.",
            category="Vulnerability Management",
            severity=ProgramSeverity.HIGH,
            objectives=[o1, o2],
            initiatives=[i1, i2],
        )
        synced.append(prog)

        # Build correlations
        for p in synced:
            await ProgramCorrelationService.correlate_program(db, p.program_id, p.scope_id)

        return synced

    @classmethod
    async def transition_program_status(cls, program_id: uuid.UUID, new_status: ProgramStatus) -> SecurityProgramRecord:
        """Transition program status safely, enforcing terminal states."""
        program = cls.get_program(program_id)
        if not program:
            raise ValueError(f"Program {program_id} not found")

        if program.status in [ProgramStatus.COMPLETED, ProgramStatus.CLOSED]:
            # Terminal State Rule: cannot reactivate or modify
            return program

        old_status = program.status
        program.status = new_status
        program.updated_at = datetime.now(timezone.utc)
        
        tenant_id = get_current_tenant_id() or uuid.UUID("00000000-0000-0000-0000-000000000000")
        async with UnitOfWork() as uow:
            db_p = await uow.program_repo.get(program_id)
            if db_p:
                db_p.status = new_status.value
                db_p.updated_at = program.updated_at
                await ProgramHistoryService.record_event(
                    program_id,
                    "STATUS_CHANGED",
                    f"Status transitioned from {old_status.value} to {new_status.value}",
                    uow=uow,
                )
                # Stage outbox event
                outbox_evt = IntelligenceEvent(
                    tenant_id=tenant_id,
                    event_type="program.status_changed",
                    payload={
                        "program_id": str(program_id),
                        "status": new_status.value,
                    }
                )
                uow.session.add(outbox_evt)
                await uow.commit()

        return program

    @classmethod
    def to_response(cls, record: SecurityProgramRecord) -> SecurityProgramResponse:
        """Convert a SecurityProgramRecord to a SecurityProgramResponse schema."""
        obj_res = [
            ProgramObjectiveResponse(
                objective_id=o.objective_id,
                name=o.name,
                description=o.description,
                completion_percentage=o.completion_percentage,
            )
            for o in record.objectives
        ]
        init_res = [
            ProgramInitiativeResponse(
                initiative_id=i.initiative_id,
                name=i.name,
                description=i.description,
                status=i.status,
                completion_percentage=i.completion_percentage,
            )
            for i in record.initiatives
        ]
        
        # Calculate KPIs/KRIs dynamically
        kpis = KPIService.calculate_kpis(record.scope_id)
        kris = KRIService.calculate_kris(record.scope_id)

        return SecurityProgramResponse(
            program_id=record.program_id,
            program_fingerprint=record.program_fingerprint,
            name=record.name,
            description=record.description,
            category=record.category,
            severity=record.severity,
            status=record.status,
            program_score=record.program_score,
            objectives=obj_res,
            initiatives=init_res,
            kpis=kpis,
            kris=kris,
            scope_id=record.scope_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
