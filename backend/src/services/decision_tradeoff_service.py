import uuid
from typing import Dict, List
from src.domain.entities.security_decision import (
    DecisionResponse,
    DecisionTradeoffResponse,
    DecisionImpactResponse,
    DecisionImpact,
)
from src.services.tradeoff_factor_registry import TradeoffFactorRegistry
from src.services.security_decision_service import SecurityDecisionService
from src.services.security_intelligence_graph_service import SecurityIntelligenceGraphService


class DecisionTradeoffService:
    @classmethod
    def calculate_tradeoff(cls, d: DecisionResponse, centrality: float) -> DecisionTradeoffResponse:
        """Compute deterministic tradeoff factors."""
        factors = TradeoffFactorRegistry.get_factors(d.decision_type)
        cost_mult = factors.get("cost_multiplier", 1.0)
        risk_coeff = factors.get("risk_reduction_coefficient", 0.5)

        estimated_cost = 1000.0 * cost_mult
        estimated_risk_reduction = 100.0 * risk_coeff * (centrality / (centrality + 1.0))
        net_benefit = estimated_risk_reduction - (estimated_cost / 1000.0)

        return DecisionTradeoffResponse(
            cost_multiplier=cost_mult,
            risk_reduction_coefficient=risk_coeff,
            estimated_cost=estimated_cost,
            estimated_risk_reduction=estimated_risk_reduction,
            net_benefit=net_benefit,
        )

    @classmethod
    def calculate_impact(cls, d: DecisionResponse, centrality: float) -> DecisionImpactResponse:
        """Compute deterministic impact metrics."""
        factors = TradeoffFactorRegistry.get_factors(d.decision_type)
        risk_coeff = factors.get("risk_reduction_coefficient", 0.5)

        op_score = 10.0 * (1.0 - risk_coeff)
        if op_score < 3.0:
            impact_level = DecisionImpact.LOW
        elif op_score < 6.0:
            impact_level = DecisionImpact.MEDIUM
        elif op_score < 8.0:
            impact_level = DecisionImpact.HIGH
        else:
            impact_level = DecisionImpact.CRITICAL

        confidence = 0.5 + 0.45 * (centrality / (centrality + 1.0))

        return DecisionImpactResponse(
            decision_impact=impact_level,
            operational_impact_score=op_score,
            confidence_score=confidence,
            affected_assets=[d.target_entity_id],
        )

    @classmethod
    def calculate(cls) -> None:
        """Calculate cost-benefit-risk tradeoffs for all active decision recommendations."""
        decisions = SecurityDecisionService.get_all_decisions()
        centrality_map = SecurityIntelligenceGraphService.calculate_centrality()

        # Find matching graph nodes for centrality lookup
        nodes = SecurityIntelligenceGraphService.get_all_nodes()
        entity_to_centrality = {}
        for n in nodes:
            entity_to_centrality[n.entity_id] = centrality_map.get(n.node_id, 1.0)

        for d in decisions:
            # Enforce Decision Terminal State Rule: tradeoff mapping updates cannot reactivate ARCHIVED decisions
            if d.status.value == "ARCHIVED":
                continue

            centrality = entity_to_centrality.get(d.target_entity_id, 1.0)

            # Assign computed matrices
            d.tradeoff_matrix = cls.calculate_tradeoff(d, centrality)
            d.impact_metrics = cls.calculate_impact(d, centrality)
