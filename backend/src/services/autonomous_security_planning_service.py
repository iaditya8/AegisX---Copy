import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from src.domain.entities.autonomous_planning import (
    PlanningRecordResponse,
    PlanStatus,
    PlanPriority,
    MilestoneResponse,
    MilestoneType,
)
from src.services.planning_category_registry import PlanningCategoryRegistry
from src.services.planning_fingerprint_service import PlanningFingerprintService
from src.services.planning_history_service import PlanningHistoryService


class AutonomousSecurityPlanningService:
    # in-memory store: plan_id -> PlanningRecordResponse
    _plans: Dict[uuid.UUID, PlanningRecordResponse] = {}
    # fingerprint -> plan_id
    _fingerprint_lookup: Dict[str, uuid.UUID] = {}

    @classmethod
    def clear_plans(cls) -> None:
        """Clear all in-memory plans and history logs."""
        cls._plans.clear()
        cls._fingerprint_lookup.clear()
        PlanningHistoryService.clear_history()

    @classmethod
    def get_all_plans(cls) -> List[PlanningRecordResponse]:
        """Retrieve all plans currently tracked."""
        return list(cls._plans.values())

    @classmethod
    def get_plan(cls, plan_id: uuid.UUID) -> Optional[PlanningRecordResponse]:
        """Retrieve a specific plan by ID."""
        return cls._plans.get(plan_id)

    @classmethod
    def get_plan_by_fingerprint(cls, fingerprint: str) -> Optional[PlanningRecordResponse]:
        """Retrieve a plan by fingerprint."""
        pid = cls._fingerprint_lookup.get(fingerprint)
        if pid:
            return cls.get_plan(pid)
        return None

    @classmethod
    def _get_uuid(cls, val) -> Optional[uuid.UUID]:
        if isinstance(val, uuid.UUID):
            return val
        if isinstance(val, str):
            try:
                return uuid.UUID(val)
            except ValueError:
                pass
        return None

    @classmethod
    def create_or_sync_plan(
        cls,
        category: str,
        name: str,
        scope_id: Optional[uuid.UUID] = None,
        priority: PlanPriority = PlanPriority.MEDIUM,
        milestones: Optional[List[MilestoneResponse]] = None,
    ) -> PlanningRecordResponse:
        """Create or synchronize an autonomous plan option enforcing terminal state protection."""
        if not PlanningCategoryRegistry.validate(category):
            raise ValueError(f"Invalid Plan Category: {category}")

        val_scope_id = cls._get_uuid(scope_id)

        # Generate stable fingerprint
        fingerprint = PlanningFingerprintService.generate_fingerprint(category, name, val_scope_id)

        existing = cls.get_plan_by_fingerprint(fingerprint)
        if existing:
            # Enforce Planning Terminal State Rule: sync cannot reactivate CLOSED plans
            if existing.status == PlanStatus.CLOSED:
                return existing

            # Identity preservation: sync preserves plan_id, created_at, status, history, milestones, priorities
            # If milestones are passed, update existing non-completed milestones or append new ones without resetting completed ones
            if milestones:
                existing_milestones = {m.target_entity_id: m for m in existing.milestones}
                updated_list = []
                for m in milestones:
                    if m.target_entity_id in existing_milestones:
                        # Keep completed or current status of existing milestone
                        curr = existing_milestones[m.target_entity_id]
                        if curr.status == "COMPLETED":
                            updated_list.append(curr)
                        else:
                            curr.status = m.status
                            curr.completed_at = m.completed_at
                            updated_list.append(curr)
                    else:
                        updated_list.append(m)
                existing.milestones = updated_list

            existing.updated_at = datetime.now(timezone.utc)
            return existing

        # Create new plan
        plan_id = uuid.uuid4()
        plan = PlanningRecordResponse(
            plan_id=plan_id,
            plan_fingerprint=fingerprint,
            category=category.strip().upper(),
            name=name.strip(),
            status=PlanStatus.DRAFT,
            priority=PlanPriority(priority),
            scope_id=val_scope_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            milestones=milestones or [],
            roadmap=None,
        )

        cls._plans[plan_id] = plan
        cls._fingerprint_lookup[fingerprint] = plan_id

        # Record history event
        PlanningHistoryService.record_event(
            plan_id, "CREATED", f"Created plan: {name}"
        )

        return plan

    @classmethod
    def approve_plan(cls, plan_id: uuid.UUID) -> PlanningRecordResponse:
        """Approve the plan. Plan approvals must always be manually triggered by operators (API/UI)."""
        plan = cls.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan with ID {plan_id} not found")

        # Enforce Planning Terminal State Rule
        if plan.status == PlanStatus.CLOSED:
            return plan

        if plan.status != PlanStatus.APPROVED:
            plan.status = PlanStatus.APPROVED
            plan.updated_at = datetime.now(timezone.utc)
            PlanningHistoryService.record_event(
                plan_id, "APPROVED", "Plan approved by operator"
            )

        return plan

    @classmethod
    def activate_plan(cls, plan_id: uuid.UUID) -> PlanningRecordResponse:
        """Activate the plan."""
        plan = cls.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan with ID {plan_id} not found")

        # Enforce Planning Terminal State Rule
        if plan.status == PlanStatus.CLOSED:
            return plan

        if plan.status != PlanStatus.ACTIVE:
            plan.status = PlanStatus.ACTIVE
            plan.updated_at = datetime.now(timezone.utc)
            PlanningHistoryService.record_event(
                plan_id, "ACTIVATED", "Plan status changed to ACTIVE"
            )

        return plan

    @classmethod
    def close_plan(cls, plan_id: uuid.UUID) -> PlanningRecordResponse:
        """Close the plan (terminal state)."""
        plan = cls.get_plan(plan_id)
        if not plan:
            raise ValueError(f"Plan with ID {plan_id} not found")

        if plan.status != PlanStatus.CLOSED:
            plan.status = PlanStatus.CLOSED
            plan.updated_at = datetime.now(timezone.utc)
            PlanningHistoryService.record_event(
                plan_id, "CLOSED", "Plan status changed to CLOSED"
            )

        return plan

    @classmethod
    async def sync_plans(cls, db=None) -> None:
        """Query active decisions and sync planning records & milestones."""
        from src.services.security_decision_service import SecurityDecisionService
        from src.domain.entities.security_decision import DecisionStatus, DecisionType

        decisions = SecurityDecisionService.get_all_decisions()

        # Group decisions by scope and category
        # Let's create two standard plans per scope:
        # 1. Category COMPLIANCE_ALIGNMENT, name: "Compliance Alignment Plan"
        # 2. Category RISK_REDUCTION_CAMPAIGN, name: "Risk Remediation Campaign Plan"
        scopes = {d.scope_id for d in decisions}

        for scope_id in scopes:
            scope_decisions = [d for d in decisions if d.scope_id == scope_id]

            # 1. Compliance Controls -> Compliance Alignment Plan
            comp_decs = [d for d in scope_decisions if d.decision_type == DecisionType.COMPLIANCE_CONTROL]
            if comp_decs:
                milestones = []
                for d in comp_decs:
                    mstatus = "COMPLETED" if d.status == DecisionStatus.COMMITTED else "PENDING"
                    mcompleted = datetime.now(timezone.utc) if mstatus == "COMPLETED" else None
                    milestones.append(
                        MilestoneResponse(
                            milestone_id=uuid.uuid4(),
                            name=d.option_name,
                            milestone_type=MilestoneType.AUDIT,
                            target_entity_id=d.decision_id,
                            status=mstatus,
                            due_date=datetime.now(timezone.utc) + timedelta(days=14),
                            completed_at=mcompleted,
                        )
                    )
                cls.create_or_sync_plan(
                    category="COMPLIANCE_ALIGNMENT",
                    name="Compliance Alignment Plan",
                    scope_id=scope_id,
                    priority=PlanPriority.HIGH,
                    milestones=milestones,
                )

            # 2. Remediations -> Risk Remediation Campaign Plan
            rem_decs = [d for d in scope_decisions if d.decision_type == DecisionType.REMEDIATION]
            if rem_decs:
                milestones = []
                for d in rem_decs:
                    mstatus = "COMPLETED" if d.status == DecisionStatus.COMMITTED else "PENDING"
                    mcompleted = datetime.now(timezone.utc) if mstatus == "COMPLETED" else None
                    milestones.append(
                        MilestoneResponse(
                            milestone_id=uuid.uuid4(),
                            name=d.option_name,
                            milestone_type=MilestoneType.REMEDIATION,
                            target_entity_id=d.decision_id,
                            status=mstatus,
                            due_date=datetime.now(timezone.utc) + timedelta(days=7),
                            completed_at=mcompleted,
                        )
                    )
                cls.create_or_sync_plan(
                    category="RISK_REDUCTION_CAMPAIGN",
                    name="Risk Remediation Campaign Plan",
                    scope_id=scope_id,
                    priority=PlanPriority.CRITICAL,
                    milestones=milestones,
                )
