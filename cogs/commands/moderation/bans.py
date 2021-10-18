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


class BanCog(Cog):
    """ Ban Cog """

    def __init__(self, bot):
        self.bot = bot

    async def ban_member(ctx: SlashContext, user: discord.User, reason: str, delete_message_days: int = 0):
        # Info: https://discordpy.readthedocs.io/en/stable/api.html#discord.Guild.ban
        await ctx.guild.ban(user=user, reason=reason, delete_message_days=delete_message_days)

        # Open a connection to the database.
        db = database.Database().get()

        # Add the ban to the mod_log database.
        db["mod_logs"].insert(dict(
            user_id=user.id, mod_id=ctx.author.id, timestamp=int(time.time()), reason=reason, type="ban"
        ))

        # Commit the changes to the database and close the connection.
        db.commit()
        db.close()

    async def unban_user(self, user: discord.User, reason: str, ctx: SlashContext = None, guild: discord.Guild = None):
        guild = guild or ctx.guild
        moderator = ctx.author if ctx else self.bot.user

        # Info: https://discordpy.readthedocs.io/en/stable/api.html#discord.Guild.unban
        try:
            await guild.unban(user=user, reason=reason)
        except discord.HTTPException:
            return

        # Open a connection to the database.
        db = database.Database().get()

        # Add the unban to the mod_log database.
        db["mod_logs"].insert(dict(
            user_id=user.id, mod_id=moderator.id, timestamp=int(time.time()), reason=reason, type="unban"
        ))

        # Commit the changes to the database and close the connection.
        db.commit()
        db.close()

    async def is_user_in_guild(self, guild: discord.Guild, user: discord.User):
        # Checks to see if the user is in the guild. If true, return the member, or None otherwise.
        guild = self.bot.get_guild(guild)
        member = guild.get_member(user.id)
        if member:
            return member
        return None

    async def is_user_banned(self, guild: discord.Guild, user: discord.User) -> bool:
        # Checks to see if the user is already banned.
        guild = self.bot.get_guild(guild)
        try:
            return await guild.fetch_ban(user)
        except discord.HTTPException:
            return False

    async def send_banned_dm_embed(ctx: SlashContext, user: discord.User, reason: str = None) -> bool:
        try:  # In case user has DMs Blocked.
            channel = await user.create_dm()
            embed = embeds.make_embed(
                author=False,
                title="Uh-oh, you've been banned!",
                description=(
                    "You can submit a ban appeal on our subreddit [here]"
                    "(https://www.reddit.com/message/compose/?to=/r/animepiracy)."
                ),
                color=0xc2bac0
            )
            embed.add_field(name="Server:", value=f"[{ctx.guild}](https://discord.gg/piracy)", inline=True)
            embed.add_field(name="Moderator:", value=ctx.author.mention, inline=True)
            embed.add_field(name="Length:", value="Indefinite", inline=True)
            embed.add_field(name="Reason:", value=reason, inline=False)
            embed.set_image(url="https://i.imgur.com/CglQwK5.gif")
            await channel.send(embed=embed)
        except discord.HTTPException:
            return False
        return True

    @cog_ext.cog_slash(
        name="ban",
        description="Bans the user from the server",
        guild_ids=config["guild_ids"],
        options=[
            create_option(
                name="user",
                description="The member that will be banned",
                option_type=6,
                required=True
            ),
            create_option(
                name="reason",
                description="The reason why the member is being banned",
                option_type=3,
                required=False
            ),
            create_option(
                name="daystodelete",
                description="The number of days of messages to delete from the member, up to 7",
                option_type=4,
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
    async def ban(self, ctx: SlashContext, user: discord.User, reason: str = None, daystodelete: int = 0):
        """ Temporarily bans member from guild. """
        await ctx.defer()

        # If we received an int instead of a discord.Member, the user is not in the server.
        if not isinstance(user, discord.Member):
            user = await self.bot.fetch_user(user)

        # Some basic checks to make sure mods can't cause problems with their ban.
        member = await self.is_user_in_guild(guild=ctx.guild.id, user=user)
        if member:
            if not await can_action_member(bot=self.bot, ctx=ctx, member=member):
                return await embeds.error_message(ctx=ctx, description=f"You cannot action {member.mention}.")

        # Checks if the user is already banned and let's the mod know if they already were.
        banned = await self.is_user_banned(guild=ctx.guild.id, user=user)
        if banned:
            return await embeds.error_message(ctx=ctx, description=f"{user.mention} is already banned.")

        # Discord caps embed fields at a ridiculously low character limit, avoids problems with future embeds.
        if not reason:
            reason = "No reason provided."
        # Discord caps embed fields at a ridiculously low character limit, avoids problems with future embeds.
        elif len(reason) > 512:
            return await embeds.error_message(ctx=ctx, description="Reason must be less than 512 characters.")

        # Start creating the embed that will be used to alert the moderator that the user was successfully banned.
        embed = embeds.make_embed(
            ctx=ctx,
            title=f"Banning user: {user.name}",
            description=f"{user.mention} was banned by {ctx.author.mention} for: {reason}",
            thumbnail_url="https://i.imgur.com/l0jyxkz.png",
            color="soft_red"
        )

        # Attempt to DM the user that they have been banned with various information about their ban.
        # If the bot was unable to DM the user, adds a notice to the output to let the mod know.
        sent = await self.send_banned_dm_embed(ctx=ctx, user=user, reason=reason)
        if not sent:
            embed.add_field(
                name="Notice:",
                value=(
                    f"Unable to message {user.mention} about this action. "
                    "This can be caused by the user not being in the server, "
                    "having DMs disabled, or having the bot blocked."
                )
            )

        # Bans the user and returns the embed letting the moderator know they were successfully banned.
        await self.ban_member(ctx=ctx, user=user, reason=reason, delete_message_days=daystodelete)
        return await ctx.send(embed=embed)

    @cog_ext.cog_slash(
        name="unban",
        description="Unbans the user from the server",
        guild_ids=config["guild_ids"],
        options=[
            create_option(
                name="user",
                description="The user that will be unbanned",
                option_type=6,
                required=True
            ),
            create_option(
                name="reason",
                description="The reason why the user is being unbanned",
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
    async def unban(self, ctx: SlashContext, user: discord.User, reason: str = None):
        """ Unbans user from guild. """
        await ctx.defer()

        user = await self.bot.fetch_user(user)

        # Checks if the user is already banned and let's the mod know if they are not.
        banned = await self.is_user_banned(guild=ctx.guild.id, user=user)
        if not banned:
            return await embeds.error_message(ctx=ctx, description=f"{user.mention} is not banned.")

        # Discord caps embed fields at a ridiculously low character limit, avoids problems with future embeds.
        if not reason:
            reason = "No reason provided."
        # Discord caps embed fields at a ridiculously low character limit, avoids problems with future embeds.
        elif len(reason) > 512:
            return await embeds.error_message(ctx=ctx, description="Reason must be less than 512 characters.")

        # Creates and sends the embed that will be used to alert the moderator that the user was successfully banned.
        embed = embeds.make_embed(
            ctx=ctx,
            title=f"Unbanning user: {user.name}",
            description=f"{user.mention} was unbanned by {ctx.author.mention} for: {reason}",
            thumbnail_url="https://i.imgur.com/4H0IYJH.png",
            color="soft_green"
        )

        # Unbans the user and returns the embed letting the moderator know they were successfully banned.
        await self.unban_user(ctx=ctx, user=user, reason=reason)
        await ctx.send(embed=embed)


def setup(bot: Bot) -> None:
    """ Load the Ban cog. """
    bot.add_cog(BanCog(bot))
    log.info("Commands loaded: bans")
