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
Main entry point for puck-bot. Creates all managers via factory functions,
registers the on_ready event, starts the background polling task, and runs
the Fluxer bot.
----------------------------------------------------------------------------
FILE VERSION: v1.1.0
LAST MODIFIED: 2026-02-26
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

import asyncio
import sys
import traceback

import fluxer

from src.managers.config_manager import create_config_manager
from src.managers.logging_config_manager import create_logging_config_manager
from src.managers.twitch_manager import create_twitch_manager
from src.managers.youtube_manager import create_youtube_manager
from src.managers.stream_state_manager import create_stream_state_manager
from src.handlers.stream_monitor import create_stream_monitor
from src.handlers.embed_announcer import create_embed_announcer


def main() -> None:
    # =========================================================================
    # Phase 1: Configuration (three-layer stack)
    # =========================================================================
    config = create_config_manager()

    # =========================================================================
    # Phase 2: Logging
    # =========================================================================
    logging_mgr = create_logging_config_manager(
        log_level=config.get("logging", "level", "INFO"),
        log_format=config.get("logging", "format", "human"),
        log_file=config.get("logging", "file"),
        console_enabled=config.get_bool("logging", "console", True),
        app_name="puck-bot",
    )
    log = logging_mgr.get_logger("main")
    log.info("Puck bot starting up...")

    # =========================================================================
    # Phase 3: Validate critical config
    # =========================================================================
    token = config.get_token()
    if not token:
        log.error("❌ No Fluxer bot token found — cannot start. Check Docker Secrets.")
        sys.exit(1)

    guild_id = config.get_guild_id()
    if not guild_id:
        log.warning("⚠️ No guild ID configured — role operations will fail")

    live_role_id = config.get_live_role_id()
    if not live_role_id:
        log.warning("⚠️ No Live role ID configured — role operations will fail")

    tracked = config.get_tracked_streams()
    twitch_count = sum(1 for s in tracked if s.get("twitch_username"))
    youtube_count = sum(1 for s in tracked if s.get("youtube_channel_id"))
    log.info(
        f"Tracking {len(tracked)} stream(s): "
        f"{twitch_count} Twitch, {youtube_count} YouTube"
    )

    # =========================================================================
    # Phase 4: Create managers via factory functions
    # =========================================================================
    twitch_mgr = create_twitch_manager(config, logging_mgr)
    youtube_mgr = create_youtube_manager(config, logging_mgr)
    state_mgr = create_stream_state_manager(config, logging_mgr)
    embed_announcer = create_embed_announcer(config, logging_mgr)

    # =========================================================================
    # Phase 5: Create bot and handlers
    # =========================================================================
    intents = fluxer.Intents.all()
    intents.message_content = True
    intents.members = True

    bot = fluxer.Bot(
        command_prefix=config.get("bot", "command_prefix", "!"),
        intents=intents,
    )

    monitor = create_stream_monitor(
        bot=bot,
        config_manager=config,
        logging_manager=logging_mgr,
        twitch_manager=twitch_mgr,
        youtube_manager=youtube_mgr,
        state_manager=state_mgr,
        embed_announcer=embed_announcer,
    )

    # =========================================================================
    # Phase 6: Register events and start
    # =========================================================================
    @bot.event
    async def on_ready() -> None:
        log.success(f"Puck connected to Fluxer as {bot.user}")
        log.info(
            f"Guild: {guild_id} | Live Role: {live_role_id} | "
            f"Poll interval: {config.get_poll_interval()}s"
        )
        # Start the background polling task
        asyncio.create_task(_run_monitor())

    async def _run_monitor() -> None:
        """Wrapper to catch and log monitor startup errors."""
        try:
            await monitor.start()
        except Exception as e:
            log.error(f"❌ Stream monitor crashed: {e}\n{traceback.format_exc()}")

    # =========================================================================
    # Phase 7: Run (blocking)
    # =========================================================================
    log.info("Connecting to Fluxer gateway...")
    try:
        bot.run(token)
    except KeyboardInterrupt:
        log.info("Received shutdown signal")
        monitor.stop()
    except Exception as e:
        log.error(f"❌ Fatal error: {e}\n{traceback.format_exc()}")
        sys.exit(1)
    finally:
        log.info("Puck bot shut down")


if __name__ == "__main__":
    main()
