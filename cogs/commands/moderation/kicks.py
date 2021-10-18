import logging
import time

import discord
from discord.ext.commands import Cog, Bot
from discord_slash import cog_ext, SlashContext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import create_option, create_permission

from utils import database
from utils import embeds
from utils.config import config
from utils.moderation import can_action_member

# Enabling logs
log = logging.getLogger(__name__)


class KickCog(Cog):
    """ Kick Cog """

    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(
        name="kick",
        description="Kicks the member from the server",
        guild_ids=config["guild_ids"],
        options=[
            create_option(
                name="member",
                description="The member that will be kicked",
                option_type=6,
                required=True
            ),
            create_option(
                name="reason",
                description="The reason why the member is being kicked",
                option_type=3,
                required=False
            ),
        ],
        default_permission=False,
        permissions={
            config["guild_ids"][0]: [
                create_permission(config["roles"]["staff"], SlashCommandPermissionType.ROLE, True),
                create_permission(config["roles"]["trial_mod"], SlashCommandPermissionType.ROLE, True)
            ]
        }
    )
    async def kick_member(self, ctx: SlashContext, member: discord.Member, reason: str = None):
        """ Kicks member from guild. """
        await ctx.defer()

        # If we received an int instead of a discord.Member, the user is not in the server.
        if not isinstance(member, discord.Member):
            return await embeds.error_message(ctx=ctx, description="That user is not in the server.")

        # Checks if invoker can action that member (self, bot, etc.)
        if not await can_action_member(bot=self.bot, ctx=ctx, member=member):
            return await embeds.error_message(ctx=ctx, description=f"You cannot action {member.mention}.")

        # Discord caps embed fields at a ridiculously low character limit, avoids problems with future embeds.
        if not reason:
            reason = "No reason provided."
        # Discord caps embed fields at a ridiculously low character limit, avoids problems with future embeds.
        elif len(reason) > 512:
            return await embeds.error_message(ctx=ctx, description="Reason must be less than 512 characters.")

        embed = embeds.make_embed(
            ctx=ctx,
            title=f"Kicking member: {member.name}",
            description=f"{member.mention} was kicked by {ctx.author.mention} for: {reason}",
            thumbnail_url="https://i.imgur.com/l0jyxkz.png",
            color="soft_red"
        )

        # Send user message telling them that they were kicked and why.
        try:  # In case user has DMs blocked.
            channel = await member.create_dm()
            dm_embed = embeds.make_embed(
                title="Uh-oh, you've been kicked!",
                description="I-I guess you can join back if you want? B-baka!",
                image_url="https://i.imgur.com/UkrBRur.gif",
                author=False,
                color=0xe49bb3
            )
            dm_embed.add_field(name="Server:", value=f"[{ctx.guild}](https://discord.gg/piracy)", inline=True)
            dm_embed.add_field(name="Moderator:", value=ctx.author.mention, inline=True)
            dm_embed.add_field(name="Reason:", value=reason, inline=False)
            await channel.send(embed=dm_embed)
        except discord.HTTPException:
            embed.add_field(
                name="Notice:",
                value=(
                    f"Unable to message {member.mention} about this action. "
                    "This can be caused by the user not being in the server, "
                    "having DMs disabled, or having the bot blocked."
                )
            )

        # Send the kick DM to the user.
        await ctx.send(embed=embed)

        # Info: https://discordpy.readthedocs.io/en/stable/api.html#discord.Guild.kick
        await ctx.guild.kick(user=member, reason=reason)

        # Open a connection to the database.
        db = database.Database().get()

        # Add the kick to the mod_log database.
        db["mod_logs"].insert(dict(
            user_id=member.id, mod_id=ctx.author.id, timestamp=int(time.time()), reason=reason, type="kick"
        ))

        # Commit the changes to the database and close the connection.
        db.commit()
        db.close()


def setup(bot: Bot) -> None:
    """ Load the Kick cog. """
    bot.add_cog(KickCog(bot))
    log.info("Commands loaded: kicks")
