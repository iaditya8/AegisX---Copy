import uuid
from typing import Dict, List, Optional

from src.domain.entities.threat_intelligence import IOCSeverity, ThreatActorStatus


class ThreatActorProfile:
    def __init__(
        self,
        actor_id: uuid.UUID,
        name: str,
        description: str,
        aliases: List[str],
        severity: IOCSeverity,
        status: ThreatActorStatus,
    ):
        self.actor_id = actor_id
        self.name = name
        self.description = description
        self.aliases = aliases or []
        self.severity = severity
        self.status = status


class ThreatActorRegistry:
    # Pre-seeded threat actors
    _actors: Dict[str, ThreatActorProfile] = {
        "APT29": ThreatActorProfile(
            actor_id=uuid.UUID("29292929-2929-2929-2929-292929292929"),
            name="APT29",
            description="Cozy Bear, Nobilium, Russian state-sponsored cyber espionage group.",
            aliases=["Cozy Bear", "Nobilium", "YTTRIUM"],
            severity=IOCSeverity.CRITICAL,
            status=ThreatActorStatus.ACTIVE,
        ),
        "APT28": ThreatActorProfile(
            actor_id=uuid.UUID("28282828-2828-2828-2828-282828282828"),
            name="APT28",
            description="Fancy Bear, Sofacy, Russian military intelligence cyber espionage group.",
            aliases=["Fancy Bear", "Sofacy", "Pawn Storm"],
            severity=IOCSeverity.HIGH,
            status=ThreatActorStatus.ACTIVE,
        ),
        "Lazarus": ThreatActorProfile(
            actor_id=uuid.UUID("88888888-8888-8888-8888-888888888888"),
            name="Lazarus",
            description="Lazarus Group, North Korean state-sponsored cyber warfare group.",
            aliases=["Lazarus Group", "Hidden Cobra", "Guardians of Peace"],
            severity=IOCSeverity.CRITICAL,
            status=ThreatActorStatus.ACTIVE,
        ),
        "FIN7": ThreatActorProfile(
            actor_id=uuid.UUID("77777777-7777-7777-7777-777777777777"),
            name="FIN7",
            description="Financial motivated cybercriminal group targeting retail and hospitality.",
            aliases=["Carbanak", "Navigator Group"],
            severity=IOCSeverity.HIGH,
            status=ThreatActorStatus.ACTIVE,
        ),
    }

    @classmethod
    def get_actor_by_name(cls, name: str) -> Optional[ThreatActorProfile]:
        """Case-insensitive or alias lookup for an actor profile."""
        name_upper = name.upper()
        for k, v in cls._actors.items():
            if k.upper() == name_upper or name_upper in [a.upper() for a in v.aliases]:
                return v
        return None

    @classmethod
    def get_all_profiles(cls) -> List[ThreatActorProfile]:
        """Retrieve all pre-seeded actor profiles."""
        return list(cls._actors.values())
