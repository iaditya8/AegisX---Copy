import uuid
from datetime import datetime, timezone
from typing import List, Dict

from src.domain.entities.security_intelligence_fabric import (
    ConfidencePropagationResponse,
    FabricCorrelationResponse,
    FabricIntelligenceNodeResponse,
    PropagationMode,
    FabricStatus,
)
from src.services.unified_security_intelligence_fabric_service import UnifiedSecurityIntelligenceFabricService
from src.services.security_decision_service import SecurityDecisionService
from src.services.autonomous_security_planning_service import AutonomousSecurityPlanningService
from src.services.threat_intelligence_service import ThreatIntelligenceService


class IntelligencePropagationService:
    @classmethod
    def calculate_node_confidence(cls, node: FabricIntelligenceNodeResponse) -> float:
        """Compute deterministic confidence scores for a node."""
        weights = node.confidence_weights
        base_mod = weights.get("base_modifier", 1.0)
        decay = weights.get("decay_factor", 0.05)

        # Start with default confidence
        confidence = base_mod

        # Derived logic based on domain sources
        if node.source_type == "POSTURE":
            # Link to plans
            plans = AutonomousSecurityPlanningService.get_all_plans()
            matching_plan = next((p for p in plans if p.plan_id in node.target_links), None)
            if matching_plan and matching_plan.milestones:
                completed = sum(1 for m in matching_plan.milestones if m.status == "COMPLETED")
                progress = completed / len(matching_plan.milestones)
                confidence = base_mod * (0.8 + 0.2 * progress)
        elif node.source_type == "RISK":
            # Link to decisions
            decisions = SecurityDecisionService.get_all_decisions()
            matching_decision = next((d for d in decisions if d.decision_id in node.target_links), None)
            if matching_decision:
                if matching_decision.status.value == "COMMITTED":
                    confidence = base_mod * 1.2
                elif matching_decision.status.value == "RECOMMENDED":
                    confidence = base_mod * 1.0
                else:
                    confidence = base_mod * 0.8
        elif node.source_type == "THREAT_INTEL":
            # Link to threat records
            threats = ThreatIntelligenceService.get_all_threats()
            matching_threat = next((t for t in threats if t.threat_intel_id in node.target_links), None)
            if matching_threat:
                # Use threat fusion score or weight
                score = getattr(matching_threat, "fusion_score", 50.0) or 50.0
                confidence = base_mod * (score / 100.0)

        # Apply decay factor deterministically
        confidence = max(0.0, min(2.0, confidence - decay))
        return confidence

    @classmethod
    def process_propagation(cls) -> None:
        """Propagate confidence and threat scores deterministically across the fabric."""
        nodes = UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()
        for node in nodes:
            # Enforce Fabric Terminal State Rule: propagation updates cannot reactivate TERMINATED elements
            if node.status == FabricStatus.TERMINATED:
                continue

            node.confidence_weights["current_confidence"] = cls.calculate_node_confidence(node)

    @classmethod
    def get_propagations(cls) -> List[ConfidencePropagationResponse]:
        """Compute the propagation routes dynamically and deterministically."""
        nodes = UnifiedSecurityIntelligenceFabricService.get_all_fabric_nodes()
        routes = []
        for node in nodes:
            # Generate deterministic propagation route responses
            conf = node.confidence_weights.get("current_confidence", 1.0)
            decay = node.confidence_weights.get("decay_factor", 0.05)
            for target_id in node.target_links:
                routes.append(
                    ConfidencePropagationResponse(
                        propagation_id=uuid.uuid4(),
                        source_node_id=node.node_id,
                        target_node_id=target_id,
                        mode=PropagationMode.WEIGHTED,
                        confidence_score=conf,
                        decay_factor=decay,
                        timestamp=datetime.now(timezone.utc),
                    )
                )
        return routes

    @classmethod
    def calculate_score_maps(cls) -> List[FabricCorrelationResponse]:
        """Compute cross-domain correlation score maps deterministically."""
        # Static but deterministic cross-domain scores maps
        return [
            FabricCorrelationResponse(
                correlation_id=uuid.uuid4(),
                domain_source="THREAT_INTEL",
                domain_target="RISK",
                relationship_strength=0.85,
            ),
            FabricCorrelationResponse(
                correlation_id=uuid.uuid4(),
                domain_source="RISK",
                domain_target="POSTURE",
                relationship_strength=0.90,
            ),
            FabricCorrelationResponse(
                correlation_id=uuid.uuid4(),
                domain_source="POSTURE",
                domain_target="COMPLIANCE",
                relationship_strength=0.75,
            ),
        ]
