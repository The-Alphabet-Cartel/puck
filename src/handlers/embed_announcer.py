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
Embed announcer handler (STUB). Provides the interface for future stream
announcement embeds. Hooks are called by StreamMonitor but perform no
action in v1.0.

Future v1.1 functionality:
  - create_announcement(): Post embed to announcement channel when live
  - update_screenshot(): Update thumbnail every 5 minutes while live
  - delete_announcement(): Remove embed when stream ends
----------------------------------------------------------------------------
FILE VERSION: v1.1.0
LAST MODIFIED: 2026-02-26
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

from src.managers.config_manager import ConfigManager
from src.managers.logging_config_manager import LoggingConfigManager
from src.models.stream_status import StreamStatus


class EmbedAnnouncer:
    """Stub handler for future stream announcement embeds."""

    def __init__(
        self,
        config_manager: ConfigManager,
        logging_manager: LoggingConfigManager,
    ) -> None:
        self._config = config_manager
        self._log = logging_manager.get_logger("embed_announcer")
        self._log.debug("🔍 EmbedAnnouncer initialized (stub — no-op in v1.0)")

    async def create_announcement(self, status: StreamStatus) -> None:
        """POST: Create a stream announcement embed. (v1.1)"""
        self._log.debug(
            f"🔍 [STUB] Would announce: {status.display_name} live on {status.platform}"
        )

    async def update_screenshot(self, status: StreamStatus) -> None:
        """PATCH: Update the stream thumbnail. (v1.1)"""
        pass

    async def delete_announcement(self, status: StreamStatus) -> None:
        """DELETE: Remove the stream announcement. (v1.1)"""
        self._log.debug(
            f"🔍 [STUB] Would remove announcement for {status.display_name}"
        )


def create_embed_announcer(
    config_manager: ConfigManager,
    logging_manager: LoggingConfigManager,
) -> EmbedAnnouncer:
    """Factory function — MANDATORY. Never call EmbedAnnouncer directly."""
    return EmbedAnnouncer(
        config_manager=config_manager,
        logging_manager=logging_manager,
    )


__all__ = ["EmbedAnnouncer", "create_embed_announcer"]
