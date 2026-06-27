import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ExerciseSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExerciseStatus(str, Enum):
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"


class ExerciseType(str, Enum):
    ATTACK_SIMULATION = "ATTACK_SIMULATION"
    ADVERSARY_EMULATION = "ADVERSARY_EMULATION"
    CONTROL_VALIDATION = "CONTROL_VALIDATION"
    DETECTION_VALIDATION = "DETECTION_VALIDATION"


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class PurpleTeamExerciseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    exercise_id: uuid.UUID
    exercise_fingerprint: str
    name: str
    description: str
    exercise_type: ExerciseType
    severity: ExerciseSeverity
    status: ExerciseStatus
    owner: Optional[str] = None
    scope_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ValidationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    validation_id: uuid.UUID
    exercise_id: uuid.UUID
    technique_id: str
    validation_status: ValidationStatus
    expected_detection: bool
    actual_detection: bool
    coverage_gap: bool
    created_at: datetime
    updated_at: datetime


class PurpleTeamFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    finding_id: uuid.UUID
    exercise_id: uuid.UUID
    technique_id: str
    severity: ExerciseSeverity
    gap_type: str
    description: str
    created_at: datetime


class PurpleTeamHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    exercise_id: uuid.UUID
    timestamp: datetime
    event_type: str
    details: str
