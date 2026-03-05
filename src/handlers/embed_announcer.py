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
Embed announcer for puck-bot. Posts rich embeds to the announcement channel
when a Twitch streamer goes live, updates the thumbnail every 5 minutes,
and deletes the announcement when the stream ends.

Twitch-only: YouTube streams do not get embed announcements.

Uses the Fluxer REST API directly via httpx for embed operations.
----------------------------------------------------------------------------
FILE VERSION: v2.0.0
LAST MODIFIED: 2026-03-04
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from src.managers.config_manager import ConfigManager
from src.managers.logging_config_manager import LoggingConfigManager
from src.models.stream_status import StreamStatus

FLUXER_API_BASE = "https://api.fluxer.app/v1"
EMBED_COLOR = 0xE0885A  # TAC orange (--tac-orange) — Puck's accent
ANNOUNCEMENTS_STATE_FILE = "/app/data/announcements.json"
UPDATE_INTERVAL_SECONDS = 300  # 5 minutes between thumbnail refreshes


class EmbedAnnouncer:
    """Posts and manages Twitch stream announcement embeds in Fluxer."""

    def __init__(
        self,
        config_manager: ConfigManager,
        logging_manager: LoggingConfigManager,
    ) -> None:
        self._config = config_manager
        self._log = logging_manager.get_logger("embed_announcer")
        self._token = config_manager.get_token()
        self._channel_id = config_manager.get_announcement_channel_id()
        self._http: Optional[httpx.AsyncClient] = None

        # Maps "twitch:{username}" -> {"message_id": str, "last_updated": float}
        self._active: dict[str, dict[str, Any]] = {}
        self._load_state()

        if not self._channel_id:
            self._log.warning(
                "⚠️ No announcement channel configured — embeds disabled. "
                "Set PUCK_ANNOUNCE_CHANNEL_ID in .env"
            )
        else:
            self._log.info(
                f"EmbedAnnouncer initialized — channel {self._channel_id}"
            )

    # -------------------------------------------------------------------------
    # Persistence — survive restarts
    # -------------------------------------------------------------------------
    def _load_state(self) -> None:
        """Load active announcement message IDs from disk."""
        path = Path(ANNOUNCEMENTS_STATE_FILE)
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._active = json.load(f)
            self._log.debug(
                f"🔍 Loaded {len(self._active)} active announcement(s)"
            )
        except (json.JSONDecodeError, OSError) as e:
            self._log.warning(f"⚠️ Could not load announcements state: {e}")
            self._active = {}

    def _save_state(self) -> None:
        """Persist active announcement message IDs to disk."""
        try:
            path = Path(ANNOUNCEMENTS_STATE_FILE)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._active, f, indent=2)
        except OSError as e:
            self._log.error(f"❌ Could not save announcements state: {e}")

    # -------------------------------------------------------------------------
    # HTTP Client
    # -------------------------------------------------------------------------
    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self._token}",
            "Content-Type": "application/json",
        }

    # -------------------------------------------------------------------------
    # Embed Builder
    # -------------------------------------------------------------------------
    def _build_embed(self, status: StreamStatus) -> dict[str, Any]:
        """Build a Fluxer embed payload for a live Twitch stream."""
        uptime = ""
        if status.started_at:
            delta = datetime.now(timezone.utc) - status.started_at
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            if hours > 0:
                uptime = f"{hours}h {minutes}m"
            else:
                uptime = f"{minutes}m"

        # Cache-bust the thumbnail URL so Fluxer fetches the latest frame
        thumbnail = status.thumbnail_url or ""
        if thumbnail:
            thumbnail = f"{thumbnail}?t={int(time.time())}"

        stream_url = status.stream_url or f"https://twitch.tv/{status.platform_username}"

        fields = []

        if status.game_or_category:
            fields.append({
                "name": "Playing",
                "value": status.game_or_category,
                "inline": True,
            })

        if uptime:
            fields.append({
                "name": "Uptime",
                "value": uptime,
                "inline": True,
            })

        if status.viewer_count > 0:
            fields.append({
                "name": "Viewers",
                "value": str(status.viewer_count),
                "inline": True,
            })

        embed: dict[str, Any] = {
            "title": f"🔴 {status.display_name} is live on Twitch!",
            "url": stream_url,
            "color": EMBED_COLOR,
            "description": status.stream_title or "Live now!",
            "fields": fields,
            "footer": {
                "text": f"twitch.tv/{status.platform_username}",
            },
        }

        if thumbnail:
            embed["image"] = {"url": thumbnail}

        return embed

    # -------------------------------------------------------------------------
    # Public Interface
    # -------------------------------------------------------------------------
    async def create_announcement(self, status: StreamStatus) -> None:
        """Post a new stream announcement embed. Twitch only."""
        if status.platform != "twitch":
            return
        if not self._channel_id:
            return

        embed = self._build_embed(status)
        key = f"twitch:{status.platform_username}"

        http = await self._get_http()
        try:
            resp = await http.post(
                f"{FLUXER_API_BASE}/channels/{self._channel_id}/messages",
                headers=self._headers(),
                json={
                    "content": "",
                    "embeds": [embed],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            message_id = data.get("id", "")

            self._active[key] = {
                "message_id": message_id,
                "last_updated": time.time(),
                "fluxer_user_id": status.fluxer_user_id,
                "display_name": status.display_name,
            }
            self._save_state()

            self._log.success(
                f"Posted announcement for {status.display_name} "
                f"(msg {message_id})"
            )
        except httpx.HTTPError as e:
            self._log.error(
                f"❌ Failed to post announcement for {status.display_name}: {e}"
            )

    async def update_announcement(self, status: StreamStatus) -> None:
        """Update an existing announcement embed with fresh data. Twitch only."""
        if status.platform != "twitch":
            return
        if not self._channel_id:
            return

        key = f"twitch:{status.platform_username}"
        active = self._active.get(key)
        if not active:
            # No existing announcement — create one instead
            await self.create_announcement(status)
            return

        # Throttle: only update if 5+ minutes since last update
        last_updated = active.get("last_updated", 0)
        if time.time() - last_updated < UPDATE_INTERVAL_SECONDS:
            return

        message_id = active["message_id"]
        embed = self._build_embed(status)

        http = await self._get_http()
        try:
            resp = await http.patch(
                f"{FLUXER_API_BASE}/channels/{self._channel_id}/messages/{message_id}",
                headers=self._headers(),
                json={
                    "embeds": [embed],
                },
            )
            resp.raise_for_status()

            active["last_updated"] = time.time()
            self._save_state()

            self._log.debug(
                f"🔍 Updated announcement for {status.display_name}"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Message was manually deleted — recreate
                self._log.warning(
                    f"⚠️ Announcement message gone for {status.display_name} "
                    f"— recreating"
                )
                del self._active[key]
                self._save_state()
                await self.create_announcement(status)
            else:
                self._log.error(
                    f"❌ Failed to update announcement for "
                    f"{status.display_name}: {e}"
                )
        except httpx.HTTPError as e:
            self._log.error(
                f"❌ Failed to update announcement for "
                f"{status.display_name}: {e}"
            )

    async def delete_announcement(self, status: StreamStatus) -> None:
        """Delete the announcement embed when stream ends. Twitch only."""
        if status.platform != "twitch":
            return
        if not self._channel_id:
            return

        key = f"twitch:{status.platform_username}"
        active = self._active.get(key)
        if not active:
            return

        message_id = active["message_id"]
        http = await self._get_http()
        try:
            resp = await http.delete(
                f"{FLUXER_API_BASE}/channels/{self._channel_id}/messages/{message_id}",
                headers=self._headers(),
            )
            # 204 No Content = success, 404 = already gone (both fine)
            if resp.status_code not in (200, 204, 404):
                resp.raise_for_status()

            self._log.success(
                f"Removed announcement for {active.get('display_name', key)}"
            )
        except httpx.HTTPError as e:
            self._log.error(
                f"❌ Failed to delete announcement for "
                f"{active.get('display_name', key)}: {e}"
            )
        finally:
            self._active.pop(key, None)
            self._save_state()

    async def cleanup_stale(self) -> None:
        """Delete any announcements for streams that are no longer live.

        Called during startup reconciliation to clean up if the bot
        restarted while someone was live and they've since gone offline.
        """
        if not self._channel_id or not self._active:
            return

        self._log.info(
            f"Checking {len(self._active)} persisted announcement(s) "
            f"for cleanup..."
        )
        # Cleanup is handled by the stream monitor's reconciliation —
        # it will call delete_announcement for any persisted entries
        # where the streamer is no longer live.

    def get_active_keys(self) -> set[str]:
        """Return the set of stream keys that have active announcements."""
        return set(self._active.keys())

    def has_announcement(self, key: str) -> bool:
        """Check if a stream key has an active announcement."""
        return key in self._active


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
