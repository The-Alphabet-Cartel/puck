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
Stream monitor handler. Runs the background polling loop that checks Twitch
and YouTube for live streams, compares against persisted state, and toggles
the configured "Live" role on Fluxer for community members.
----------------------------------------------------------------------------
FILE VERSION: v1.1.0
LAST MODIFIED: 2026-02-26
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

import asyncio
import traceback

import fluxer

from src.handlers.embed_announcer import EmbedAnnouncer
from src.managers.config_manager import ConfigManager
from src.managers.logging_config_manager import LoggingConfigManager
from src.managers.stream_state_manager import StreamStateManager
from src.managers.twitch_manager import TwitchManager
from src.managers.youtube_manager import YouTubeManager
from src.models.stream_status import StreamStatus


class StreamMonitor:
    """Monitors Twitch/YouTube streams and toggles Live role on Fluxer."""

    def __init__(
        self,
        bot: fluxer.Bot,
        config_manager: ConfigManager,
        logging_manager: LoggingConfigManager,
        twitch_manager: TwitchManager,
        youtube_manager: YouTubeManager,
        state_manager: StreamStateManager,
        embed_announcer: EmbedAnnouncer,
    ) -> None:
        self._bot = bot
        self._config = config_manager
        self._log = logging_manager.get_logger("stream_monitor")
        self._twitch = twitch_manager
        self._youtube = youtube_manager
        self._state = state_manager
        self._embed = embed_announcer
        self._poll_count: int = 0
        self._youtube_cycle: int = 0
        self._running: bool = False

    # -------------------------------------------------------------------------
    # User-to-Stream Mapping
    # -------------------------------------------------------------------------
    def _build_mappings(self) -> tuple[dict[str, str], dict[str, str]]:
        """
        Build lookup dicts from tracked_streams config.

        Returns:
            twitch_map: {twitch_username: fluxer_user_id}
            youtube_map: {youtube_channel_id: fluxer_user_id}
        """
        twitch_map: dict[str, str] = {}
        youtube_map: dict[str, str] = {}

        for stream in self._config.get_tracked_streams():
            fuid = stream.get("fluxer_user_id", "")
            if stream.get("twitch_username"):
                twitch_map[stream["twitch_username"].lower()] = fuid
            if stream.get("youtube_channel_id"):
                youtube_map[stream["youtube_channel_id"]] = fuid

        return twitch_map, youtube_map

    # -------------------------------------------------------------------------
    # Role Toggle
    # -------------------------------------------------------------------------
    async def _add_live_role(self, status: StreamStatus) -> None:
        """Add the Live role to a Fluxer member."""
        guild_id = self._config.get_guild_id()
        role_id = self._config.get_live_role_id()
        if not guild_id or not role_id:
            self._log.warning("⚠️ Guild ID or Live Role ID not configured — skipping role add")
            return
        try:
            guild = await self._bot.fetch_guild(int(guild_id))
            member = await guild.fetch_member(int(status.fluxer_user_id))

            # Check if member already has the role
            if int(role_id) in member.roles:
                self._log.debug(f"🔍 {status.display_name} already has Live role")
                return

            await member.add_role(
                int(role_id),
                guild_id=int(guild_id),
                reason=f"Puck: {status.display_name} went live on {status.platform}",
            )
            self._log.success(
                f"Added Live role to {status.display_name} "
                f"({status.platform}: {status.stream_title})"
            )
        except fluxer.Forbidden:
            self._log.error(
                f"❌ Missing permissions to add Live role to {status.display_name} "
                f"— check role hierarchy"
            )
        except Exception as e:
            self._log.error(f"❌ Failed to add Live role to {status.display_name}: {e}")

    async def _remove_live_role(self, status: StreamStatus) -> None:
        """Remove the Live role from a Fluxer member."""
        guild_id = self._config.get_guild_id()
        role_id = self._config.get_live_role_id()
        if not guild_id or not role_id:
            return
        try:
            guild = await self._bot.fetch_guild(int(guild_id))
            member = await guild.fetch_member(int(status.fluxer_user_id))

            if int(role_id) not in member.roles:
                self._log.debug(f"🔍 {status.display_name} doesn't have Live role")
                return

            await member.remove_role(
                int(role_id),
                guild_id=int(guild_id),
                reason=f"Puck: {status.display_name} went offline on {status.platform}",
            )
            self._log.success(f"Removed Live role from {status.display_name}")
        except fluxer.Forbidden:
            self._log.error(
                f"❌ Missing permissions to remove Live role from {status.display_name}"
            )
        except Exception as e:
            self._log.error(f"❌ Failed to remove Live role from {status.display_name}: {e}")

    # -------------------------------------------------------------------------
    # Polling Loop
    # -------------------------------------------------------------------------
    async def poll_once(self) -> None:
        """Execute a single poll cycle."""
        self._poll_count += 1
        self._youtube_cycle += 1
        twitch_map, youtube_map = self._build_mappings()
        tracked_streams = self._config.get_tracked_streams()

        # --- Twitch (every cycle) ---
        twitch_usernames = list(twitch_map.keys())
        twitch_live = await self._twitch.check_streams(twitch_usernames)

        # Map fluxer_user_id onto results
        for status in twitch_live:
            fuid = twitch_map.get(status.platform_username, "")
            status.fluxer_user_id = fuid

        # --- YouTube (every N cycles) ---
        youtube_live: list[StreamStatus] = []
        yt_multiplier = self._config.get_youtube_poll_multiplier()
        if youtube_map and self._youtube_cycle >= yt_multiplier:
            self._youtube_cycle = 0
            youtube_ids = list(youtube_map.keys())
            youtube_live = await self._youtube.check_streams(youtube_ids)

            for status in youtube_live:
                fuid = youtube_map.get(status.platform_username, "")
                status.fluxer_user_id = fuid

        # --- Compare & Act ---
        all_live = twitch_live + youtube_live
        went_live, went_offline = self._state.compare(all_live, tracked_streams)

        for status in went_live:
            if status.fluxer_user_id:
                await self._add_live_role(status)
                await self._embed.create_announcement(status)

        for status in went_offline:
            if status.fluxer_user_id:
                await self._remove_live_role(status)
                await self._embed.delete_announcement(status)

        if self._poll_count % 10 == 0:
            live_count = len(all_live)
            self._log.debug(
                f"🔍 Poll #{self._poll_count}: {live_count} live stream(s) across "
                f"{len(twitch_usernames)} Twitch / {len(youtube_map)} YouTube"
            )

    async def start(self) -> None:
        """Start the background polling loop."""
        interval = self._config.get_poll_interval()
        self._running = True
        self._log.success(
            f"Stream monitor started — polling every {interval}s "
            f"(YouTube every {interval * self._config.get_youtube_poll_multiplier()}s)"
        )

        while self._running:
            try:
                await self.poll_once()
            except Exception as e:
                self._log.error(
                    f"❌ Poll cycle failed: {e}\n{traceback.format_exc()}"
                )
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False
        self._log.info("ℹ️ Stream monitor stopping")


def create_stream_monitor(
    bot: fluxer.Bot,
    config_manager: ConfigManager,
    logging_manager: LoggingConfigManager,
    twitch_manager: TwitchManager,
    youtube_manager: YouTubeManager,
    state_manager: StreamStateManager,
    embed_announcer: EmbedAnnouncer,
) -> StreamMonitor:
    """Factory function — MANDATORY. Never call StreamMonitor directly."""
    return StreamMonitor(
        bot=bot,
        config_manager=config_manager,
        logging_manager=logging_manager,
        twitch_manager=twitch_manager,
        youtube_manager=youtube_manager,
        state_manager=state_manager,
        embed_announcer=embed_announcer,
    )


__all__ = ["StreamMonitor", "create_stream_monitor"]
