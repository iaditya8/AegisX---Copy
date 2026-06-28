from src.domain.entities.security_intelligence_graph import NodeType


class GraphNodeTypeRegistry:
    @classmethod
    def validate(cls, node_type: str) -> bool:
        """Validate if node_type is a valid GRC Graph NodeType."""
        try:
            NodeType(node_type)
            return True
        except ValueError:
            return False
