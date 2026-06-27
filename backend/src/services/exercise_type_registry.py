from typing import Any, Set, Union
from src.domain.entities.purple_team import ExerciseType


class ExerciseTypeRegistry:
    @classmethod
    def get_registered_types(cls) -> Set[ExerciseType]:
        """Retrieve all registered exercise types."""
        return set(ExerciseType)

    @classmethod
    def is_valid_type(cls, exercise_type: Any) -> bool:
        """Check if an exercise type is registered/valid."""
        if isinstance(exercise_type, ExerciseType):
            return True
        try:
            ExerciseType(str(exercise_type).upper())
            return True
        except ValueError:
            return False

    @classmethod
    def resolve_type(cls, exercise_type: Union[ExerciseType, str]) -> ExerciseType:
        """Resolve string/enum to ExerciseType, defaulting to ATTACK_SIMULATION."""
        if isinstance(exercise_type, ExerciseType):
            return exercise_type
        try:
            return ExerciseType(str(exercise_type).upper())
        except ValueError:
            return ExerciseType.ATTACK_SIMULATION
