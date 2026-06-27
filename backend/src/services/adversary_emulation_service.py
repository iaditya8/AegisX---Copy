from typing import Dict, List, Optional


class AdversaryEmulationService:
    # In-memory mapping of threat actors to their signature techniques
    ACTOR_PROFILES = {
        "APT29": ["T1059", "T1078"],
        "APT28": ["T1027", "T1105"],
        "LAZARUS": ["T1047", "T1055"],
        "FIN7": ["T1059", "T1562"],
    }

    @classmethod
    def get_techniques_for_actor(cls, actor_name: str) -> List[str]:
        """Retrieve signature techniques mapped to a threat actor profile (case-insensitive)."""
        name_upper = str(actor_name).strip().upper()
        return cls.ACTOR_PROFILES.get(name_upper, [])

    @classmethod
    def get_actors_for_technique(cls, technique_id: str) -> List[str]:
        """Retrieve threat actors associated with a given technique."""
        tech_upper = str(technique_id).strip().upper()
        actors = []
        for actor, techniques in cls.ACTOR_PROFILES.items():
            if tech_upper in techniques:
                # Return normalized casing matching our actors
                if actor == "LAZARUS":
                    actors.append("Lazarus")
                else:
                    actors.append(actor)
        return actors
