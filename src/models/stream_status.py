"""
============================================================================
Bragi: Bot Infrastructure for The Alphabet Cartel
The Alphabet Cartel - https://fluxer.gg/yGJfJH5C | alphabetcartel.net
============================================================================

MISSION - NEVER TO BE VIOLATED:
    Welcome  → Greet and orient new members to our chosen family
    Moderate → Support staff with tools that keep our space safe
    Support  → Connect members to resources, information, and each other
    Sustain  → Run reliably so our community always has what it needs

============================================================================
Data models for stream status tracking. Defines the StreamStatus dataclass
used throughout Puck to represent a tracked user's live/offline state.
----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-02-26
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class StreamStatus:
    """Represents the live status of a tracked community member's stream."""

    fluxer_user_id: str
    display_name: str
    platform: str                              # "twitch" or "youtube"
    platform_username: str                     # Twitch username or YouTube channel ID
    is_live: bool = False
    stream_title: Optional[str] = None
    game_or_category: Optional[str] = None
    viewer_count: int = 0
    thumbnail_url: Optional[str] = None
    stream_url: Optional[str] = None
    started_at: Optional[datetime] = None
    last_checked: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        """Serialize to dict for JSON persistence."""
        return {
            "fluxer_user_id": self.fluxer_user_id,
            "display_name": self.display_name,
            "platform": self.platform,
            "platform_username": self.platform_username,
            "is_live": self.is_live,
            "stream_title": self.stream_title,
            "game_or_category": self.game_or_category,
            "viewer_count": self.viewer_count,
            "thumbnail_url": self.thumbnail_url,
            "stream_url": self.stream_url,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_checked": self.last_checked.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StreamStatus":
        """Deserialize from dict (JSON persistence)."""
        started_at = None
        if data.get("started_at"):
            started_at = datetime.fromisoformat(data["started_at"])
        last_checked = datetime.now(timezone.utc)
        if data.get("last_checked"):
            last_checked = datetime.fromisoformat(data["last_checked"])
        return cls(
            fluxer_user_id=data["fluxer_user_id"],
            display_name=data["display_name"],
            platform=data["platform"],
            platform_username=data["platform_username"],
            is_live=data.get("is_live", False),
            stream_title=data.get("stream_title"),
            game_or_category=data.get("game_or_category"),
            viewer_count=data.get("viewer_count", 0),
            thumbnail_url=data.get("thumbnail_url"),
            stream_url=data.get("stream_url"),
            started_at=started_at,
            last_checked=last_checked,
        )


__all__ = ["StreamStatus"]
