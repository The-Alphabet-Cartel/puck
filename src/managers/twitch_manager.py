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
Twitch API manager for puck-bot. Handles OAuth client credentials auth and
batch stream status checks via the Twitch Helix API.
----------------------------------------------------------------------------
FILE VERSION: v1.1.0
LAST MODIFIED: 2026-02-26
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.managers.config_manager import ConfigManager
from src.managers.logging_config_manager import LoggingConfigManager
from src.models.stream_status import StreamStatus

HELIX_BASE_URL = "https://api.twitch.tv/helix"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"


class TwitchManager:
    """Manages Twitch Helix API authentication and stream status checks."""

    def __init__(
        self,
        config_manager: ConfigManager,
        logging_manager: LoggingConfigManager,
    ) -> None:
        self._config = config_manager
        self._log = logging_manager.get_logger("twitch_manager")
        self._client_id = config_manager.get_twitch_client_id()
        self._client_secret = config_manager.get_twitch_client_secret()
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._http: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    async def close(self) -> None:
        """Close the HTTP client gracefully."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # -------------------------------------------------------------------------
    # OAuth Client Credentials
    # -------------------------------------------------------------------------
    async def _ensure_token(self) -> bool:
        """Ensure we have a valid app access token, refreshing if needed."""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return True

        if not self._client_id or not self._client_secret:
            self._log.error("❌ Twitch client_id or client_secret not configured")
            return False

        try:
            http = await self._get_http_client()
            resp = await http.post(
                TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "client_credentials",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expires_at = time.time() + data.get("expires_in", 3600)
            self._log.success("Twitch OAuth token acquired")
            return True
        except httpx.HTTPError as e:
            self._log.error(f"❌ Twitch OAuth token request failed: {e}")
            return False

    # -------------------------------------------------------------------------
    # Stream Status Checking
    # -------------------------------------------------------------------------
    async def check_streams(
        self, usernames: list[str]
    ) -> list[StreamStatus]:
        """
        Check live status for a batch of Twitch usernames.

        Twitch Helix supports up to 100 user_login params per request.
        Returns a StreamStatus for each username that is currently live.
        Usernames NOT in the response are offline.
        """
        if not usernames:
            return []

        if not await self._ensure_token():
            self._log.warning("⚠️ Skipping Twitch check — no valid token")
            return []

        http = await self._get_http_client()
        headers = {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {self._access_token}",
        }

        live_statuses: list[StreamStatus] = []

        # Batch in groups of 100 (Helix limit)
        for i in range(0, len(usernames), 100):
            batch = usernames[i : i + 100]
            params = [("user_login", name) for name in batch]

            try:
                resp = await http.get(
                    f"{HELIX_BASE_URL}/streams",
                    params=params,
                    headers=headers,
                )

                if resp.status_code == 401:
                    self._log.warning("⚠️ Twitch token expired — refreshing")
                    self._access_token = None
                    if await self._ensure_token():
                        headers["Authorization"] = f"Bearer {self._access_token}"
                        resp = await http.get(
                            f"{HELIX_BASE_URL}/streams",
                            params=params,
                            headers=headers,
                        )
                    else:
                        continue

                resp.raise_for_status()
                data = resp.json()

                for stream in data.get("data", []):
                    started_at = None
                    if stream.get("started_at"):
                        started_at = datetime.fromisoformat(
                            stream["started_at"].replace("Z", "+00:00")
                        )
                    thumbnail = stream.get("thumbnail_url", "")
                    if thumbnail:
                        thumbnail = thumbnail.replace("{width}", "640").replace("{height}", "360")

                    live_statuses.append(StreamStatus(
                        fluxer_user_id="",  # Mapped by stream_monitor
                        display_name=stream.get("user_name", ""),
                        platform="twitch",
                        platform_username=stream.get("user_login", "").lower(),
                        is_live=True,
                        stream_title=stream.get("title"),
                        game_or_category=stream.get("game_name"),
                        viewer_count=stream.get("viewer_count", 0),
                        thumbnail_url=thumbnail,
                        stream_url=f"https://twitch.tv/{stream.get('user_login', '')}",
                        started_at=started_at,
                    ))

                self._log.debug(
                    f"🔍 Twitch batch {i // 100 + 1}: "
                    f"{len(data.get('data', []))} live / {len(batch)} checked"
                )

            except httpx.HTTPError as e:
                self._log.error(f"❌ Twitch API request failed: {e}")
                continue

        return live_statuses


def create_twitch_manager(
    config_manager: ConfigManager,
    logging_manager: LoggingConfigManager,
) -> TwitchManager:
    """Factory function — MANDATORY. Never call TwitchManager directly."""
    return TwitchManager(
        config_manager=config_manager,
        logging_manager=logging_manager,
    )


__all__ = ["TwitchManager", "create_twitch_manager"]
