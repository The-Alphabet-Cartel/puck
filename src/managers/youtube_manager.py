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
YouTube API manager for puck-bot. Handles YouTube Data API v3 live stream
checks with RSS pre-filtering for quota conservation.
----------------------------------------------------------------------------
FILE VERSION: v1.1.0
LAST MODIFIED: 2026-02-26
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from src.managers.config_manager import ConfigManager
from src.managers.logging_config_manager import LoggingConfigManager
from src.models.stream_status import StreamStatus

RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
API_BASE_URL = "https://www.googleapis.com/youtube/v3"
RSS_RECENCY_HOURS = 24
DAILY_QUOTA_LIMIT = 10000
SEARCH_COST = 100  # units per search.list call


class YouTubeManager:
    """Manages YouTube live stream detection with RSS pre-check for quota conservation."""

    def __init__(
        self,
        config_manager: ConfigManager,
        logging_manager: LoggingConfigManager,
    ) -> None:
        self._config = config_manager
        self._log = logging_manager.get_logger("youtube_manager")
        self._api_key = config_manager.get_youtube_api_key()
        self._http: Optional[httpx.AsyncClient] = None
        self._daily_quota_used: int = 0
        self._quota_reset_date: Optional[str] = None
        self._quota_exhausted: bool = False

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the shared HTTP client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    async def close(self) -> None:
        """Close the HTTP client gracefully."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    def _check_quota_reset(self) -> None:
        """Reset daily quota counter if a new day has started (Pacific time)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._quota_reset_date != today:
            self._daily_quota_used = 0
            self._quota_exhausted = False
            self._quota_reset_date = today
            self._log.debug("🔍 YouTube quota counter reset for new day")

    # -------------------------------------------------------------------------
    # RSS Pre-Check (free, no quota)
    # -------------------------------------------------------------------------
    async def _rss_has_recent_activity(self, channel_id: str) -> bool:
        """
        Check YouTube RSS feed for recent video activity.

        Returns True if any video was published in the last RSS_RECENCY_HOURS,
        meaning it's worth spending API quota to check for a live stream.
        Returns True on any error (fail-open to avoid missing live streams).
        """
        http = await self._get_http_client()
        url = RSS_URL.format(channel_id=channel_id)

        try:
            resp = await http.get(url)
            if resp.status_code != 200:
                self._log.debug(f"🔍 RSS check for {channel_id} returned {resp.status_code} — assuming active")
                return True

            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)

            if not entries:
                return False

            cutoff = datetime.now(timezone.utc) - timedelta(hours=RSS_RECENCY_HOURS)
            for entry in entries[:5]:  # Only check most recent entries
                published = entry.find("atom:published", ns)
                if published is not None and published.text:
                    pub_dt = datetime.fromisoformat(
                        published.text.replace("Z", "+00:00")
                    )
                    if pub_dt > cutoff:
                        return True
            return False

        except Exception as e:
            self._log.debug(f"🔍 RSS pre-check failed for {channel_id}: {e} — assuming active")
            return True  # Fail-open

    # -------------------------------------------------------------------------
    # YouTube Data API v3 Live Check
    # -------------------------------------------------------------------------
    async def _api_check_live(self, channel_id: str) -> Optional[StreamStatus]:
        """
        Check if a YouTube channel is currently live via the Data API v3.

        Costs 100 quota units per call. Returns StreamStatus if live, None if not.
        """
        self._check_quota_reset()

        if self._quota_exhausted:
            self._log.debug("🔍 YouTube quota exhausted — skipping API call")
            return None

        if not self._api_key:
            self._log.warning("⚠️ YouTube API key not configured — skipping")
            return None

        http = await self._get_http_client()

        try:
            resp = await http.get(
                f"{API_BASE_URL}/search",
                params={
                    "part": "snippet",
                    "channelId": channel_id,
                    "eventType": "live",
                    "type": "video",
                    "key": self._api_key,
                },
            )

            self._daily_quota_used += SEARCH_COST

            if resp.status_code == 403:
                self._log.warning("⚠️ YouTube API quota exhausted — switching to RSS-only mode")
                self._quota_exhausted = True
                return None

            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])

            if not items:
                return None

            item = items[0]
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            thumbnail = snippet.get("thumbnails", {}).get("high", {}).get("url", "")

            return StreamStatus(
                fluxer_user_id="",  # Mapped by stream_monitor
                display_name=snippet.get("channelTitle", ""),
                platform="youtube",
                platform_username=channel_id,
                is_live=True,
                stream_title=snippet.get("title"),
                game_or_category=None,
                viewer_count=0,  # Not available from search endpoint
                thumbnail_url=thumbnail,
                stream_url=f"https://youtube.com/watch?v={video_id}" if video_id else None,
                started_at=None,
            )

        except httpx.HTTPError as e:
            self._log.error(f"❌ YouTube API request failed for {channel_id}: {e}")
            return None

    # -------------------------------------------------------------------------
    # Public Interface
    # -------------------------------------------------------------------------
    async def check_streams(
        self, channel_ids: list[str]
    ) -> list[StreamStatus]:
        """
        Check live status for YouTube channels.

        Uses RSS pre-check to avoid spending API quota unnecessarily.
        """
        if not channel_ids:
            return []

        live_statuses: list[StreamStatus] = []
        checked_api = 0

        for channel_id in channel_ids:
            # Step 1: Free RSS pre-check
            has_activity = await self._rss_has_recent_activity(channel_id)
            if not has_activity:
                self._log.debug(f"🔍 RSS: No recent activity for {channel_id} — skipping API")
                continue

            # Step 2: API check (costs quota)
            status = await self._api_check_live(channel_id)
            checked_api += 1
            if status:
                live_statuses.append(status)

        self._log.debug(
            f"🔍 YouTube: {len(live_statuses)} live / {checked_api} API calls / "
            f"{len(channel_ids)} total channels / ~{self._daily_quota_used} quota used today"
        )
        return live_statuses


def create_youtube_manager(
    config_manager: ConfigManager,
    logging_manager: LoggingConfigManager,
) -> YouTubeManager:
    """Factory function — MANDATORY. Never call YouTubeManager directly."""
    return YouTubeManager(
        config_manager=config_manager,
        logging_manager=logging_manager,
    )


__all__ = ["YouTubeManager", "create_youtube_manager"]
