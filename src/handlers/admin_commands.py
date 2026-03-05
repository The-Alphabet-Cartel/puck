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
Admin utility handler for puck-bot. Provides the !roles command for
listing guild roles and their IDs — essential for populating config files
with correct role IDs without guessing.

Admin-only: requires the caller to have a role with the Administrator
permission bit (0x8).
----------------------------------------------------------------------------
FILE VERSION: v1.0.0
LAST MODIFIED: 2026-03-04
BOT: puck-bot
CLEAN ARCHITECTURE: Compliant
Repository: https://github.com/the-alphabet-cartel/puck
============================================================================
"""

import fluxer

from src.managers.config_manager import ConfigManager
from src.managers.logging_config_manager import LoggingConfigManager


class AdminCommandsHandler:
    """Admin-only commands for puck-bot. Currently implements !roles."""

    def __init__(
        self,
        bot: fluxer.Bot,
        config_manager: ConfigManager,
        logging_manager: LoggingConfigManager,
    ) -> None:
        self._bot = bot
        self._config = config_manager
        self._log = logging_manager.get_logger("admin_commands")

    async def handle(self, message: fluxer.Message) -> bool:
        """Process a message. Returns True if handled, False otherwise.

        Called by the main dispatcher for !-prefixed messages only.
        """
        content = message.content.strip().lower()

        if content == "!roles":
            await self._cmd_roles(message)
            return True

        return False

    async def _cmd_roles(self, message: fluxer.Message) -> None:
        """List all guild roles with their IDs. Admin-only."""
        guild_id = message.channel.guild_id
        try:
            guild = await self._bot.fetch_guild(guild_id)
            member = await guild.fetch_member(message.author.id)
            roles = await guild.fetch_roles()
        except Exception as e:
            self._log.error(f"Could not fetch guild data: {e}")
            return

        # member.roles is list[int] in fluxer-py (not role objects)
        member_role_ids = set(member.roles)

        # Check if any of the member's roles have Administrator (0x8)
        is_admin = any(
            r for r in roles
            if r.id in member_role_ids and getattr(r, "permissions", 0) & 0x8
        )

        if not is_admin:
            self._log.debug(
                f"!roles ignored for {message.author} — not an administrator"
            )
            return

        self._log.info(f"!roles used by {message.author} in #{message.channel}")

        lines = ["**Guild Roles and IDs:**\n```"]
        for role in sorted(roles, key=lambda r: r.position, reverse=True):
            lines.append(f"{role.name:<40} {role.id}")
        lines.append("```")

        output = "\n".join(lines)

        # Fluxer message limit is 2000 chars — chunk if needed
        if len(output) <= 2000:
            await message.reply(output)
        else:
            chunks = []
            chunk = ["**Guild Roles and IDs:**\n```"]
            for role in sorted(roles, key=lambda r: r.position, reverse=True):
                line = f"{role.name:<40} {role.id}"
                if sum(len(ln) for ln in chunk) + len(line) > 1900:
                    chunk.append("```")
                    chunks.append("\n".join(chunk))
                    chunk = ["```"]
                chunk.append(line)
            chunk.append("```")
            chunks.append("\n".join(chunk))
            for c in chunks:
                await message.reply(c)


def create_admin_commands_handler(
    bot: fluxer.Bot,
    config_manager: ConfigManager,
    logging_manager: LoggingConfigManager,
) -> AdminCommandsHandler:
    """Factory function — MANDATORY. Never call AdminCommandsHandler directly."""
    return AdminCommandsHandler(
        bot=bot,
        config_manager=config_manager,
        logging_manager=logging_manager,
    )


__all__ = ["AdminCommandsHandler", "create_admin_commands_handler"]
