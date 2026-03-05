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
ConfigManager for puck-bot. Loads the three-layer config stack: JSON
defaults → .env overrides → Docker Secrets. Also loads the separate
tracked_streams.json for stream-to-user mappings.
----------------------------------------------------------------------------
FILE VERSION: v1.2.0
LAST MODIFIED: 2026-03-02
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("puck-bot.config_manager")


class ConfigManager:
    """Loads and provides access to puck-bot configuration."""

    def __init__(
        self,
        config_path: str = "/app/src/config/puck_config.json",
        streams_path: str = "/app/src/config/tracked_streams.json",
    ) -> None:
        self._config: dict[str, Any] = {}
        self._streams: list[dict[str, Any]] = []
        self._streams_path = streams_path
        self._load_json(config_path)
        self._load_streams(streams_path)
        self._apply_env_overrides()
        self._apply_secret_overrides()

    # -------------------------------------------------------------------------
    # Layer 1: JSON defaults
    # -------------------------------------------------------------------------
    def _load_json(self, config_path: str) -> None:
        path = Path(config_path)
        if not path.exists():
            log.warning(
                f"⚠️ Config file not found at {config_path} — using empty defaults"
            )
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            log.debug(f"🔍 Loaded config from {config_path}")
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"❌ Failed to load config JSON: {e} — using empty defaults")

    def _load_streams(self, streams_path: str) -> None:
        path = Path(streams_path)
        if not path.exists():
            log.warning(
                f"⚠️ Streams file not found at {streams_path} — no streams tracked"
            )
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._streams = data.get("streams", [])
            log.debug(f"🔍 Loaded {len(self._streams)} tracked stream(s)")
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"❌ Failed to load streams JSON: {e} — no streams tracked")

    # -------------------------------------------------------------------------
    # Layer 2: .env overrides (non-sensitive)
    # -------------------------------------------------------------------------
    def _apply_env_overrides(self) -> None:
        env_map = {
            "LOG_LEVEL": ("logging", "level"),
            "LOG_FORMAT": ("logging", "format"),
            "PUCK_LOG_FILE": ("logging", "file"),
            "LOG_CONSOLE": ("logging", "console"),
            "COMMAND_PREFIX": ("bot", "command_prefix"),
            "PUCK_GUILD_ID": ("fluxer", "guild_id"),
            "PUCK_LIVE_ROLE_ID": ("fluxer", "live_role_id"),
            "PUCK_ANNOUNCE_CHANNEL_ID": ("fluxer", "announcement_channel_id"),
            "PUCK_POLL_INTERVAL": ("polling", "interval_seconds"),
            "PUCK_YOUTUBE_POLL_MULTIPLIER": ("youtube", "poll_multiplier"),
        }
        for env_key, (section, key) in env_map.items():
            value = os.environ.get(env_key)
            if value is not None:
                self._config.setdefault(section, {})[key] = value
                log.debug(f"🔍 Applied env override: {env_key}")

    # -------------------------------------------------------------------------
    # Layer 3: Docker Secret overrides (sensitive)
    # -------------------------------------------------------------------------
    def _apply_secret_overrides(self) -> None:
        secret_map = {
            "TOKEN_FILE": ("bot", "token", "/run/secrets/puck_token"),
            "TWITCH_CLIENT_ID_FILE": (
                "twitch",
                "client_id",
                "/run/secrets/twitch_client_id",
            ),
            "TWITCH_CLIENT_SECRET_FILE": (
                "twitch",
                "client_secret",
                "/run/secrets/twitch_client_secret",
            ),
            "YOUTUBE_API_KEY_FILE": (
                "youtube",
                "api_key",
                "/run/secrets/youtube_api_key",
            ),
        }
        for env_key, (section, key, default_path) in secret_map.items():
            secret_path = os.environ.get(env_key, default_path)
            value = self._read_secret_file(secret_path)
            if value:
                self._config.setdefault(section, {})[key] = value
                log.debug(f"🔍 Loaded secret: {env_key}")
            else:
                log.warning(f"⚠️ Secret not found for {env_key} at {secret_path}")

    def _read_secret_file(self, path: str) -> Optional[str]:
        secret_path = Path(path)
        if not secret_path.exists():
            return None
        try:
            return secret_path.read_text(encoding="utf-8").strip()
        except OSError as e:
            log.error(f"❌ Could not read secret {path}: {e}")
            return None

    # -------------------------------------------------------------------------
    # Accessors
    # -------------------------------------------------------------------------
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """Get a config value by section and key."""
        return self._config.get(section, {}).get(key, fallback)

    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """Get a config value as an integer with safe fallback."""
        value = self.get(section, key, fallback)
        try:
            return int(value)
        except (TypeError, ValueError):
            log.warning(
                f"⚠️ [{section}.{key}] expected int, got {value!r} — using {fallback}"
            )
            return fallback

    def get_bool(self, section: str, key: str, fallback: bool = True) -> bool:
        """Get a config value as a boolean with safe fallback."""
        value = self.get(section, key, fallback)
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")

    def get_token(self) -> str:
        """Get the Fluxer bot token."""
        return self.get("bot", "token", "")

    def get_twitch_client_id(self) -> str:
        """Get the Twitch application client ID."""
        return self.get("twitch", "client_id", "")

    def get_twitch_client_secret(self) -> str:
        """Get the Twitch application client secret."""
        return self.get("twitch", "client_secret", "")

    def get_youtube_api_key(self) -> str:
        """Get the YouTube Data API v3 key."""
        return self.get("youtube", "api_key", "")

    def get_tracked_streams(self) -> list[dict[str, Any]]:
        """Get the list of tracked stream mappings."""
        return self._streams

    def get_guild_id(self) -> str:
        """Get the Fluxer guild ID."""
        return str(self.get("fluxer", "guild_id", ""))

    def get_live_role_id(self) -> str:
        """Get the Live role ID for Fluxer."""
        return str(self.get("fluxer", "live_role_id", ""))

    def get_poll_interval(self) -> int:
        """Get polling interval in seconds (default 90)."""
        return self.get_int("polling", "interval_seconds", 90)

    def get_youtube_poll_multiplier(self) -> int:
        """Get YouTube poll multiplier (default 3)."""
        return self.get_int("youtube", "poll_multiplier", 3)

    def get_announcement_channel_id(self) -> str:
        """Get the announcement channel ID (future use)."""
        return str(self.get("fluxer", "announcement_channel_id", ""))

    def get_channel_name_live(self) -> str:
        """Get the channel name to use when someone is streaming."""
        return str(self.get("fluxer", "channel_name_live", "🟢 Live Now"))

    def get_channel_name_idle(self) -> str:
        """Get the channel name to use when nobody is streaming."""
        return str(self.get("fluxer", "channel_name_idle", "Live Now"))

    def reload_streams(self) -> list[dict[str, Any]]:
        """Re-read tracked_streams.json from disk. Used by ConfigWatcher hot-reload."""
        self._load_streams(self._streams_path)
        log.info(f"ℹ️ Reloaded tracked streams: {len(self._streams)} stream(s)")
        return self._streams


def create_config_manager(
    config_path: str = "/app/src/config/puck_config.json",
    streams_path: str = "/app/src/config/tracked_streams.json",
) -> ConfigManager:
    """Factory function — MANDATORY. Never call ConfigManager directly."""
    return ConfigManager(config_path=config_path, streams_path=streams_path)


__all__ = ["ConfigManager", "create_config_manager"]
