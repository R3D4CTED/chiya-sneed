import logging
import requests

import discord
from discord.ext.commands import Bot, Cog
from discord_slash import cog_ext, SlashContext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import create_option, create_permission

from utils import embeds
from utils.config import config

log = logging.getLogger(__name__)


class Server(Cog):
    """ Server Commands Cog """

    def __init__(self, bot: Bot):
        self.bot = bot

    @cog_ext.cog_subcommand(
        base="server",
        name="pop",
        description="Gets the current server population",
        guild_ids=config["guild_ids"],
        base_default_permission=False,
        base_permissions={
            config["guild_ids"][0]: [
                create_permission(config["roles"]["staff"], SlashCommandPermissionType.ROLE, True),
                create_permission(config["roles"]["trial_mod"], SlashCommandPermissionType.ROLE, True)
            ]
        }
    )
    async def pop(self, ctx: SlashContext):
        """Returns the current guild member count."""
        await ctx.defer()
        await ctx.send(ctx.guild.member_count)

    @cog_ext.cog_subcommand(
        base="server",
        name="banner",
        description="Sets the banner to the image provided",
        guild_ids=config["guild_ids"],
        base_default_permission=False,
        options=[
            create_option(
                name="link",
                description="The link to the image to be set",
                option_type=3,
                required=True
            )
        ]
    )
    async def banner(self, ctx: SlashContext, link: str):
        """Sets the banner for the Discord server."""
        await ctx.defer()

        r = requests.get(url=link)

        if r.status_code != 200:
            return await embeds.error_message(ctx=ctx, description="The link you entered was not accessible.")

        try:
            await ctx.guild.edit(banner=r.content)
        except discord.errors.InvalidArgument:
            return await embeds.error_message(ctx=ctx, description="Unable to set banner, verify the link is correct.")

        embed = embeds.make_embed(
            ctx=ctx,
            title="Banner updated",
            description=f"Banner [image]({link}) updated by {ctx.author.mention}",
            color="soft_green"
        )

        await ctx.send(embed=embed)

    @cog_ext.cog_subcommand(
        base="server",
        name="topic",
        description="Sets the channel to the topic provided",
        guild_ids=config["guild_ids"],
        base_default_permission=False,
        options=[
            create_option(
                name="channel",
                description="The channel to edit",
                option_type=7,
                required=True
            ),
            create_option(
                name="topic",
                description="The topic message to set",
                option_type=3,
                required=True
            )
        ]
    )
    async def topic(self, ctx: SlashContext, channel: discord.TextChannel, topic: str):
        """Sets the banner for the Discord server."""
        await ctx.defer()
        if len(topic) >= 1024:
            return await embeds.error_message(ctx=ctx, description="Topic message must be less than 1024 characters.")
        await channel.edit(topic=topic)
        return await embeds.success_message(ctx=ctx, description="Successfully updated the channel topic.")


def setup(bot: Bot) -> None:
    """ Load the Server cog. """
    bot.add_cog(Server(bot))
    log.info("Commands loaded: server")
