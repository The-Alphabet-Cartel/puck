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
Stream state manager for puck-bot. Persists stream live/offline state to
JSON for restart survival, and compares current API results against previous
state to detect WENT_LIVE and WENT_OFFLINE transitions.
----------------------------------------------------------------------------
FILE VERSION: v1.1.0
LAST MODIFIED: 2026-02-26
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

import json
from pathlib import Path
from typing import Optional

from src.managers.config_manager import ConfigManager
from src.managers.logging_config_manager import LoggingConfigManager
from src.models.stream_status import StreamStatus

STATE_FILE = "/app/data/stream_state.json"


class StreamStateManager:
    """Manages persistent stream state and detects live/offline transitions."""

    def __init__(
        self,
        config_manager: ConfigManager,
        logging_manager: LoggingConfigManager,
        state_file: str = STATE_FILE,
    ) -> None:
        self._config = config_manager
        self._log = logging_manager.get_logger("stream_state_manager")
        self._state_file = Path(state_file)
        self._previous: dict[str, StreamStatus] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load previous state from JSON file. Handles missing/corrupt files gracefully."""
        if not self._state_file.exists():
            self._log.debug("🔍 No previous state file — starting fresh")
            return
        try:
            with open(self._state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, entry in data.get("streams", {}).items():
                self._previous[key] = StreamStatus.from_dict(entry)
            self._log.debug(f"🔍 Loaded previous state: {len(self._previous)} stream(s)")
        except (json.JSONDecodeError, OSError, KeyError) as e:
            self._log.warning(f"⚠️ Could not load state file: {e} — starting fresh")
            self._previous = {}

    def persist(self, current: dict[str, StreamStatus]) -> None:
        """Write current state to JSON file for restart survival."""
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "streams": {
                    key: status.to_dict() for key, status in current.items()
                }
            }
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._previous = current.copy()
        except OSError as e:
            self._log.error(f"❌ Failed to persist state: {e}")

    def compare(
        self,
        current_live: list[StreamStatus],
        tracked_streams: list[dict],
    ) -> tuple[list[StreamStatus], list[StreamStatus]]:
        """
        Compare current API results against previous state.

        Args:
            current_live: StreamStatus objects for currently live streams
            tracked_streams: Full list of tracked stream configs

        Returns:
            (went_live, went_offline) — lists of StreamStatus objects
        """
        # Build a set of currently live stream keys (platform:username)
        current_keys: dict[str, StreamStatus] = {}
        for status in current_live:
            key = f"{status.platform}:{status.platform_username}"
            current_keys[key] = status

        # Build set of all tracked stream keys
        all_tracked_keys: set[str] = set()
        for stream_cfg in tracked_streams:
            if stream_cfg.get("twitch_username"):
                all_tracked_keys.add(f"twitch:{stream_cfg['twitch_username'].lower()}")
            if stream_cfg.get("youtube_channel_id"):
                all_tracked_keys.add(f"youtube:{stream_cfg['youtube_channel_id']}")

        previous_live_keys = {
            k for k, v in self._previous.items() if v.is_live
        }

        # Detect transitions
        went_live: list[StreamStatus] = []
        went_offline: list[StreamStatus] = []

        for key, status in current_keys.items():
            if key not in previous_live_keys:
                went_live.append(status)
                self._log.info(
                    f"ℹ️ 🔴 WENT LIVE: {status.display_name} "
                    f"on {status.platform} — {status.stream_title}"
                )

        for key in previous_live_keys:
            if key not in current_keys and key in all_tracked_keys:
                prev = self._previous[key]
                prev.is_live = False
                went_offline.append(prev)
                self._log.info(
                    f"ℹ️ ⚫ WENT OFFLINE: {prev.display_name} on {prev.platform}"
                )

        # Build full current state (live + tracked-but-offline)
        full_state: dict[str, StreamStatus] = {}
        for key, status in current_keys.items():
            full_state[key] = status
        for key in all_tracked_keys:
            if key not in full_state and key in self._previous:
                offline = self._previous[key]
                offline.is_live = False
                full_state[key] = offline

        # Persist and update previous
        self.persist(full_state)
        return went_live, went_offline

    def get_previous_state(self) -> dict[str, StreamStatus]:
        """Return the previous state dict (for reconciliation)."""
        return self._previous.copy()


def create_stream_state_manager(
    config_manager: ConfigManager,
    logging_manager: LoggingConfigManager,
    state_file: str = STATE_FILE,
) -> StreamStateManager:
    """Factory function — MANDATORY. Never call StreamStateManager directly."""
    return StreamStateManager(
        config_manager=config_manager,
        logging_manager=logging_manager,
        state_file=state_file,
    )


__all__ = ["StreamStateManager", "create_stream_state_manager"]
