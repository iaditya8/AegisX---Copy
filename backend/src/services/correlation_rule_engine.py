from typing import List, Dict, Any
from src.infrastructure.database.models import CorrelationRule


class CorrelationRuleEngine:
    @classmethod
    def evaluate_expression(cls, expression: dict, context: Dict[str, Any]) -> bool:
        """Recursively evaluate rule conditions against a signal context dictionary."""
        if not isinstance(expression, dict):
            return False

        operator = expression.get("operator")
        conditions = expression.get("conditions")

        if operator and isinstance(conditions, list):
            op_upper = operator.upper()
            if op_upper == "AND":
                return all(cls.evaluate_expression(c, context) for c in conditions)
            elif op_upper == "OR":
                return any(cls.evaluate_expression(c, context) for c in conditions)
            return False

        # Leaf condition evaluation
        signal = expression.get("signal")
        op = expression.get("operator")
        expected_val = expression.get("value")

        if not signal or not op:
            return False

        # Resolve signal value from context
        actual_val = context.get(signal)
        if actual_val is None:
            return False

        # Resolve expected value if it points to a context key
        if isinstance(expected_val, str) and expected_val in context:
            expected_val = context.get(expected_val)

        op_upper = op.upper()
        try:
            if op_upper in ("EQUALS", "=="):
                return str(actual_val).lower() == str(expected_val).lower()
            elif op_upper in ("NOTEQUALS", "!="):
                return str(actual_val).lower() != str(expected_val).lower()
            elif op_upper in ("GT", ">"):
                return float(actual_val) > float(expected_val)
            elif op_upper in ("LT", "<"):
                return float(actual_val) < float(expected_val)
            elif op_upper in ("GTE", ">="):
                return float(actual_val) >= float(expected_val)
            elif op_upper in ("LTE", "<="):
                return float(actual_val) <= float(expected_val)
            elif op_upper == "IN":
                if isinstance(actual_val, (list, tuple, set)):
                    if isinstance(expected_val, (list, tuple, set)):
                        return any(x in expected_val for x in actual_val)
                    return any(str(x) in str(expected_val) for x in actual_val)
                if isinstance(expected_val, (list, tuple, set)):
                    return actual_val in expected_val or str(actual_val) in [str(x) for x in expected_val]
                return str(actual_val) in str(expected_val)
            elif op_upper == "CONTAINS":
                if isinstance(actual_val, (list, tuple, set)):
                    if isinstance(expected_val, (list, tuple, set)):
                        return any(x in actual_val for x in expected_val)
                    return expected_val in actual_val or str(expected_val) in [str(x) for x in actual_val]
                return str(expected_val) in str(actual_val)
        except Exception:
            return False

        return False

    @classmethod
    def evaluate_rules(cls, rules: List[CorrelationRule], context: Dict[str, Any]) -> List[CorrelationRule]:
        """Evaluate a list of rules against the signal context and return matching rules."""
        matched = []
        for rule in rules:
            if cls.evaluate_expression(rule.condition_expression, context):
                matched.append(rule)
        return matched
