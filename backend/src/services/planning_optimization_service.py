import uuid
from typing import List, Dict
from src.domain.entities.autonomous_planning import (
    PlanningRecordResponse,
    RoadmapResponse,
    MilestoneResponse,
    PlanStatus,
)
from src.services.planning_priority_registry import PlanningPriorityRegistry
from src.services.security_decision_service import SecurityDecisionService
from src.services.autonomous_security_planning_service import AutonomousSecurityPlanningService


class PlanningOptimizationService:
    @classmethod
    def calculate_roadmap(cls, plan: PlanningRecordResponse) -> RoadmapResponse:
        """Compute deterministic roadmap optimization for a plan."""
        milestones = plan.milestones
        if not milestones:
            return RoadmapResponse(
                roadmap_id=uuid.uuid4(),
                optimized_milestone_ids=[],
                estimated_effort_days=0.0,
                resource_utilization_coefficient=0.5,
            )

        # Retrieve decisions for net_benefit sorting
        decisions_by_id = {d.decision_id: d for d in SecurityDecisionService.get_all_decisions()}

        def get_sort_key(m: MilestoneResponse):
            # 1. Status: Completed milestones first
            status_val = 0 if m.status == "COMPLETED" else 1
            # 2. Priority Weight: Higher weight first
            weight = PlanningPriorityRegistry.get_weight(m.milestone_type)
            # 3. Decision Net Benefit (if exists)
            decision = decisions_by_id.get(m.target_entity_id)
            net_benefit = 0.0
            if decision and decision.tradeoff_matrix:
                net_benefit = decision.tradeoff_matrix.net_benefit or 0.0
            # 4. Tie-breaker: alphabetical name
            return (status_val, -weight, -net_benefit, m.name)

        sorted_milestones = sorted(milestones, key=get_sort_key)
        opt_ids = [m.milestone_id for m in sorted_milestones]

        # Deterministic Effort Days Calculation
        effort_map = {
            "REMEDIATION": 5.0,
            "VALIDATION": 3.0,
            "DEPLOYMENT": 2.0,
            "AUDIT": 1.0,
        }
        total_effort = sum(effort_map.get(m.milestone_type.value, 2.0) for m in milestones)

        # Resource Utilization Coefficient
        completed = sum(1 for m in milestones if m.status == "COMPLETED")
        coef = 0.5 + 0.45 * (completed / len(milestones))

        return RoadmapResponse(
            roadmap_id=uuid.uuid4(),
            optimized_milestone_ids=opt_ids,
            estimated_effort_days=total_effort,
            resource_utilization_coefficient=coef,
        )

    @classmethod
    def optimize_sequences(cls) -> None:
        """Sequence milestones deterministically based on security decision tradeoffs."""
        plans = AutonomousSecurityPlanningService.get_all_plans()
        for p in plans:
            # Enforce Planning Terminal State Rule: optimization calculations cannot reactivate CLOSED plans
            if p.status == PlanStatus.CLOSED:
                continue

            # Derived intelligence calculation
            p.roadmap = cls.calculate_roadmap(p)
