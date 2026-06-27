from typing import Set

from src.domain.entities.threat_intelligence import ThreatFeedType


class ThreatFeedRegistry:
    FEEDS = {
        ThreatFeedType.INTERNAL: "Internal proprietary intelligence feed",
        ThreatFeedType.COMMUNITY: "Open source community shared feed",
        ThreatFeedType.COMMERCIAL: "Premium commercial threat intelligence feed",
    }

    @classmethod
    def get_registered_feeds(cls) -> Set[ThreatFeedType]:
        """Retrieve all pre-seeded feeds."""
        return set(cls.FEEDS.keys())

    @classmethod
    def is_valid_feed(cls, feed: ThreatFeedType) -> bool:
        """Check if a feed is registered."""
        return feed in cls.FEEDS
