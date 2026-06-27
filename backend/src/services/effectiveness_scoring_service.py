from typing import List, Dict, Any
from src.domain.entities.control_validation import ValidationStatus


class EffectivenessScoringService:
    @classmethod
    def calculate_effectiveness(
        cls, validations: List[Any], attack_techniques: List[str]
    ) -> Dict[str, float]:
        """Deterministically calculate effectiveness, validation, coverage, and health scores."""
        # 1. Validation score
        if not validations:
            val_score = 100.0
        else:
            total_points = 0.0
            for v in validations:
                status_str = str(v.validation_status.value).upper()
                if "PASS" in status_str:
                    total_points += 100.0
                elif "PART" in status_str:
                    total_points += 50.0
                else:
                    total_points += 0.0
            val_score = round(total_points / len(validations), 2)

        # 2. Attack coverage score
        if not attack_techniques or not validations:
            cov_score = 100.0
        else:
            # Find techniques covered by at least one PASSED validation
            passed_techs = set()
            for v in validations:
                status_str = str(v.validation_status.value).upper()
                if "PASS" in status_str and v.attack_technique in attack_techniques:
                    passed_techs.add(v.attack_technique)
            cov_score = round((len(passed_techs) / len(attack_techniques)) * 100.0, 2)

        # 3. Health score: weighted blend
        health_score = round(val_score * 0.7 + cov_score * 0.3, 2)

        return {
            "validation_score": val_score,
            "attack_coverage_score": cov_score,
            "control_health_score": health_score,
            "effectiveness_score": health_score,
        }
