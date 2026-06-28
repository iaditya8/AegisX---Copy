from src.domain.entities.security_intelligence_graph import EdgeType


class GraphRelationshipWeightRegistry:
    # Pre-seeded: maps EdgeType to float baseline connection weight
    _weights = {
        EdgeType.AFFECTS: 3.0,
        EdgeType.CONTAINED_IN: 1.0,
        EdgeType.MITIGATES: 1.5,
        EdgeType.MAPS_TO: 2.0,
        EdgeType.CORRELATES_WITH: 1.5,
        EdgeType.TRIGGERS: 2.5,
    }

    @classmethod
    def get_weight(cls, edge_type: EdgeType) -> float:
        """Retrieve pre-seeded edge weight."""
        return cls._weights.get(edge_type, 1.0)
