from src.domain.entities.security_intelligence_graph import EdgeType


class GraphEdgeTypeRegistry:
    @classmethod
    def validate(cls, edge_type: str) -> bool:
        """Validate if edge_type is a valid GRC Graph EdgeType."""
        try:
            EdgeType(edge_type)
            return True
        except ValueError:
            return False
